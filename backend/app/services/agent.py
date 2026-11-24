from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.graph import build_graph
from app.agent.state import AgentState
from app.db.session import SessionLocal
from app.models.entities import AgentTask, AgentTaskEvent, Recommendation
from app.schemas.agent import (
    AgentEventSchema,
    AgentTaskDetailSchema,
    FindingSchema,
    RecommendationSchema,
)
from app.services import audit
from app.workers.dispatch import dispatch_agent_task


def create_task(db: Session, organization_id: UUID, user_id: UUID, user_request: str) -> AgentTask:
    task = AgentTask(
        organization_id=organization_id,
        initiated_by=user_id,
        user_request=user_request,
        task_type="pipeline_investigation",
        status="pending",
        intent=None,
        input_data={"request": user_request},
        created_at=datetime.utcnow(),
    )
    db.add(task)
    db.flush()
    db.add(
        AgentTaskEvent(
            organization_id=organization_id,
            task_id=task.id,
            step="queued",
            status="pending",
            message="Agent task queued for investigation.",
            event_metadata={},
            created_at=datetime.utcnow(),
        )
    )
    audit.log_event(
        db,
        organization_id,
        user_id,
        "agent_task.created",
        "agent_task",
        task.id,
        {"user_request": user_request},
    )
    db.commit()
    db.refresh(task)
    dispatch_agent_task(task.id)
    db.refresh(task)
    return task


def get_task(db: Session, organization_id: UUID, task_id: UUID) -> AgentTask:
    task = db.scalar(
        select(AgentTask).where(
            AgentTask.id == task_id,
            AgentTask.organization_id == organization_id,
        )
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent task not found")
    return task


def list_tasks(db: Session, organization_id: UUID) -> list[AgentTask]:
    return list(
        db.scalars(
            select(AgentTask)
            .where(AgentTask.organization_id == organization_id)
            .order_by(AgentTask.created_at.desc())
        ).all()
    )


def get_events(db: Session, organization_id: UUID, task_id: UUID) -> list[AgentEventSchema]:
    get_task(db, organization_id, task_id)
    events = db.scalars(
        select(AgentTaskEvent)
        .where(
            AgentTaskEvent.task_id == task_id,
            AgentTaskEvent.organization_id == organization_id,
        )
        .order_by(AgentTaskEvent.created_at)
    ).all()
    return [
        AgentEventSchema(
            id=event.id,
            step=event.step,
            status=event.status,
            message=event.message,
            metadata=event.event_metadata,
            created_at=event.created_at,
        )
        for event in events
    ]


def get_task_detail(db: Session, organization_id: UUID, task_id: UUID) -> AgentTaskDetailSchema:
    task = get_task(db, organization_id, task_id)
    recommendations = list(
        db.scalars(
            select(Recommendation)
            .where(
                Recommendation.task_id == task_id,
                Recommendation.organization_id == organization_id,
            )
            .order_by(Recommendation.created_at)
        ).all()
    )
    result: dict[str, Any] = task.result or {}
    findings = [
        FindingSchema(
            id=item.id,
            lead_id=item.lead_id,
            type=item.finding_type,
            priority=item.priority,
            title=item.title,
            description=item.explanation,
            evidence=item.evidence,
            created_at=item.created_at,
        )
        for item in recommendations
    ]
    return AgentTaskDetailSchema(
        id=task.id,
        organization_id=task.organization_id,
        initiated_by=task.initiated_by,
        user_request=task.user_request,
        task_type=task.task_type,
        status=task.status,
        intent=task.intent,
        error=task.error,
        created_at=task.created_at,
        completed_at=task.completed_at,
        reasoning_summary=result.get("reasoning_summary"),
        data_sources=result.get("data_sources", []),
        result=result,
        findings=findings,
        recommendations=[RecommendationSchema.model_validate(item) for item in recommendations],
        events=get_events(db, organization_id, task_id),
    )


def run_task_sync(task_id: str) -> None:
    db = SessionLocal()
    try:
        task = db.scalar(select(AgentTask).where(AgentTask.id == UUID(task_id)))
        if not task or task.status in {"completed", "failed", "running"}:
            return
        task.status = "running"
        db.commit()
        state: AgentState = {
            "db": db,
            "organization_id": task.organization_id,
            "user_id": task.initiated_by,
            "task_id": task.id,
            "user_request": task.user_request,
            "events": [],
            "records": [],
            "findings": [],
            "recommendations": [],
            "data_sources": [],
        }
        build_graph().invoke(state)
        db.commit()
    except Exception as exc:
        db.rollback()
        task = db.scalar(select(AgentTask).where(AgentTask.id == UUID(task_id)))
        if task:
            task.status = "failed"
            task.error = str(exc)
            task.completed_at = datetime.utcnow()
            db.add(
                AgentTaskEvent(
                    organization_id=task.organization_id,
                    task_id=task.id,
                    step="error",
                    status="failed",
                    message="Agent task failed.",
                    event_metadata={"error": str(exc)},
                    created_at=datetime.utcnow(),
                )
            )
            db.commit()
    finally:
        db.close()
