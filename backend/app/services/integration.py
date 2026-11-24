import base64
import hashlib
import hmac
import time
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.encryption import decrypt_credentials, encrypt_credentials
from app.integrations.base import CredentialError, IntegrationError
from app.integrations.registry import PROVIDER_METADATA, get_adapter
from app.models.entities import Integration
from app.schemas.integrations import ConnectResponse, IntegrationSchema
from app.services import audit, pipeline


def _state(provider: str) -> str:
    issued = str(int(time.time()))
    message = f"{provider}:{issued}".encode()
    signature = hmac.new(settings.jwt_secret_key.encode("utf-8"), message, hashlib.sha256).hexdigest()[:24]
    return base64.urlsafe_b64encode(f"{provider}:{issued}:{signature}".encode()).decode("utf-8")


def _verify_state(state: str, provider: str) -> None:
    try:
        decoded = base64.urlsafe_b64decode(state.encode("utf-8")).decode("utf-8")
        state_provider, issued, signature = decoded.split(":", 2)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state") from exc
    message = f"{state_provider}:{issued}".encode()
    expected = hmac.new(settings.jwt_secret_key.encode("utf-8"), message, hashlib.sha256).hexdigest()[:24]
    if not hmac.compare_digest(signature, expected) or state_provider != provider:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")
    if abs(time.time() - int(issued)) > 900:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state has expired")


def build_connect_response(provider: str) -> ConnectResponse:
    if provider not in PROVIDER_METADATA:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unsupported provider")
    state = _state(provider)
    callback_url = f"/api/v1/integrations/{provider}/callback?state={state}"
    return ConnectResponse(
        authorization_url=f"/api/v1/integrations/{provider}/connect",
        state=state,
        callback_url=callback_url,
    )


def list_integrations(db: Session, organization_id: UUID) -> list[IntegrationSchema]:
    rows = db.scalars(
        select(Integration)
        .where(Integration.organization_id == organization_id)
        .order_by(Integration.provider)
    ).all()
    return [IntegrationSchema.model_validate(row) for row in rows]


def complete_connection(
    db: Session,
    organization_id: UUID,
    user_id: UUID,
    provider: str,
    state: str,
    external_account_id: str,
) -> IntegrationSchema:
    if provider not in PROVIDER_METADATA:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unsupported provider")
    _verify_state(state, provider)
    credentials: dict[str, Any] = {
        "mock": True,
        "connected_at": datetime.utcnow().isoformat(),
        "external_account_id": external_account_id,
    }
    integration = db.scalar(
        select(Integration).where(
            Integration.organization_id == organization_id,
            Integration.provider == provider,
            Integration.external_account_id == external_account_id,
        )
    )
    if integration:
        integration.encrypted_credentials = encrypt_credentials(credentials)
        integration.connection_status = "connected"
        integration.last_error = None
        integration.updated_at = datetime.utcnow()
    else:
        integration = Integration(
            organization_id=organization_id,
            provider=provider,
            external_account_id=external_account_id,
            encrypted_credentials=encrypt_credentials(credentials),
            connection_status="connected",
            permissions=PROVIDER_METADATA[provider]["permissions"],
        )
        db.add(integration)
        db.flush()
    audit.log_event(
        db,
        organization_id,
        user_id,
        "integration.connected",
        "integration",
        integration.id,
        {"provider": provider},
    )
    db.commit()
    db.refresh(integration)
    return IntegrationSchema.model_validate(integration)


def disconnect_integration(
    db: Session, organization_id: UUID, user_id: UUID, integration_id: UUID
) -> None:
    integration = db.scalar(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.organization_id == organization_id,
        )
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    integration.connection_status = "disconnected"
    integration.encrypted_credentials = encrypt_credentials({"mock": True, "disconnected": True})
    integration.last_error = None
    integration.updated_at = datetime.utcnow()
    audit.log_event(
        db,
        organization_id,
        user_id,
        "integration.disconnected",
        "integration",
        integration.id,
        {"provider": integration.provider},
    )
    db.commit()


def sync_integration(db: Session, integration: Integration, user_id: UUID | None = None) -> IntegrationSchema:
    if integration.connection_status in {"disconnected", "expired"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Integration is {integration.connection_status}",
        )
    try:
        credentials = decrypt_credentials(integration.encrypted_credentials)
        adapter = get_adapter(integration.provider, credentials)
        adapter.check_connection()
        rows = adapter.fetch_leads(str(integration.organization_id))
        for row in rows:
            pipeline.upsert_lead(db, integration.organization_id, integration.id, row)
        integration.connection_status = "connected"
        integration.last_synced_at = datetime.utcnow()
        integration.last_error = None
        integration.updated_at = datetime.utcnow()
        audit.log_event(
            db,
            integration.organization_id,
            user_id,
            "integration.synced",
            "integration",
            integration.id,
            {"provider": integration.provider, "records": len(rows)},
        )
        db.commit()
    except (CredentialError, ValueError) as exc:
        integration.connection_status = "expired"
        integration.last_error = str(exc)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrationError as exc:
        integration.connection_status = "error"
        integration.last_error = str(exc)
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    db.refresh(integration)
    return IntegrationSchema.model_validate(integration)
