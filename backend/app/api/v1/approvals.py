from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.models.entities import Organization, OrganizationMember, User
from app.schemas.approvals import (
    ApprovalActionRequest,
    ApprovalDetailSchema,
    ApprovalRejectRequest,
)
from app.schemas.executions import ExecutionSchema
from app.services import approval as approval_service

router = APIRouter(prefix="/approvals", tags=["approvals"])
APPROVER = require_roles("owner", "admin", "manager")


@router.get("", response_model=list[ApprovalDetailSchema])
def list_approvals(context=Depends(APPROVER), db: Session = Depends(get_db)):
    organization, _, _ = context
    return approval_service.list_approvals(db, organization.id)


@router.post("/{approval_id}/approve", response_model=ExecutionSchema)
def approve(
    approval_id: UUID,
    payload: ApprovalActionRequest,
    context: tuple[Organization, User, OrganizationMember] = Depends(APPROVER),
    db: Session = Depends(get_db),
):
    organization, user, _ = context
    return approval_service.approve(db, organization.id, user.id, approval_id, payload)


@router.post("/{approval_id}/reject", response_model=ApprovalDetailSchema)
def reject(
    approval_id: UUID,
    payload: ApprovalRejectRequest,
    context: tuple[Organization, User, OrganizationMember] = Depends(APPROVER),
    db: Session = Depends(get_db),
):
    organization, user, _ = context
    return approval_service.reject(db, organization.id, user.id, approval_id, payload)
