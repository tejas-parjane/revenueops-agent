import time
from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.encryption import decrypt_credentials, encrypt_credentials
from app.core.time import as_utc, utcnow
from app.db.session import SessionLocal
from app.integrations.base import (
    CredentialError,
    ExternalAPIError,
    ExternalTimeoutError,
    IntegrationError,
    RateLimitError,
)
from app.integrations.registry import get_adapter
from app.models.entities import (
    ActionExecution,
    Approval,
    Integration,
    OrganizationMember,
    Recommendation,
)
from app.schemas.actions import validate_action_payload
from app.schemas.executions import ExecutionRetryRequest, ExecutionSchema
from app.services import audit

EXECUTOR_ROLES = {"owner", "admin", "manager"}


def _assert_executor(db: Session, organization_id: UUID, user_id: UUID) -> None:
    membership = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
        )
    )
    if not membership or membership.role not in EXECUTOR_ROLES:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="User is not authorized to execute actions",
        )


def list_executions(db: Session, organization_id: UUID) -> list[ExecutionSchema]:
    rows = db.scalars(
        select(ActionExecution)
        .where(ActionExecution.organization_id == organization_id)
        .order_by(ActionExecution.created_at.desc())
    ).all()
    return [ExecutionSchema.model_validate(row) for row in rows]


def get_execution(db: Session, organization_id: UUID, execution_id: UUID) -> ExecutionSchema:
    execution = db.scalar(
        select(ActionExecution).where(
            ActionExecution.id == execution_id,
            ActionExecution.organization_id == organization_id,
        )
    )
    if not execution:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Execution not found")
    return ExecutionSchema.model_validate(execution)


def _with_retries(operation: Callable[[], Any]) -> Any:
    attempts = max(settings.execution_max_retries, 1)
    for attempt in range(attempts):
        try:
            return operation()
        except RateLimitError:
            if attempt == attempts - 1:
                raise
            time.sleep(settings.execution_retry_delay_seconds * (2**attempt))
    raise ExternalAPIError("Execution failed after bounded retries")


def _claim_execution(db: Session, execution_id: UUID) -> bool:
    result = db.execute(
        update(ActionExecution)
        .where(
            ActionExecution.id == execution_id,
            ActionExecution.status.in_({"pending", "failed"}),
        )
        .values(status="running")
    )
    db.commit()
    return result.rowcount == 1


def _credentials(db: Session, integration: Integration) -> dict[str, Any]:
    try:
        return decrypt_credentials(integration.encrypted_credentials)
    except ValueError as exc:
        raise CredentialError(str(exc)) from exc


def _persist_refreshed_credentials(
    db: Session,
    integration: Integration,
    original: dict[str, Any],
    adapter: Any,
) -> None:
    if adapter.credentials != original:
        integration.encrypted_credentials = encrypt_credentials(adapter.credentials)
        db.commit()


