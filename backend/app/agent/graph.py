from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from langgraph.graph import END, StateGraph
from sqlalchemy import func, select

from app.agent.sanitizer import contains_untrusted_instruction, public_value, sanitize_text
from app.agent.state import AgentState
from app.core.config import settings
from app.core.hashing import action_hash
from app.integrations.registry import provider_display_name
from app.models.entities import AgentTask, AgentTaskEvent, Approval, Integration, Lead, Recommendation


def emit(
    state: AgentState,
    step: str,
    status: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    event = {
        "id": str(uuid4()),
        "step": step,
        "status": status,
        "message": message,
        "metadata": metadata or {},
        "created_at": datetime.utcnow(),
    }
    events = [*state.get("events", []), event]
    db = state.get("db")
    if db is not None and state.get("task_id") and state.get("organization_id"):
        db.add(
            AgentTaskEvent(
                id=UUID(event["id"]),
                organization_id=state["organization_id"],
                task_id=state["task_id"],
                step=step,
                status=status,
                message=message,
                event_metadata=metadata or {},
                created_at=event["created_at"],
            )
        )
    return events


def classify_intent(state: AgentState) -> dict[str, Any]:
    request = state["user_request"].lower()
    if "draft" in request or "email" in request or "follow-up" in request or "follow up" in request:
        intent = "follow_up_preparation"
    elif "crm" in request and "update" in request:
        intent = "crm_update"
    elif "representative" in request or "rep " in request or "performance" in request:
        intent = "performance_analysis"
    else:
        intent = "pipeline_investigation"
    return {
        "intent": intent,
        "reasoning_summary": "Analyzed connected sales records for evidence-backed pipeline risks.",
        "events": emit(
            state,
            "intent_classifier",
            "completed",
            f"Classified request as {intent.replace('_', ' ')}.",
        ),
    }


def retrieve_context(state: AgentState) -> dict[str, Any]:
    db = state["db"]
    leads = list(
        db.scalars(
            select(Lead)
            .where(Lead.organization_id == state["organization_id"])
            .order_by(Lead.deal_value.desc())
        ).all()
    )
    integrations = db.scalars(
        select(Integration).where(Integration.organization_id == state["organization_id"])
    ).all()
    providers = {str(item.id): item.provider for item in integrations}
    records: list[dict[str, Any]] = []
    for lead in leads:
        provider = providers.get(str(lead.source_integration_id))
        records.append(
            {
                "id": str(lead.id),
                "external_id": lead.external_id,
                "name": lead.name,
                "email": lead.email,
                "company": lead.company,
                "deal_value": float(lead.deal_value or 0),
                "stage": lead.stage,
                "owner": lead.owner,
                "last_activity_at": lead.last_activity_at,
                "notes": lead.notes,
                "source": provider or "manual_import",
            }
        )
    data_sources = sorted(
        {provider_display_name(provider) for provider in providers.values()} | {"Manual import"}
    )
    return {
        "records": records,
        "data_sources": data_sources,
        "events": emit(
            state,
            "data_retrieval",
            "completed",
            f"Retrieved {len(records)} lead records from connected sources.",
            {"sources": data_sources},
        ),
    }


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


def investigate(state: AgentState) -> dict[str, Any]:
    now = datetime.utcnow()
    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add_finding(
        lead: dict[str, Any],
        finding_type: str,
        priority: str,
        title: str,
        description: str,
        evidence: list[dict[str, Any]],
    ) -> None:
        key = (finding_type, lead["id"])
        if key in seen:
            return
        seen.add(key)
        findings.append(
            {
                "id": str(uuid4()),
                "lead_id": lead["id"],
                "type": finding_type,
                "priority": priority,
                "title": title,
                "description": description,
                "evidence": evidence,
                "created_at": now.isoformat(),
            }
        )

    for lead in state.get("records", []):
        base_evidence = [
            {
                "source": lead["source"],
                "external_id": lead["external_id"],
                "name": public_value(lead["name"]),
                "company": public_value(lead["company"]),
                "deal_value": lead["deal_value"],
                "stage": public_value(lead["stage"]),
                "owner": public_value(lead["owner"]),
            }
        ]
        last_activity = lead.get("last_activity_at")
        if last_activity is None:
            add_finding(
                lead,
                "missing_activity_data",
                "medium",
                f"Activity history missing for {public_value(lead['company'])}",
                "The source record has no last-activity timestamp. Verify the CRM record before sending outreach.",
                base_evidence + [{"issue": "last_activity_at is null"}],
            )
        else:
            hours = max((now - last_activity).total_seconds() / 3600, 0.0)
            if hours >= settings.agent_inactivity_hours:
                priority = _priority(lead["deal_value"], hours, lead.get("stage"))
                add_finding(
                    lead,
                    "neglected_lead",
                    priority,
                    f"{public_value(lead['company'])} inactive for {hours:.0f} hours",
                    f"{public_value(lead['name'])} has no qualifying follow-up in the last "
                    f"{settings.agent_inactivity_hours} hours. Deal value is ${lead['deal_value']:,.0f}.",
                    base_evidence
                    + [
                        {
                            "hours_inactive": round(hours, 2),
                            "last_activity_at": last_activity.isoformat(),
                            "note_excerpt": sanitize_text(lead.get("notes")),
                        }
                    ],
                )
        if contains_untrusted_instruction(lead.get("notes")):
            add_finding(
                lead,
                "untrusted_instruction_detected",
                "medium",
                "Instruction-like text found in retrieved CRM note",
                "Retrieved content contained instruction-like text. It was treated as untrusted data and excluded from generated actions.",
                base_evidence
                + [
                    {
                        "category": "prompt_injection_candidate",
                        "note_excerpt": sanitize_text(lead.get("notes")),
                    }
                ],
            )

    by_email: dict[str, list[dict[str, Any]]] = {}
    for lead in state.get("records", []):
        email = (lead.get("email") or "").lower().strip()
        if email:
            by_email.setdefault(email, []).append(lead)
    for email, group in by_email.items():
        if len(group) < 2:
            continue
        primary = group[0]
        add_finding(
            primary,
            "duplicate_records",
            "medium",
            "Duplicate contact records detected",
            f"{len(group)} records share the same email address and should be reviewed before outreach.",
            [
                {
                    "email": email,
                    "lead_ids": [lead["id"] for lead in group],
                    "external_ids": [lead["external_id"] for lead in group],
                }
            ],
        )

    return {
        "findings": findings,
        "events": emit(
            state,
            "investigation",
            "completed",
            f"Identified {len(findings)} evidence-backed findings from {len(state.get('records', []))} records.",
        ),
    }


def _create_action(finding: dict[str, Any], lead: dict[str, Any]) -> dict[str, Any]:
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


def recommend(state: AgentState) -> dict[str, Any]:
    records = {record["id"]: record for record in state.get("records", [])}
    recommendations: list[dict[str, Any]] = []
    for finding in state.get("findings", []):
        lead = records.get(finding["lead_id"])
        if not lead:
            continue
        action = _create_action(finding, lead)
        now = datetime.utcnow()
        recommendations.append(
            {
                "id": str(uuid4()),
                "task_id": str(state["task_id"]),
                "lead_id": finding["lead_id"],
                "priority": finding["priority"],
                "finding_type": finding["type"],
                "title": finding["title"],
                "explanation": finding["description"],
                "evidence": finding["evidence"],
                "proposed_action": action,
                "status": "proposed",
                "created_at": now.isoformat(),
            }
        )
    return {
        "recommendations": recommendations,
        "events": emit(
            state,
            "recommendation",
            "completed",
            f"Prepared {len(recommendations)} recommendations for human approval.",
        ),
    }


def persist(state: AgentState) -> dict[str, Any]:
    db = state["db"]
    existing = db.scalar(
        select(func.count()).select_from(Recommendation).where(Recommendation.task_id == state["task_id"])
    )
    if not existing:
        now = datetime.utcnow()
        expires_at = now + timedelta(days=settings.approval_expiration_days)
        for item in state.get("recommendations", []):
            action = item["proposed_action"]
            recommendation = Recommendation(
                id=UUID(item["id"]),
                organization_id=state["organization_id"],
                task_id=state["task_id"],
                lead_id=UUID(item["lead_id"]),
                priority=item["priority"],
                finding_type=item["finding_type"],
                title=item["title"],
                explanation=item["explanation"],
                evidence=item["evidence"],
                proposed_action=action,
                status="proposed",
                created_at=now,
            )
            db.add(recommendation)
            db.add(
                Approval(
                    organization_id=state["organization_id"],
                    recommendation_id=recommendation.id,
                    status="pending",
                    action_payload=action,
                    action_hash=action_hash(action),
                    expires_at=expires_at,
                    created_at=now,
                )
            )
        db.flush()
    return {
        "events": emit(
            state,
            "persistence",
            "completed",
            "Stored findings, recommendations and approval requests.",
        )
    }


def finalize(state: AgentState) -> dict[str, Any]:
    db = state["db"]
    task = db.scalar(select(AgentTask).where(AgentTask.id == state["task_id"]))
    if task:
        task.status = "completed"
        task.intent = state.get("intent")
        task.completed_at = datetime.utcnow()
        task.result = {
            "reasoning_summary": state.get("reasoning_summary", ""),
            "data_sources": state.get("data_sources", []),
            "findings": [
                {
                    "id": finding["id"],
                    "type": finding["type"],
                    "priority": finding["priority"],
                    "title": finding["title"],
                }
                for finding in state.get("findings", [])
            ],
            "findings_count": len(state.get("findings", [])),
            "recommendations_count": len(state.get("recommendations", [])),
        }
    return {
        "result": task.result if task else {},
        "events": emit(state, "reporting", "completed", "Task completed successfully."),
    }


def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("classify_intent", classify_intent)
    workflow.add_node("retrieve_context", retrieve_context)
    workflow.add_node("investigate", investigate)
    workflow.add_node("recommend", recommend)
    workflow.add_node("persist", persist)
    workflow.add_node("finalize", finalize)
    workflow.set_entry_point("classify_intent")
    workflow.add_edge("classify_intent", "retrieve_context")
    workflow.add_edge("retrieve_context", "investigate")
    workflow.add_edge("investigate", "recommend")
    workflow.add_edge("recommend", "persist")
    workflow.add_edge("persist", "finalize")
    workflow.add_edge("finalize", END)
    return workflow.compile()
