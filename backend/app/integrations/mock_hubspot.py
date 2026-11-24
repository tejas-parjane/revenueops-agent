from datetime import datetime, timedelta
from typing import Any, ClassVar
from uuid import uuid4

from app.integrations.base import BaseIntegrationAdapter, NormalizedLead


class MockHubSpotAdapter(BaseIntegrationAdapter):
    provider = "hubspot"
    tasks: ClassVar[dict[str, dict[str, Any]]] = {}
    updates: ClassVar[dict[str, dict[str, Any]]] = {}

    def fetch_leads(self, organization_id: str) -> list[NormalizedLead]:
        self.check_connection()
        now = datetime.utcnow()
        fixtures = [
            {
                "external_id": "hubspot-acme-001",
                "name": "Dana Whitfield",
                "email": "dana@acme.example",
                "company": "Acme Corp",
                "deal_value": 52000.0,
                "stage": "Proposal",
                "owner": "Maya Chen",
                "hours_inactive": 76,
                "notes": "Requested a updated pricing proposal and a follow-up call.",
            },
            {
                "external_id": "hubspot-globex-002",
                "name": "Ravi Patel",
                "email": "ravi@globex.example",
                "company": "Globex",
                "deal_value": 34000.0,
                "stage": "Discovery",
                "owner": "Maya Chen",
                "hours_inactive": 6,
                "notes": "Recent discovery call completed; proposal due next week.",
            },
            {
                "external_id": "hubspot-initech-003",
                "name": "Sam Okafor",
                "email": "sam@initech.example",
                "company": "Initech",
                "deal_value": 2400.0,
                "stage": "Qualified",
                "owner": "Leo Brooks",
                "hours_inactive": 120,
                "notes": "Waiting on budget confirmation.",
            },
            {
                "external_id": "hubspot-soylent-004",
                "name": "Nina Alvarez",
                "email": "nina@soylent.example",
                "company": "Soylent",
                "deal_value": 18500.0,
                "stage": "Negotiation",
                "owner": "Maya Chen",
                "hours_inactive": None,
                "notes": "",
            },
            {
                "external_id": "hubspot-umbrella-005",
                "name": "Tom Reyes",
                "email": "tom@umbrella.example",
                "company": "Umbrella",
                "deal_value": 28000.0,
                "stage": "Proposal",
                "owner": "Leo Brooks",
                "hours_inactive": 96,
                "notes": "Multiple stakeholders are reviewing the proposal.",
            },
            {
                "external_id": "hubspot-umbrella-006",
                "name": "Thomas Reyes",
                "email": "tom@umbrella.example",
                "company": "Umbrella",
                "deal_value": 28000.0,
                "stage": "Proposal",
                "owner": "Leo Brooks",
                "hours_inactive": 91,
                "notes": "Duplicate CRM record from a list import.",
            },
        ]
        leads: list[NormalizedLead] = []
        for item in fixtures:
            hours = item.pop("hours_inactive")
            leads.append(
                NormalizedLead(
                    external_id=item["external_id"],
                    name=item["name"],
                    email=item["email"],
                    company=item["company"],
                    deal_value=float(item["deal_value"]),
                    stage=item["stage"],
                    owner=item["owner"],
                    last_activity_at=now - timedelta(hours=hours) if hours is not None else None,
                    notes=item["notes"],
                    raw_data={"fixture": item["external_id"], "organization_id": organization_id},
                )
            )
        return leads

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.check_connection()
        idempotency_key = payload.get("idempotency_key")
        if idempotency_key:
            for task_id, task in self.tasks.items():
                if task.get("idempotency_key") == idempotency_key:
                    return {"id": task_id, "status": "created", "idempotent": True, "portal_id": "mock-portal"}
        task_id = f"hubspot-task-{uuid4().hex}"
        self.tasks[task_id] = {"id": task_id, **payload}
        return {"id": task_id, "status": "created", "portal_id": "mock-portal"}

    def update_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.check_connection()
        idempotency_key = payload.get("idempotency_key")
        if idempotency_key:
            for record_id, record in self.updates.items():
                if record.get("idempotency_key") == idempotency_key:
                    return {"id": record_id, "status": "updated", "idempotent": True}
        record_id = str(payload.get("record_id") or uuid4().hex)
        self.updates[record_id] = {"id": record_id, **payload}
        return {"id": record_id, "status": "updated"}

    def verify_action(self, action_type: str, reference: str) -> bool:
        if action_type in {"create_task", "send_email_record"}:
            return reference in self.tasks
        if action_type == "update_crm":
            return reference in self.updates
        return False
