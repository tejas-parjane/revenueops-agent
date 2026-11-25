from datetime import datetime
from typing import Any

from app.agent.sanitizer import public_value, sanitize_text
from app.core.config import settings
from app.core.time import as_utc, utcnow


def _priority(deal_value: float, hours: float, stage: str | None) -> str:
    score = 0
    if deal_value >= 25000:
        score += 40
    elif deal_value >= settings.agent_high_value_threshold:
        score += 25
    else:
        score += 5
    if hours >= 96:
        score += 30
    elif hours >= settings.agent_inactivity_hours:
        score += 20
    if (stage or "").lower() in {"proposal", "negotiation", "closing"}:
        score += 20
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def find_neglected_leads(records: list[dict[str, Any]], now: datetime | None = None) -> list[dict[str, Any]]:
    current = now or utcnow()
    results: list[dict[str, Any]] = []
    for lead in records:
        last_activity = lead.get("last_activity_at")
        if last_activity is None:
            continue
        timestamp = as_utc(last_activity)
        if timestamp is None:
            continue
        hours = max((current - timestamp).total_seconds() / 3600, 0.0)
        if hours >= settings.agent_inactivity_hours:
            results.append(
                {
                    "lead_id": lead["id"],
                    "hours_inactive": round(hours, 2),
                    "deal_value": float(lead.get("deal_value") or 0),
                    "stage": public_value(lead.get("stage")),
                    "priority": _priority(
                        float(lead.get("deal_value") or 0), hours, lead.get("stage")
                    ),
                }
            )
    return results


def find_missing_activity(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "lead_id": lead["id"],
            "company": public_value(lead.get("company")),
            "name": public_value(lead.get("name")),
        }
        for lead in records
        if lead.get("last_activity_at") is None
    ]


def find_duplicate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for lead in records:
        email = str(lead.get("email") or "").strip().lower()
        if email:
            groups.setdefault(email, []).append(lead)
    return [
        {
            "email": email,
            "lead_ids": [item["id"] for item in group],
            "external_ids": [item.get("external_id") for item in group],
        }
        for email, group in groups.items()
        if len(group) >= 2
    ]


def tool_summary(records: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    return {
        "neglected_leads": find_neglected_leads(records, now),
        "missing_activity": find_missing_activity(records),
        "duplicate_records": find_duplicate_records(records),
    }


def create_action(finding: dict[str, Any], lead: dict[str, Any]) -> dict[str, Any]:
    action_type = "create_task"
    provider = lead["source"] if lead["source"] != "manual_import" else "hubspot"
    company = public_value(lead["company"])
    first_name = public_value(lead["name"]).split(" ")[0]
    owner = public_value(lead["owner"])
    external_id = lead["external_id"]
    payload: dict[str, Any] = {
        "lead_id": lead["id"],
        "external_id": external_id,
        "risk": "low",
        "business_justification": finding["description"],
    }

    if finding["type"] == "neglected_lead":
        high_value = lead["deal_value"] >= settings.agent_high_value_threshold
        if lead.get("email"):
            action_type = "send_email"
            provider = "gmail"
            payload.update(
                {
                    "type": action_type,
                    "provider": provider,
                    "to": lead["email"],
                    "subject": f"Following up on {company} opportunity",
                    "body": (
                        f"Hi {first_name},\n\nI wanted to follow up on the {public_value(lead['stage'])} "
                        f"conversation with {company}. Would you be open to a brief call this week to review "
                        f"next steps?\n\nBest,\n{owner}"
                    ),
                    "risk": "medium" if high_value else "low",
                }
            )
        else:
            payload.update(
                {
                    "type": action_type,
                    "provider": provider,
                    "title": f"Follow up with {company}",
                    "description": finding["description"],
                    "record_id": external_id,
                }
            )
    elif finding["type"] == "missing_activity_data":
        payload.update(
            {
                "type": "update_crm",
                "provider": "hubspot",
                "record_id": external_id,
                "properties": {
                    "follow_up_review_required": True,
                    "review_note": "Activity timestamp missing; verify during next pipeline review.",
                },
            }
        )
        action_type = "update_crm"
        provider = "hubspot"
    elif finding["type"] == "duplicate_records":
        payload.update(
            {
                "type": "create_task",
                "provider": "hubspot",
                "title": "Review duplicate contact records",
                "description": finding["description"],
                "record_id": external_id,
            }
        )
    else:
        payload.update(
            {
                "type": "create_task",
                "provider": "hubspot",
                "title": "Review untrusted note content",
                "description": finding["description"],
                "record_id": external_id,
            }
        )
    return payload


def safe_llm_action(template: dict[str, Any], draft: dict[str, Any]) -> dict[str, Any]:
    action = dict(template)
    action_type = str(template.get("type") or "")
    if action_type == "send_email":
        for field in ("subject", "body"):
            value = draft.get(field)
            if isinstance(value, str) and value.strip():
                action[field] = sanitize_text(value, 600 if field == "body" else 160)
    elif action_type == "create_task":
        for field in ("title", "description"):
            value = draft.get(field)
            if isinstance(value, str) and value.strip():
                action[field] = sanitize_text(value, 600 if field == "description" else 160)
    return action