def _call_adapter(
    db: Session,
    execution: ActionExecution,
    integration: Integration,
    action: dict[str, Any],
    lead: Recommendation,
) -> tuple[dict[str, Any], bool]:
    action = validate_action_payload(action)
    if action.get("provider") != integration.provider:
        raise ExternalAPIError("Action provider does not match the connected integration")
    credentials = _credentials(db, integration)
    adapter = get_adapter(integration.provider, credentials)
    adapter.check_connection()
    action_type = str(action.get("type") or "")
    record_id = str(action.get("record_id") or action.get("external_id") or "")

    if action_type == "send_email":
        message = {
            "to": action.get("to"),
            "subject": action.get("subject"),
            "body": action.get("body"),
            "lead_id": str(lead.lead_id),
            "idempotency_key": execution.idempotency_key,
        }
        draft = adapter.create_draft(message)
        sent = adapter.send_email(message)
        reference = str(sent.get("id") or "")
        response: dict[str, Any] = {"draft": draft, "sent": sent}
        hubspot = db.scalar(
            select(Integration).where(
                Integration.organization_id == execution.organization_id,
                Integration.provider == "hubspot",
            )
        )
        if hubspot and hubspot.connection_status == "connected":
            hubspot_credentials = _credentials(db, hubspot)
            hubspot_adapter = get_adapter("hubspot", hubspot_credentials)
            activity = hubspot_adapter.create_task(
                {
                    "title": f"Follow-up sent to {action.get('to')}",
                    "description": "Approved follow-up sent by RevenueOps Agent.",
                    "record_id": record_id,
                    "idempotency_key": f"{execution.idempotency_key}:crm-activity",
                    "metadata": {"message_id": reference},
                }
            )
            response["crm_activity"] = activity
            verified = adapter.verify_action("send_email", reference) and hubspot_adapter.verify_action(
                "create_task", str(activity.get("id") or "")
            )
        else:
            verified = adapter.verify_action("send_email", reference)
        _persist_refreshed_credentials(db, integration, credentials, adapter)
        if hubspot and hubspot.connection_status == "connected":
            _persist_refreshed_credentials(db, hubspot, hubspot_credentials, hubspot_adapter)
        return response, verified

    if action_type == "create_task":
        result = adapter.create_task(
            {
                "title": action.get("title") or "RevenueOps follow-up",
                "description": action.get("description") or action.get("business_justification"),
                "record_id": record_id,
                "lead_id": str(lead.lead_id),
                "idempotency_key": execution.idempotency_key,
            }
        )
        reference = str(result.get("id") or result.get("reference") or "")
        verified = adapter.verify_action("create_task", reference)
        _persist_refreshed_credentials(db, integration, credentials, adapter)
        return {"task": result}, verified

    if action_type == "update_crm":
        result = adapter.update_record(
            {
                "record_id": record_id,
                "properties": action.get("properties") or {},
                "lead_id": str(lead.lead_id),
                "idempotency_key": execution.idempotency_key,
            }
        )
        reference = str(result.get("id") or result.get("reference") or "")
        verified = adapter.verify_action("update_crm", reference)
        _persist_refreshed_credentials(db, integration, credentials, adapter)
        return {"update": result}, verified

    raise ExternalAPIError(f"Unsupported action type: {action_type}")


def _execute(db: Session, execution_id: UUID) -> None:
    if not _claim_execution(db, execution_id):
        return
    execution = db.scalar(select(ActionExecution).where(ActionExecution.id == execution_id))
    if not execution:
        return

    approval = db.scalar(
        select(Approval).where(
            Approval.id == execution.approval_id,
            Approval.organization_id == execution.organization_id,
            Approval.recommendation_id == execution.recommendation_id,
        )
    )
    recommendation = db.scalar(
        select(Recommendation).where(
            Recommendation.id == execution.recommendation_id,
            Recommendation.organization_id == execution.organization_id,
            Recommendation.task_id == execution.task_id,
        )
    )
    integration = db.scalar(
        select(Integration).where(
            Integration.id == execution.integration_id,
            Integration.organization_id == execution.organization_id,
            Integration.provider == (execution.request_payload or {}).get("provider"),
        )
    )
    if not approval or not recommendation or not integration:
        execution.status = "failed"
        execution.error_message = "Execution references missing records"
        db.commit()
        return

    if approval.status != "approved":
        execution.status = "failed"
        execution.error_message = "Execution attempted without an approved action"
        db.commit()
        return
    now = utcnow()
    if (as_utc(approval.expires_at) or now) <= now:
        execution.status = "failed"
        execution.error_message = "Approval expired before execution"
        approval.status = "expired"
        db.commit()
        return

    action = execution.request_payload or {}
    try:
        response, verified = _with_retries(
            lambda: _call_adapter(db, execution, integration, action, recommendation)
        )
        execution.executed_at = utcnow()
        if verified:
            execution.status = "verified"
            execution.error_message = None
            recommendation.status = "executed"
            response["verified"] = True
        else:
            execution.status = "failed"
            execution.error_message = "External operation could not be verified"
            recommendation.status = "failed"
            response["verified"] = False
        execution.response_payload = response
        audit.log_event(
            db,
            execution.organization_id,
            approval.approved_by,
            "action.executed",
            "action_execution",
            execution.id,
            {"action_type": execution.action_type, "status": execution.status},
        )
    except ExternalTimeoutError as exc:
        execution.status = "uncertain"
        execution.error_message = f"External operation timed out: {exc}"
        recommendation.status = "uncertain"
    except (IntegrationError, ValueError) as exc:
        execution.status = "failed"
        execution.error_message = str(exc)
        recommendation.status = "failed"
    except Exception as exc:
        execution.status = "failed"
        execution.error_message = f"Unexpected execution error: {exc}"
        recommendation.status = "failed"
    db.commit()


def execute_action_sync(execution_id: str) -> None:
    db = SessionLocal()
    try:
        _execute(db, UUID(execution_id))
    finally:
        db.close()


