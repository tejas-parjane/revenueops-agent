from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

SUPPORTED_PROVIDERS = {"hubspot", "gmail", "google_sheets"}
SUPPORTED_ACTION_TYPES = {"send_email", "create_task", "update_crm"}


class ActionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: Literal["send_email", "create_task", "update_crm"]
    provider: Literal["hubspot", "gmail", "google_sheets"]
    lead_id: UUID
    external_id: str | None = Field(default=None, max_length=255)
    record_id: str | None = Field(default=None, max_length=255)
    to: EmailStr | None = None
    subject: str | None = Field(default=None, max_length=200)
    body: str | None = Field(default=None, max_length=4000)
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    properties: dict[str, str | bool | int | float | None] | None = None
    risk: Literal["low", "medium", "high"] = "medium"
    business_justification: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_action_specific_fields(self) -> "ActionPayload":
        if self.type == "send_email" and not (self.to and self.subject and self.body):
            raise ValueError("send_email actions require to, subject, and body")
        if self.type == "create_task" and not self.title:
            raise ValueError("create_task actions require a title")
        if self.type == "update_crm" and not self.properties:
            raise ValueError("update_crm actions require properties")
        if self.type == "send_email" and self.provider != "gmail":
            raise ValueError("send_email actions must use gmail")
        if self.type == "update_crm" and self.provider != "hubspot":
            raise ValueError("update_crm actions must use hubspot")
        return self


def validate_action_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload or not isinstance(payload, dict):
        raise ValueError("Action payload must be an object")
    data = ActionPayload.model_validate(payload).model_dump(exclude_none=True)
    if "lead_id" in data:
        data["lead_id"] = str(data["lead_id"])
    if data.get("type") not in SUPPORTED_ACTION_TYPES or data.get("provider") not in SUPPORTED_PROVIDERS:
        raise ValueError("Unsupported action type or provider")
    return data


def assert_action_targets_lead(
    action: dict[str, Any],
    lead_id: Any,
    email: str | None,
    external_id: str | None,
) -> None:
    if str(action.get("lead_id") or "") != str(lead_id):
        raise ValueError("Action must target the approval's lead")
    if action.get("external_id") and str(action["external_id"]) != str(external_id):
        raise ValueError("Action must target the source record")
    if action.get("record_id") and str(action["record_id"]) != str(external_id):
        raise ValueError("Action must target the source record")
    if action.get("to") and email and str(action["to"]).lower() != str(email).lower():
        raise ValueError("Email recipient must match the approved lead")
