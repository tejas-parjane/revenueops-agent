from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_org_context, require_roles
from app.models.entities import Integration, Organization, OrganizationMember, User
from app.schemas.auth import OkResponse
from app.schemas.integrations import ConnectResponse, IntegrationSchema
from app.services import integration as integration_service

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("", response_model=list[IntegrationSchema])
def list_integrations(context=Depends(get_org_context), db: Session = Depends(get_db)):
    organization, _, _ = context
    return integration_service.list_integrations(db, organization.id)


@router.get("/{provider}/connect", response_model=ConnectResponse)
def connect_integration(provider: str):
    return integration_service.build_connect_response(provider)


@router.get("/{provider}/callback", response_model=IntegrationSchema)
def integration_callback(
    provider: str,
    state: str,
    external_account_id: str | None = None,
    context=Depends(get_org_context),
    db: Session = Depends(get_db),
):
    organization, user, _ = context
    account_id = external_account_id or f"mock-{provider}"
    return integration_service.complete_connection(
        db, organization.id, user.id, provider, state, account_id
    )


@router.delete("/{integration_id}", response_model=OkResponse)
def disconnect_integration(
    integration_id: UUID,
    context: tuple[Organization, User, OrganizationMember] = Depends(
        require_roles("owner", "admin", "manager")
    ),
    db: Session = Depends(get_db),
):
    organization, user, _ = context
    integration_service.disconnect_integration(db, organization.id, user.id, integration_id)
    return OkResponse(ok=True)


@router.post("/{integration_id}/sync", response_model=IntegrationSchema)
def sync_integration(
    integration_id: UUID,
    context: tuple[Organization, User, OrganizationMember] = Depends(
        require_roles("owner", "admin", "manager")
    ),
    db: Session = Depends(get_db),
):
    organization, user, _ = context
    integration = db.scalar(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.organization_id == organization.id,
        )
    )
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    return integration_service.sync_integration(db, integration, user.id)
