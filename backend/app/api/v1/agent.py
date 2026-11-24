from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_org_context
from app.schemas.agent import (
    AgentEventSchema,
    AgentTaskCreate,
    AgentTaskDetailSchema,
    AgentTaskSchema,
)
from app.services import agent as agent_service

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/tasks", response_model=AgentTaskSchema, status_code=status.HTTP_202_ACCEPTED)
def create_task(
    payload: AgentTaskCreate,
    context=Depends(get_org_context),
    db: Session = Depends(get_db),
):
    organization, user, _ = context
    return AgentTaskSchema.model_validate(
        agent_service.create_task(db, organization.id, user.id, payload.user_request)
    )


@router.get("/tasks", response_model=list[AgentTaskSchema])
def list_tasks(context=Depends(get_org_context), db: Session = Depends(get_db)):
    organization, _, _ = context
    return [AgentTaskSchema.model_validate(item) for item in agent_service.list_tasks(db, organization.id)]


@router.get("/tasks/{task_id}", response_model=AgentTaskDetailSchema)
def get_task(task_id: UUID, context=Depends(get_org_context), db: Session = Depends(get_db)):
    organization, _, _ = context
    return agent_service.get_task_detail(db, organization.id, task_id)


@router.get("/tasks/{task_id}/events", response_model=list[AgentEventSchema])
def get_events(task_id: UUID, context=Depends(get_org_context), db: Session = Depends(get_db)):
    organization, _, _ = context
    return agent_service.get_events(db, organization.id, task_id)
