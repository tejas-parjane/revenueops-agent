import base64
import hashlib
from typing import Any
from urllib.parse import quote

from app.integrations.base import NormalizedLead
from app.integrations.live_base import LiveAdapter


class LiveGmailAdapter(LiveAdapter):
    provider = "gmail"

    def fetch_leads(self, organization_id: str) -> list[NormalizedLead]:
        return []

    def _message_id(self, payload: dict[str, Any]) -> str:
        key = str(payload.get("idempotency_key") or payload.get("lead_id") or "revenueops")
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
        return f"{digest}@revenueops.agent"

    def _raw_message(self, payload: dict[str, Any]) -> str:
        subject = str(payload.get("subject") or "RevenueOps follow-up").replace("\r", " ").replace("\n", " ")
        lines = [
            f"To: {payload.get('to') or ''}",
            f"Subject: {subject}",
            f"Message-ID: <{self._message_id(payload)}>",
            "MIME-Version: 1.0",
            "Content-Type: text/plain; charset=UTF-8",
            "",
            str(payload.get("body") or ""),
        ]
        return base64.urlsafe_b64encode("\r\n".join(lines).encode("utf-8")).decode("utf-8").rstrip("=")

    def create_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._request(
            "POST",
            "https://gmail.googleapis.com/gmail/v1/users/me/drafts",
            body={"message": {"raw": self._raw_message(payload)}},
        )
        return {"id": str(result.get("id") or ""), "status": "drafted"}

    def send_email(self, payload: dict[str, Any]) -> dict[str, Any]:
        query = quote(f"rfc822msgid:{self._message_id(payload)}", safe="")
        existing = self._request(
            "GET", f"https://gmail.googleapis.com/gmail/v1/users/me/messages?q={query}"
        )
        messages = existing.get("messages") or []
        if messages:
            return {"id": str(messages[0].get("id") or ""), "status": "sent", "idempotent": True}
        result = self._request(
            "POST",
            "https://gmail.googleapis.com/gmail/v1/users/me/messages:send",
            body={"raw": self._raw_message(payload)},
        )
        return {"id": str(result.get("id") or ""), "status": "sent"}

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.create_draft(payload)

    def update_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.send_email(payload)

    def verify_action(self, action_type: str, reference: str) -> bool:
        if not reference:
            return False
        if action_type == "create_draft":
            path = f"drafts/{reference}"
        else:
            path = f"messages/{reference}"
        result = self._request("GET", f"https://gmail.googleapis.com/gmail/v1/users/me/{path}")
        return bool(result.get("id"))
