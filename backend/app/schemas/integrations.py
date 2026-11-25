from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.auth import ORMModel


class IntegrationSchema(ORMModel):
    id: UUID
    provider: str
    external_account_id: str
    connection_status: str
    mode: Literal["mock", "live"] = "mock"
    last_synced_at: datetime | None = None
    last_error: str | None = None
    permissions: list[str] | dict = Field(default_factory=list)
    created_at: datetime


class ConnectResponse(BaseModel):
    authorization_url: str
    state: str
    callback_url: str
    mode: Literal["mock", "live"]
