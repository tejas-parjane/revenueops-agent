import hashlib
import secrets
from datetime import timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.encryption import decrypt_credentials, encrypt_credentials
from app.core.time import as_utc, utcnow
from app.integrations.base import CredentialError, IntegrationError
from app.integrations.oauth import authorization_url, exchange_code, provider_mode, redirect_uri
from app.integrations.registry import PROVIDER_METADATA, get_adapter
from app.models.entities import Integration, OAuthState
from app.schemas.integrations import ConnectResponse, IntegrationSchema
from app.services import audit, pipeline


def _state_hash(state: str) -> str:
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


def _create_state(
    db: Session,
    provider: str,
    organization_id: UUID,
    user_id: UUID,
    target_redirect_uri: str,
) -> str:
    state = secrets.token_urlsafe(32)
    db.add(
        OAuthState(
            organization_id=organization_id,
            user_id=user_id,
            provider=provider,
            state_hash=_state_hash(state),
            redirect_uri=target_redirect_uri,
            expires_at=utcnow() + timedelta(minutes=15),
        )
    )
    db.commit()
    return state


def _consume_state(
    db: Session,
    state: str,
    provider: str,
    organization_id: UUID | None = None,
    user_id: UUID | None = None,
    mock_only: bool = False,
) -> OAuthState:
    filters = [OAuthState.state_hash == _state_hash(state), OAuthState.provider == provider]
    if organization_id is not None:
        filters.append(OAuthState.organization_id == organization_id)
    if user_id is not None:
        filters.append(OAuthState.user_id == user_id)
    record = db.scalar(select(OAuthState).where(*filters).with_for_update())
    now = utcnow()
    expires_at = as_utc(record.expires_at) if record else None
    if not record or record.consumed_at is not None or expires_at is None or expires_at <= now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OAuth state")
    is_mock_state = str(record.redirect_uri).startswith("/")
    if mock_only != is_mock_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state was created for another flow")
    record.consumed_at = now
    db.commit()
    return record


def _credential_mode(integration: Integration) -> str:
    try:
        credentials = decrypt_credentials(integration.encrypted_credentials)
    except ValueError:
        return "mock"
    if credentials.get("mode") == "live" or credentials.get("access_token") or credentials.get("refresh_token"):
        return "live"
    return "mock"


def _integration_schema(integration: Integration) -> IntegrationSchema:
    data = IntegrationSchema.model_validate(integration).model_dump()
    data["mode"] = _credential_mode(integration)
    return IntegrationSchema.model_validate(data)


def build_connect_response(
    db: Session, provider: str, organization_id: UUID, user_id: UUID
) -> ConnectResponse:
    if provider not in PROVIDER_METADATA:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unsupported provider")
    mode = provider_mode(provider)
    if mode == "live":
        target_redirect_uri = redirect_uri(provider)
        state = _create_state(db, provider, organization_id, user_id, target_redirect_uri)
        return ConnectResponse(
            authorization_url=authorization_url(provider, state, target_redirect_uri),
            state=state,
            callback_url=target_redirect_uri,
            mode="live",
        )
    target_redirect_uri = f"/api/v1/integrations/{provider}/callback"
    state = _create_state(db, provider, organization_id, user_id, target_redirect_uri)
    return ConnectResponse(
        authorization_url=f"/api/v1/integrations/{provider}/connect",
        state=state,
        callback_url=f"{target_redirect_uri}?state={state}",
        mode="mock",
    )


def list_integrations(db: Session, organization_id: UUID) -> list[IntegrationSchema]:
    rows = db.scalars(
        select(Integration)
        .where(Integration.organization_id == organization_id)
        .order_by(Integration.provider)
    ).all()
    return [_integration_schema(row) for row in rows]


def _upsert_integration(
    db: Session,
    organization_id: UUID,
    provider: str,
    external_account_id: str,
    credentials: dict[str, Any],
) -> Integration:
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
        integration.updated_at = utcnow()
        return integration
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
    return integration


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
    _consume_state(db, state, provider, organization_id, user_id, mock_only=True)
    credentials: dict[str, Any] = {
        "mock": True,
        "mode": "mock",
        "connected_at": utcnow().isoformat(),
        "external_account_id": external_account_id,
    }
    integration = _upsert_integration(
        db, organization_id, provider, external_account_id, credentials
    )
    audit.log_event(
        db,
        organization_id,
        user_id,
        "integration.connected",
        "integration",
        integration.id,
        {"provider": provider, "mode": "mock"},
    )
    db.commit()
    db.refresh(integration)
    return _integration_schema(integration)


def complete_live_connection(db: Session, provider: str, state: str, code: str) -> IntegrationSchema:
    if provider not in PROVIDER_METADATA:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unsupported provider")
    oauth_state = _consume_state(db, state, provider, mock_only=False)
    try:
        tokens = exchange_code(provider, code, oauth_state.redirect_uri)
    except CredentialError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except IntegrationError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    expires_in = float(tokens.pop("expires_in", 0) or 0)
    credentials: dict[str, Any] = {
        "mode": "live",
        "connected_at": utcnow().isoformat(),
        "expires_at": (utcnow() + timedelta(seconds=expires_in or 3600)).isoformat(),
        **tokens,
    }
    external_account_id = f"oauth-{provider}-{oauth_state.state_hash[:12]}"
    integration = _upsert_integration(
        db, oauth_state.organization_id, provider, external_account_id, credentials
    )
    audit.log_event(
        db,
        oauth_state.organization_id,
        oauth_state.user_id,
        "integration.connected",
        "integration",
        integration.id,
        {"provider": provider, "mode": "live"},
    )
    db.commit()
    db.refresh(integration)
    return _integration_schema(integration)


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
    integration.encrypted_credentials = encrypt_credentials(
        {"mock": True, "mode": "mock", "disconnected": True}
    )
    integration.last_error = None
    integration.updated_at = utcnow()
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
        if adapter.credentials != credentials:
            integration.encrypted_credentials = encrypt_credentials(adapter.credentials)
        for row in rows:
            pipeline.upsert_lead(db, integration.organization_id, integration.id, row)
        integration.connection_status = "connected"
        integration.last_synced_at = utcnow()
        integration.last_error = None
        integration.updated_at = utcnow()
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
    return _integration_schema(integration)
