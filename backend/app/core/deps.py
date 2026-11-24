from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.entities import Organization, OrganizationMember, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    payload = decode_access_token(token)
    try:
        user_id = UUID(str(payload["sub"]))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    user = db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def get_org_context(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> tuple[Organization, User, OrganizationMember]:
    organization_id = user.active_organization_id
    membership = db.scalar(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id == organization_id,
        )
    )
    if not membership and organization_id is None:
        membership = db.scalar(
            select(OrganizationMember)
            .where(OrganizationMember.user_id == user.id)
            .order_by(OrganizationMember.created_at)
        )
        if membership:
            user.active_organization_id = membership.organization_id
            db.commit()
            db.refresh(user)
            organization_id = user.active_organization_id
    if not membership or organization_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active organization")
    organization = db.scalar(select(Organization).where(Organization.id == organization_id))
    if not organization:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization not found")
    return organization, user, membership


def require_roles(*roles: str) -> Callable:
    def checker(context: tuple[Organization, User, OrganizationMember] = Depends(get_org_context)):
        organization, user, membership = context
        if membership.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role permissions",
            )
        return organization, user, membership

    return checker