def _reconcile_uncertain(
    db: Session,
    execution: ActionExecution,
    integration: Integration,
    recommendation: Recommendation,
) -> bool:
    response = dict(execution.response_payload or {})
    if not response:
        return False
    try:
        action = validate_action_payload(execution.request_payload or {})
        credentials = _credentials(db, integration)
        adapter = get_adapter(integration.provider, credentials)
        action_type = str(action["type"])

        if action_type == "send_email":
            sent = response.get("sent") if isinstance(response.get("sent"), dict) else {}
            reference = str(sent.get("id") or "")
            verified = bool(reference) and adapter.verify_action("send_email", reference)
            crm = response.get("crm_activity") if isinstance(response.get("crm_activity"), dict) else {}
            if verified and crm.get("id"):
                hubspot = db.scalar(
                    select(Integration).where(
                        Integration.organization_id == execution.organization_id,
                        Integration.provider == "hubspot",
                        Integration.connection_status == "connected",
                    )
                )
                verified = bool(hubspot) and get_adapter(
                    "hubspot", _credentials(db, hubspot)
                ).verify_action("create_task", str(crm["id"]))
        elif action_type == "create_task":
            task = response.get("task") if isinstance(response.get("task"), dict) else {}
            reference = str(task.get("id") or task.get("reference") or "")
            verified = bool(reference) and adapter.verify_action("create_task", reference)
        elif action_type == "update_crm":
            update = response.get("update") if isinstance(response.get("update"), dict) else {}
            reference = str(update.get("id") or update.get("reference") or "")
            verified = bool(reference) and adapter.verify_action("update_crm", reference)
        else:
            return False
        _persist_refreshed_credentials(db, integration, credentials, adapter)
    except (IntegrationError, ValueError):
        return False

    if not verified:
        return False

    response["verified"] = True
    execution.status = "verified"
    execution.error_message = None
    execution.response_payload = response
    recommendation.status = "executed"
    audit.log_event(
        db,
        execution.organization_id,
        None,
        "action.reconciled",
        "action_execution",
        execution.id,
        {"idempotency_key": execution.idempotency_key},
    )
    db.commit()
    return True


def retry_execution(
    db: Session,
    organization_id: UUID,
    user_id: UUID,
    execution_id: UUID,
    request: ExecutionRetryRequest | None = None,
) -> ExecutionSchema:
    execution = db.scalar(
        select(ActionExecution).where(
            ActionExecution.id == execution_id,
            ActionExecution.organization_id == organization_id,
        )
    )
    if not execution:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Execution not found")
    _assert_executor(db, organization_id, user_id)
    if execution.status == "verified":
        return ExecutionSchema.model_validate(execution)
    if execution.status == "running":
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail="Execution is already running")

    approval = db.scalar(
        select(Approval).where(
            Approval.id == execution.approval_id,
            Approval.organization_id == organization_id,
            Approval.recommendation_id == execution.recommendation_id,
        )
    )
    now = utcnow()
    if not approval or approval.status != "approved" or (as_utc(approval.expires_at) or now) <= now:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Execution cannot be retried without a valid approval",
        )

    if execution.status == "uncertain":
        recommendation = db.scalar(
            select(Recommendation).where(
                Recommendation.id == execution.recommendation_id,
                Recommendation.organization_id == organization_id,
            )
        )
        integration = db.scalar(
            select(Integration).where(
                Integration.id == execution.integration_id,
                Integration.organization_id == organization_id,
            )
        )
        if recommendation and integration and _reconcile_uncertain(
            db, execution, integration, recommendation
        ):
            db.refresh(execution)
            return ExecutionSchema.model_validate(execution)
        if request is None or not request.acknowledge_uncertain:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="Execution outcome is uncertain; reconcile or acknowledge before retry",
            )

    if execution.status not in {"pending", "failed", "uncertain"}:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="Execution cannot be retried from its current status",
        )

    execution.status = "pending"
    execution.error_message = None
    execution.response_payload = None
    audit.log_event(
        db,
        organization_id,
        user_id,
        "action.retried",
        "action_execution",
        execution.id,
        {
            "idempotency_key": execution.idempotency_key,
            "acknowledged_uncertain": bool(request and request.acknowledge_uncertain),
            "note": request.note if request else None,
        },
    )
    db.commit()
    db.refresh(execution)

    from app.workers.dispatch import dispatch_execution

    dispatch_execution(execution.id)
    db.refresh(execution)
    return ExecutionSchema.model_validate(execution)
