from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.auth import ORMModel


class LeadImportRow(BaseModel):
    external_id: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None
    company: str | None = None
    deal_value: float = Field(default=0.0, ge=0)
    stage: str | None = None
    owner: str | None = None
    last_activity_at: datetime | None = None
    notes: str | None = None


class LeadImportRequest(BaseModel):
    integration_id: UUID | None = None
    rows: list[LeadImportRow] = Field(min_length=1)


class LeadSchema(ORMModel):
    id: UUID
    external_id: str
    name: str
    email: EmailStr | None = None
    company: str | None = None
    deal_value: float
    stage: str | None = None
    owner: str | None = None
    last_activity_at: datetime | None = None
    days_inactive: float | None = None
    priority: str | None = None
    notes: str | None = None
    source_provider: str | None = None
    created_at: datetime
    updated_at: datetime


class LeadImportResult(BaseModel):
    imported: int
    updated: int
    leads: list[LeadSchema]
