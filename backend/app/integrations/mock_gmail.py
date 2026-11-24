from typing import Any, ClassVar
from uuid import uuid4

from app.integrations.base import BaseIntegrationAdapter, NormalizedLead


class MockGmailAdapter(BaseIntegrationAdapter):
    provider = "gmail"
    drafts: ClassVar[dict[str, dict[str, Any]]] = {}
    sent_messages: ClassVar[dict[str, dict[str, Any]]] = {}

    def fetch_leads(self, organization_id: str) -> list[NormalizedLead]:
        self.check_connection()
        return []

    def create_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.check_connection()
        draft_id = f"draft-{uuid4().hex}"
        self.drafts[draft_id] = {"id": draft_id, **payload}
        return {"id": draft_id, "status": "drafted"}

    def send_email(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.check_connection()
        idempotency_key = payload.get("idempotency_key")
        if idempotency_key:
            for message_id, message in self.sent_messages.items():
                if message.get("idempotency_key") == idempotency_key:
                    return {"id": message_id, "status": "sent", "idempotent": True}
        message_id = f"msg-{uuid4().hex}"
        self.sent_messages[message_id] = {"id": message_id, **payload}
        return {"id": message_id, "status": "sent"}

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.create_draft(payload)

    def update_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        message_id = str(payload.get("message_id") or uuid4().hex)
        if message_id in self.sent_messages:
            self.sent_messages[message_id].update(payload)
            return {"id": message_id, "status": "updated"}
        return self.send_email(payload)

    def verify_action(self, action_type: str, reference: str) -> bool:
        if action_type == "create_draft":
            return reference in self.drafts
        return reference in self.sent_messages
