from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.auth import ORMModel


class MemberSchema(ORMModel):
    id: UUID
    user_id: UUID
    email: EmailStr
    full_name: str
    role: str
    created_at: datetime


class InvitationCreate(BaseModel):
    email: EmailStr
    role: str = Field(default="member", pattern="^(owner|admin|manager|member|viewer)$")


class InvitationSchema(ORMModel):
    id: UUID
    organization_id: UUID
    email: EmailStr
    role: str
    token: str
    status: str
    created_at: datetime
