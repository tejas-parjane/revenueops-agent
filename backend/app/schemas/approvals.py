from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.agent import RecommendationSchema
from app.schemas.auth import ORMModel
from app.schemas.leads import LeadSchema


class ApprovalActionRequest(BaseModel):
    edited_payload: dict[str, Any] | None = None
    expected_hash: str | None = None
    note: str | None = Field(default=None, max_length=1000)


class ApprovalRejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class ApprovalDetailSchema(ORMModel):
    id: UUID
    recommendation_id: UUID
    status: str
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    expires_at: datetime
    action_hash: str
    risk_level: str = "medium"
    note: str | None = None
    reason: str | None = None
    lead: LeadSchema
    recommendation: RecommendationSchema
