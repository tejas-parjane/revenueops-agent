from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.hashing import action_hash
from app.core.time import as_utc, utcnow
from app.models.entities import (
    ActionExecution,
    Approval,
    Integration,
    Lead,
    OrganizationMember,
    Recommendation,
)
from app.schemas.agent import RecommendationSchema
from app.schemas.approvals import ApprovalActionRequest, ApprovalDetailSchema, ApprovalRejectRequest
from app.schemas.executions import ExecutionSchema
from app.schemas.leads import LeadSchema
from app.services import audit, pipeline
from app.workers.dispatch import dispatch_execution

APPROVER_ROLES = {"owner", "admin", "manager"}


def _assert_approver(db: Session, organization_id: UUID, user_id: UUID) -> None:
    membership = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
        )
    )
    if not membership or membership.role not in APPROVER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not authorized to approve actions",
        )


def _load_approval(
    db: Session, organization_id: UUID, approval_id: UUID
) -> tuple[Approval, Recommendation, Lead]:
    row = db.execute(
        select(Approval, Recommendation, Lead)
        .join(Recommendation, Recommendation.id == Approval.recommendation_id)
        .join(Lead, Lead.id == Recommendation.lead_id)
        .where(Approval.id == approval_id, Approval.organization_id == organization_id)
    ).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")
    return row[0], row[1], row[2]


def _detail(db: Session, approval: Approval, recommendation: Recommendation, lead: Lead) -> ApprovalDetailSchema:
    action = approval.action_payload or {}
    return ApprovalDetailSchema(
        id=approval.id,
        recommendation_id=approval.recommendation_id,
        status=approval.status,
        approved_by=approval.approved_by,
        approved_at=approval.approved_at,
        expires_at=approval.expires_at,
        action_hash=approval.action_hash,
        risk_level=str(action.get("risk") or "medium"),
        note=approval.note,
        reason=approval.reason,
        lead=LeadSchema.model_validate(pipeline.decorate_lead(lead)),
        recommendation=RecommendationSchema.model_validate(recommendation),
    )


def list_approvals(db: Session, organization_id: UUID) -> list[ApprovalDetailSchema]:
    rows = db.execute(
        select(Approval, Recommendation, Lead)
        .join(Recommendation, Recommendation.id == Approval.recommendation_id)
        .join(Lead, Lead.id == Recommendation.lead_id)
        .where(Approval.organization_id == organization_id)
        .order_by(Approval.created_at.desc())
    ).all()
    return [_detail(db, approval, recommendation, lead) for approval, recommendation, lead in rows]


def approve(
    db: Session,
    organization_id: UUID,
    user_id: UUID,
    approval_id: UUID,
    payload: ApprovalActionRequest,
) -> ExecutionSchema:
    approval, recommendation, lead = _load_approval(db, organization_id, approval_id)
    _assert_approver(db, organization_id, user_id)

    if approval.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval is no longer pending")
    if as_utc(approval.expires_at) <= utcnow():
        approval.status = "expired"
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval has expired")

    current_hash = approval.action_hash
    if payload.expected_hash and payload.expected_hash != current_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Proposed action changed before approval",
        )

    action: dict[str, Any] = dict(approval.action_payload or {})
    if payload.edited_payload is not None:
        edited = payload.edited_payload
        if not isinstance(edited.get("type"), str) or not edited.get("type"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Action type is required")
        if str(edited.get("lead_id") or "") != str(lead.id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Edited action must target the same lead",
            )
        if edited.get("external_id") and edited.get("external_id") != action.get("external_id"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Edited action must target the same external record",
            )
        action = edited
        new_hash = action_hash(action)
        approval.action_payload = action
        approval.action_hash = new_hash
        recommendation.proposed_action = action
    else:
        new_hash = current_hash

    provider = str(action.get("provider") or "hubspot")
    integration = db.scalar(
        select(Integration).where(
            Integration.organization_id == organization_id,
            Integration.provider == provider,
        )
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No connected integration for provider {provider}",
        )
    if integration.connection_status != "connected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Integration {provider} is not connected",
        )

    approval.status = "approved"
    approval.approved_by = user_id
    approval.approved_at = utcnow()
    approval.note = payload.note
    recommendation.status = "approved"

    idempotency_key = f"approval:{approval.id}:{new_hash}"
    existing = db.scalar(
        select(ActionExecution).where(ActionExecution.idempotency_key == idempotency_key)
    )
    if existing:
        db.commit()
        return ExecutionSchema.model_validate(existing)

    execution = ActionExecution(
        organization_id=organization_id,
        task_id=recommendation.task_id,
        recommendation_id=recommendation.id,
        approval_id=approval.id,
        integration_id=integration.id,
        action_type=str(action.get("type") or "unknown"),
        idempotency_key=idempotency_key,
        request_payload=action,
        status="pending",
        created_at=utcnow(),
    )
    db.add(execution)
    db.flush()
    audit.log_event(
        db,
        organization_id,
        user_id,
        "approval.granted",
        "approval",
        approval.id,
        {"action_type": execution.action_type, "idempotency_key": idempotency_key},
    )
    db.commit()
    db.refresh(execution)
    dispatch_execution(execution.id)
    db.refresh(execution)
    return ExecutionSchema.model_validate(execution)


def reject(
    db: Session,
    organization_id: UUID,
    user_id: UUID,
    approval_id: UUID,
    payload: ApprovalRejectRequest,
) -> ApprovalDetailSchema:
    approval, recommendation, lead = _load_approval(db, organization_id, approval_id)
    _assert_approver(db, organization_id, user_id)
    if approval.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval is no longer pending")
    approval.status = "rejected"
    approval.reason = payload.reason
    approval.approved_by = user_id
    approval.approved_at = utcnow()
    recommendation.status = "rejected"
    audit.log_event(
        db,
        organization_id,
        user_id,
        "approval.rejected",
        "approval",
        approval.id,
        {"reason": payload.reason},
    )
    db.commit()
    db.refresh(approval)
    return _detail(db, approval, recommendation, lead)
