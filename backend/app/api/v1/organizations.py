from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_org_context, require_roles
from app.models.entities import Organization, OrganizationMember, User
from app.schemas.auth import OrganizationSchema
from app.schemas.organizations import InvitationCreate, InvitationSchema, MemberSchema
from app.services import organization as organization_service

router = APIRouter(prefix="/organizations", tags=["organizations"])


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


@router.post("", response_model=OrganizationSchema, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    context: tuple[Organization, User, OrganizationMember] = Depends(
        require_roles("owner", "admin")
    ),
    db: Session = Depends(get_db),
):
    _, user, _ = context
    return organization_service.create_organization_for_user(db, user, payload.name)


@router.get("/current", response_model=OrganizationSchema)
def current_organization(context=Depends(get_org_context)):
    organization, _, _ = context
    return OrganizationSchema.model_validate(organization)


@router.get("/members", response_model=list[MemberSchema])
def members(
    context=Depends(get_org_context),
    db: Session = Depends(get_db),
):
    organization, _, _ = context
    return organization_service.get_members(db, organization.id)


@router.post("/invitations", response_model=InvitationSchema, status_code=status.HTTP_201_CREATED)
def create_invitation(
    payload: InvitationCreate,
    context: tuple[Organization, User, OrganizationMember] = Depends(
        require_roles("owner", "admin")
    ),
    db: Session = Depends(get_db),
):
    organization, user, _ = context
    return organization_service.create_invitation(db, organization, user.id, payload)
