from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select

from app.core.config import settings
from app.integrations.registry import provider_display_name
from app.models.entities import (
    ActionExecution,
    AgentTask,
    Approval,
    Integration,
    Lead,
    Recommendation,
    User,
)
from app.schemas.dashboard import ActivityItem, OverviewResponse, PipelineRiskSchema
from app.schemas.integrations import IntegrationSchema
from app.services import pipeline


def _user_map(db, organization_id: UUID) -> dict[str, str]:
    rows = db.scalars(
        select(User).where(User.active_organization_id == organization_id)
    ).all()
    return {str(user.id): user.full_name for user in rows}


def _integration_map(db, organization_id: UUID) -> dict[str, str]:
    rows = db.scalars(
        select(Integration).where(Integration.organization_id == organization_id)
    ).all()
    return {str(row.id): row.provider for row in rows}


def build_activity(db, organization_id: UUID, limit: int = 12) -> list[ActivityItem]:
    users = _user_map(db, organization_id)
    integrations = _integration_map(db, organization_id)
    items: list[ActivityItem] = []

    for task in db.scalars(
        select(AgentTask)
        .where(AgentTask.organization_id == organization_id)
        .order_by(AgentTask.created_at.desc())
        .limit(limit)
    ).all():
        items.append(
            ActivityItem(
                id=str(task.id),
                type="agent_task",
                title=f"Agent investigation: {task.task_type.replace('_', ' ')}",
                status=task.status,
                actor=users.get(str(task.initiated_by), "Unknown user"),
                provider="AI Agent",
                timestamp=task.created_at,
                detail=task.user_request,
            )
        )

    for approval in db.scalars(
        select(Approval)
        .where(Approval.organization_id == organization_id)
        .order_by(Approval.created_at.desc())
        .limit(limit)
    ).all():
        action = approval.action_payload or {}
        items.append(
            ActivityItem(
                id=str(approval.id),
                type="approval",
                title=f"Approval {approval.status}: {action.get('type', 'action')}",
                status=approval.status,
                actor=users.get(str(approval.approved_by), "Pending"),
                provider=provider_display_name(str(action.get("provider") or "")),
                timestamp=approval.approved_at or approval.created_at,
                detail=action.get("business_justification"),
            )
        )

    for execution in db.scalars(
        select(ActionExecution)
        .where(ActionExecution.organization_id == organization_id)
        .order_by(ActionExecution.created_at.desc())
        .limit(limit)
    ).all():
        provider = integrations.get(str(execution.integration_id))
        items.append(
            ActivityItem(
                id=str(execution.id),
                type="execution",
                title=f"Execution: {execution.action_type.replace('_', ' ')}",
                status=execution.status,
                actor="RevenueOps Agent",
                provider=provider_display_name(provider) if provider else None,
                timestamp=execution.executed_at or execution.created_at,
                detail=execution.error_message,
            )
        )

    items.sort(key=lambda item: item.timestamp, reverse=True)
    return items[:limit]


def get_overview(db, organization_id: UUID) -> OverviewResponse:
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=settings.agent_inactivity_hours)

    active_leads = int(
        db.scalar(select(func.count()).select_from(Lead).where(Lead.organization_id == organization_id)) or 0
    )
    pipeline_value = float(
        db.scalar(
            select(func.coalesce(func.sum(Lead.deal_value), 0.0)).where(
                Lead.organization_id == organization_id
            )
        )
        or 0.0
    )
    overdue_followups = int(
        db.scalar(
            select(func.count())
            .select_from(Lead)
            .where(
                Lead.organization_id == organization_id,
                Lead.last_activity_at.is_not(None),
                Lead.last_activity_at < cutoff,
            )
        )
        or 0
    )
    neglected_leads = int(
        db.scalar(
            select(func.count())
            .select_from(Lead)
            .where(
                Lead.organization_id == organization_id,
                Lead.last_activity_at.is_not(None),
                Lead.last_activity_at < cutoff,
                Lead.deal_value >= settings.agent_high_value_threshold,
            )
        )
        or 0
    )
    pending_approvals = int(
        db.scalar(
            select(func.count())
            .select_from(Approval)
            .where(
                Approval.organization_id == organization_id,
                Approval.status == "pending",
                Approval.expires_at > now,
            )
        )
        or 0
    )
    completed_tasks = int(
        db.scalar(
            select(func.count())
            .select_from(AgentTask)
            .where(
                AgentTask.organization_id == organization_id,
                AgentTask.status == "completed",
            )
        )
        or 0
    )

    attention_rows = list(
        db.scalars(
            select(Lead)
            .where(
                Lead.organization_id == organization_id,
                Lead.last_activity_at.is_not(None),
                Lead.last_activity_at < cutoff,
                Lead.deal_value >= settings.agent_high_value_threshold,
            )
            .order_by(Lead.deal_value.desc())
            .limit(5)
        ).all()
    )
    from app.services import integration as integration_service

    integration_rows: list[IntegrationSchema] = integration_service.list_integrations(db, organization_id)
    providers = {str(row.id): row.provider for row in db.scalars(
        select(Integration).where(Integration.organization_id == organization_id)
    ).all()}
    needs_attention = [
        pipeline.decorate_lead(lead, providers.get(str(lead.source_integration_id)), now)
        for lead in attention_rows
    ]

    return OverviewResponse(
        metrics={
            "active_leads": active_leads,
            "pipeline_value": pipeline_value,
            "neglected_leads": neglected_leads,
            "overdue_followups": overdue_followups,
            "pending_approvals": pending_approvals,
            "completed_tasks": completed_tasks,
        },
        needs_attention=[pipeline.LeadSchema.model_validate(lead) for lead in needs_attention],
        recent_activity=build_activity(db, organization_id),
        high_priority=[pipeline.LeadSchema.model_validate(lead) for lead in needs_attention[:3]],
        integration_health=integration_rows,
    )


def get_pipeline_risks(db, organization_id: UUID) -> list[PipelineRiskSchema]:
    rows = db.scalars(
        select(Recommendation)
        .where(
            Recommendation.organization_id == organization_id,
            Recommendation.status.in_(["proposed", "approved"]),
        )
        .order_by(Recommendation.created_at.desc())
    ).all()
    return [
        PipelineRiskSchema(
            id=row.id,
            lead_id=row.lead_id,
            type=row.finding_type,
            priority=row.priority,
            title=row.title,
            description=row.explanation,
            evidence=row.evidence,
            created_at=row.created_at,
        )
        for row in rows
    ]
