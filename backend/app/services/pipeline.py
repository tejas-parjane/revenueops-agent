from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import as_utc, utcnow
from app.integrations.base import NormalizedLead
from app.models.entities import Integration, Lead
from app.schemas.leads import LeadImportRequest, LeadImportResult, LeadSchema
from app.services import audit


def _hours_inactive(last_activity_at: datetime | None, now: datetime) -> float | None:
    current = as_utc(now)
    last = as_utc(last_activity_at)
    if current is None or last is None:
        return None
    return max((current - last).total_seconds() / 3600, 0.0)


def _priority(deal_value: float, hours_inactive: float | None) -> str:
    if hours_inactive is None:
        return "medium"
    if hours_inactive < settings.agent_inactivity_hours:
        return "normal"
    if deal_value >= settings.agent_high_value_threshold:
        return "high"
    return "low"


def decorate_lead(lead: Lead, provider: str | None = None, now: datetime | None = None) -> Lead:
    current = now or utcnow()
    hours = _hours_inactive(lead.last_activity_at, current)
    lead.days_inactive = round(hours / 24, 2) if hours is not None else None
    lead.priority = _priority(float(lead.deal_value or 0), hours)
    lead.source_provider = provider
    return lead


def _provider_map(db: Session, organization_id: UUID) -> dict[str, str]:
    rows = db.scalars(
        select(Integration).where(Integration.organization_id == organization_id)
    ).all()
    return {str(row.id): row.provider for row in rows}


def list_leads(db: Session, organization_id: UUID) -> list[Lead]:
    leaders = list(
        db.scalars(
            select(Lead)
            .where(Lead.organization_id == organization_id)
            .order_by(Lead.deal_value.desc())
        ).all()
    )
    providers = _provider_map(db, organization_id)
    now = utcnow()
    return [
        decorate_lead(lead, providers.get(str(lead.source_integration_id)), now) for lead in leaders
    ]


def get_lead(db: Session, organization_id: UUID, lead_id: UUID) -> Lead:
    lead = db.scalar(
        select(Lead).where(Lead.id == lead_id, Lead.organization_id == organization_id)
    )
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    providers = _provider_map(db, organization_id)
    return decorate_lead(lead, providers.get(str(lead.source_integration_id)))


def upsert_lead(
    db: Session,
    organization_id: UUID,
    source_integration_id: UUID | None,
    row: NormalizedLead,
) -> tuple[Lead, bool]:
    existing = db.scalar(
        select(Lead).where(
            Lead.organization_id == organization_id,
            Lead.source_integration_id == source_integration_id,
            Lead.external_id == row.external_id,
        )
    )
    if existing:
        existing.name = row.name
        existing.email = row.email
        existing.company = row.company
        existing.deal_value = row.deal_value
        existing.stage = row.stage
        existing.owner = row.owner
        existing.last_activity_at = row.last_activity_at
        existing.notes = row.notes
        existing.raw_data = row.raw_data
        existing.updated_at = utcnow()
        return existing, False

    lead = Lead(
        organization_id=organization_id,
        source_integration_id=source_integration_id,
        external_id=row.external_id,
        name=row.name,
        email=row.email,
        company=row.company,
        deal_value=row.deal_value,
        stage=row.stage,
        owner=row.owner,
        last_activity_at=row.last_activity_at,
        notes=row.notes,
        raw_data=row.raw_data,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(lead)
    return lead, True


def import_leads(
    db: Session,
    organization_id: UUID,
    user_id: UUID,
    payload: LeadImportRequest,
) -> LeadImportResult:
    integration_id = payload.integration_id
    if integration_id is None:
        integration = db.scalar(
            select(Integration).where(
                Integration.organization_id == organization_id,
                Integration.provider == "hubspot",
            )
        )
        integration_id = integration.id if integration else None
    else:
        integration = db.scalar(
            select(Integration).where(
                Integration.id == integration_id,
                Integration.organization_id == organization_id,
            )
        )
        if not integration:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    imported = 0
    updated = 0
    affected: list[Lead] = []
    for item in payload.rows:
        row = NormalizedLead(
            external_id=item.external_id,
            name=item.name,
            email=item.email,
            company=item.company,
            deal_value=item.deal_value,
            stage=item.stage,
            owner=item.owner,
            last_activity_at=item.last_activity_at,
            notes=item.notes,
            raw_data={"source": "manual_import"},
        )
        lead, created = upsert_lead(db, organization_id, integration_id, row)
        affected.append(lead)
        if created:
            imported += 1
        else:
            updated += 1

    audit.log_event(
        db,
        organization_id,
        user_id,
        "leads.imported",
        "lead",
        metadata={"imported": imported, "updated": updated},
    )
    db.commit()
    providers = _provider_map(db, organization_id)
    return LeadImportResult(
        imported=imported,
        updated=updated,
        leads=[LeadSchema.model_validate(decorate_lead(lead, providers.get(str(integration_id)))) for lead in affected],
    )
