from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_org_context, require_roles
from app.schemas.executions import ExecutionSchema
from app.services import execution as execution_service

router = APIRouter(prefix="/executions", tags=["executions"])


@router.get("", response_model=list[ExecutionSchema])
def list_executions(context=Depends(get_org_context), db: Session = Depends(get_db)):
    organization, _, _ = context
    return execution_service.list_executions(db, organization.id)


@router.get("/{execution_id}", response_model=ExecutionSchema)
def get_execution(execution_id: UUID, context=Depends(get_org_context), db: Session = Depends(get_db)):
    organization, _, _ = context
    return execution_service.get_execution(db, organization.id, execution_id)


@router.post("/{execution_id}/retry", response_model=ExecutionSchema)
def retry_execution(
    execution_id: UUID,
    context=Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
):
    organization, user, _ = context
    return execution_service.retry_execution(db, organization.id, user.id, execution_id)
