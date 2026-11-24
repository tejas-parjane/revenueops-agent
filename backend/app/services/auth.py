from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.encryption import encrypt_credentials
from app.core.security import create_access_token, hash_password, verify_password
from app.integrations.registry import PROVIDER_METADATA
from app.models.entities import Integration, Organization, OrganizationMember, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.services import audit
from app.services import integration as integration_service


def _token_response(user: User, organization: Organization) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(str(user.id), str(user.active_organization_id)),
        token_type="bearer",
        user=user,
        organization=organization,
    )


def register_user(db: Session, payload: RegisterRequest) -> TokenResponse:
    email = payload.email.lower().strip()
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    organization = Organization(name=payload.organization_name.strip())
    db.add(organization)
    db.flush()

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        active_organization_id=organization.id,
    )
    db.add(user)
    db.flush()

    db.add(
        OrganizationMember(
            organization_id=organization.id,
            user_id=user.id,
            role="owner",
        )
    )

    for provider, metadata in PROVIDER_METADATA.items():
        db.add(
            Integration(
                organization_id=organization.id,
                provider=provider,
                external_account_id=f"mock-{provider}-{organization.id.hex[:8]}",
                encrypted_credentials=encrypt_credentials(
                    {"mock": True, "connected_at": datetime.utcnow().isoformat()}
                ),
                connection_status="connected",
                permissions=metadata["permissions"],
                last_synced_at=None,
                last_error=None,
            )
        )
    db.flush()

    audit.log_event(
        db,
        organization.id,
        user.id,
        "user.registered",
        "user",
        user.id,
        {"organization_name": organization.name},
    )
    db.commit()
    db.refresh(user)
    db.refresh(organization)

    hubspot = db.scalar(
        select(Integration).where(
            Integration.organization_id == organization.id,
            Integration.provider == "hubspot",
        )
    )
    if hubspot:
        integration_service.sync_integration(db, hubspot, user.id)

    db.refresh(user)
    db.refresh(organization)
    return _token_response(user, organization)


def login_user(db: Session, payload: LoginRequest) -> TokenResponse:
    email = payload.email.lower().strip()
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    organization = db.scalar(
        select(Organization).where(Organization.id == user.active_organization_id)
    )
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have an active organization",
        )
    return _token_response(user, organization)
