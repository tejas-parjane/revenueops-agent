from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.schemas.integrations import IntegrationSchema
from app.schemas.leads import LeadSchema


class OverviewMetrics(BaseModel):
    active_leads: int
    pipeline_value: float
    neglected_leads: int
    overdue_followups: int
    pending_approvals: int
    completed_tasks: int


class ActivityItem(BaseModel):
    id: str
    type: str
    title: str
    status: str
    actor: str
    provider: str | None = None
    timestamp: datetime
    detail: str | None = None


class OverviewResponse(BaseModel):
    metrics: OverviewMetrics
    needs_attention: list[LeadSchema]
    recent_activity: list[ActivityItem]
    high_priority: list[LeadSchema]
    integration_health: list[IntegrationSchema]


class PipelineRiskSchema(BaseModel):
    id: UUID
    lead_id: UUID
    type: str
    priority: str
    title: str
    description: str
    evidence: list[dict[str, Any]] | dict[str, Any]
    created_at: datetime
