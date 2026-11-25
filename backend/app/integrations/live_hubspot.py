from datetime import UTC, datetime
from typing import Any

from app.integrations.base import NormalizedLead
from app.integrations.live_base import LiveAdapter


class LiveHubSpotAdapter(LiveAdapter):
    provider = "hubspot"

    def fetch_leads(self, organization_id: str) -> list[NormalizedLead]:
        url = (
            "https://api.hubapi.com/crm/v3/objects/contacts"
            "?limit=100&properties=firstname,lastname,email,company,dealvalue,hs_lastmodifieddate,notes"
        )
        payload = self._request("GET", url)
        leads: list[NormalizedLead] = []
        for item in payload.get("results", []):
            properties = item.get("properties") or {}
            first = str(properties.get("firstname") or "")
            last = str(properties.get("lastname") or "")
            name = f"{first} {last}".strip() or str(properties.get("email") or item.get("id") or "Unknown")
            try:
                deal_value = float(properties.get("dealvalue") or 0)
            except (TypeError, ValueError):
                deal_value = 0.0
            leads.append(
                NormalizedLead(
                    external_id=str(item.get("id") or properties.get("email") or ""),
                    name=name,
                    email=properties.get("email"),
                    company=properties.get("company"),
                    deal_value=deal_value,
                    stage=properties.get("hs_deal_stage") or properties.get("stage"),
                    owner=properties.get("hubspot_owner_id"),
                    last_activity_at=self._parse_timestamp(
                        properties.get("hs_lastmodifieddate") or properties.get("lastmodifieddate")
                    ),
                    notes=properties.get("notes"),
                    raw_data={"id": item.get("id"), "properties": properties, "organization_id": organization_id},
                )
            )
        return leads

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        idempotency_key = str(payload.get("idempotency_key") or "")
        if idempotency_key:
            search = self._request(
                "POST",
                "https://api.hubapi.com/crm/v3/objects/tasks/search",
                body={
                    "filters": [
                        {
                            "propertyName": "hs_task_body",
                            "operator": "CONTAINS_TOKEN",
                            "value": idempotency_key,
                        }
                    ],
                    "properties": ["hs_task_subject", "hs_task_body"],
                    "limit": 1,
                },
            )
            existing = search.get("results") or []
            if existing:
                return {"id": str(existing[0].get("id")), "status": "created", "idempotent": True}

        description = str(
            payload.get("description") or payload.get("business_justification") or "RevenueOps follow-up"
        )
        body = f"{description}\n\nIdempotency-Key: {idempotency_key}".strip()
        task_payload: dict[str, Any] = {
            "properties": {
                "hs_task_subject": str(payload.get("title") or "RevenueOps follow-up"),
                "hs_task_body": body[:6000],
                "hs_task_status": "NOT_STARTED",
                "hs_timestamp": str(int(datetime.now(UTC).timestamp() * 1000)),
            }
        }
        record_id = str(payload.get("record_id") or "")
        if record_id:
            task_payload["associations"] = [
                {
                    "to": {"id": record_id},
                    "types": [
                        {"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 204}
                    ],
                }
            ]
        result = self._request("POST", "https://api.hubapi.com/crm/v3/objects/tasks", body=task_payload)
        return {"id": str(result.get("id") or ""), "status": "created", "portal_id": result.get("portalId")}

    def update_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        record_id = str(payload.get("record_id") or "")
        if not record_id:
            raise ValueError("HubSpot update requires a record_id")
        result = self._request(
            "PATCH",
            f"https://api.hubapi.com/crm/v3/objects/contacts/{record_id}",
            body={"properties": payload.get("properties") or {}},
        )
        return {"id": str(result.get("id") or record_id), "status": "updated"}

    def verify_action(self, action_type: str, reference: str) -> bool:
        if not reference:
            return False
        if action_type in {"create_task", "send_email_record"}:
            object_type = "tasks"
        elif action_type == "update_crm":
            object_type = "contacts"
        else:
            return False
        result = self._request("GET", f"https://api.hubapi.com/crm/v3/objects/{object_type}/{reference}")
        return bool(result.get("id"))
