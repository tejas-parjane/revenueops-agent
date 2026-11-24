from datetime import datetime, timedelta
from typing import Any, ClassVar
from uuid import uuid4

from app.integrations.base import BaseIntegrationAdapter, NormalizedLead


class MockGoogleSheetsAdapter(BaseIntegrationAdapter):
    provider = "google_sheets"
    rows: ClassVar[dict[str, dict[str, Any]]] = {}

    def fetch_leads(self, organization_id: str) -> list[NormalizedLead]:
        self.check_connection()
        now = datetime.utcnow()
        return [
            NormalizedLead(
                external_id="sheets-harbor-001",
                name="Ellis Grant",
                email="ellis@harbor.example",
                company="Harbor Freight",
                deal_value=12500.0,
                stage="Discovery",
                owner="Maya Chen",
                last_activity_at=now - timedelta(hours=60),
                notes="Imported from the quarterly sales tracking sheet.",
                raw_data={"sheet": "Q4 Pipeline", "row": 2, "organization_id": organization_id},
            )
        ]

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.check_connection()
        row_id = f"sheet-row-{uuid4().hex}"
        self.rows[row_id] = {"id": row_id, **payload}
        return {"id": row_id, "status": "appended"}

    def update_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.check_connection()
        row_id = str(payload.get("row_id") or uuid4().hex)
        self.rows[row_id] = {"id": row_id, **payload}
        return {"id": row_id, "status": "updated"}

    def verify_action(self, action_type: str, reference: str) -> bool:
        return reference in self.rows
