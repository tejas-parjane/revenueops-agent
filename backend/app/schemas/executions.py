from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.auth import ORMModel


class ExecutionRetryRequest(BaseModel):
    acknowledge_uncertain: bool = False
    note: str | None = Field(default=None, max_length=1000)


class ExecutionSchema(ORMModel):
    id: UUID
    organization_id: UUID
    task_id: UUID
    recommendation_id: UUID
    integration_id: UUID
    action_type: str
    idempotency_key: str
    status: str
    request_payload: dict[str, Any]
    response_payload: dict[str, Any] | None = None
    error_message: str | None = None
    executed_at: datetime | None = None
    created_at: datetime
