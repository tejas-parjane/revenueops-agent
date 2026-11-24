from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.auth import ORMModel


class AgentTaskCreate(BaseModel):
    user_request: str = Field(min_length=3, max_length=2000)


class PipelineInvestigateRequest(BaseModel):
    request: str | None = None


class AgentEventSchema(ORMModel):
    id: UUID
    step: str
    status: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class FindingSchema(ORMModel):
    id: UUID
    lead_id: UUID
    type: str
    priority: str
    title: str
    description: str
    evidence: list[dict[str, Any]] | dict[str, Any]
    created_at: datetime


class RecommendationSchema(ORMModel):
    id: UUID
    task_id: UUID
    lead_id: UUID
    priority: str
    finding_type: str
    title: str
    explanation: str
    evidence: list[dict[str, Any]] | dict[str, Any]
    proposed_action: dict[str, Any]
    status: str
    created_at: datetime


class AgentTaskSchema(ORMModel):
    id: UUID
    organization_id: UUID
    initiated_by: UUID
    user_request: str
    task_type: str
    status: str
    intent: str | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class AgentTaskDetailSchema(AgentTaskSchema):
    reasoning_summary: str | None = None
    data_sources: list[str] = Field(default_factory=list)
    result: dict[str, Any] | None = None
    findings: list[FindingSchema] = Field(default_factory=list)
    recommendations: list[RecommendationSchema] = Field(default_factory=list)
    events: list[AgentEventSchema] = Field(default_factory=list)
