import secrets
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Organization, OrganizationInvitation, OrganizationMember, User
from app.schemas.organizations import InvitationCreate, InvitationSchema, MemberSchema
from app.services import audit


def create_organization_for_user(db: Session, user: User, name: str) -> Organization:
    organization = Organization(name=name.strip())
    db.add(organization)
    db.flush()
    db.add(
        OrganizationMember(
            organization_id=organization.id,
            user_id=user.id,
            role="owner",
        )
    )
    user.active_organization_id = organization.id
    audit.log_event(
        db,
        organization.id,
        user.id,
        "organization.created",
        "organization",
        organization.id,
        {"name": organization.name},
    )
    db.commit()
    db.refresh(organization)
    return organization


def get_members(db: Session, organization_id: UUID) -> list[MemberSchema]:
    rows = db.execute(
        select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == organization_id)
        .order_by(OrganizationMember.created_at)
    ).all()
    return [
        MemberSchema(
            id=member.id,
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=member.role,
            created_at=member.created_at,
        )
        for member, user in rows
    ]


def create_invitation(
    db: Session,
    organization: Organization,
    user_id: UUID,
    payload: InvitationCreate,
) -> InvitationSchema:
    email = payload.email.lower().strip()
    existing = db.scalar(
        select(OrganizationInvitation).where(
            OrganizationInvitation.organization_id == organization.id,
            OrganizationInvitation.email == email,
            OrganizationInvitation.status == "pending",
        )
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invitation already pending")

    invitation = OrganizationInvitation(
        organization_id=organization.id,
        email=email,
        role=payload.role,
        token=secrets.token_urlsafe(24),
        status="pending",
    )
    db.add(invitation)
    audit.log_event(
        db,
        organization.id,
        user_id,
        "invitation.created",
        "invitation",
        metadata={"email": email, "role": payload.role},
    )
    db.commit()
    db.refresh(invitation)
    return InvitationSchema.model_validate(invitation)


def switch_organization(db: Session, user: User, organization_id: UUID) -> Organization:
    membership = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id == organization_id,
        )
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    organization = db.scalar(select(Organization).where(Organization.id == organization_id))
    if not organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    user.active_organization_id = organization.id
    db.commit()
    db.refresh(user)
    return organization
