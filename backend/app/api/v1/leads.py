from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_org_context, require_roles
from app.models.entities import Organization, OrganizationMember, User
from app.schemas.agent import AgentTaskSchema, PipelineInvestigateRequest
from app.schemas.leads import LeadImportRequest, LeadImportResult, LeadSchema
from app.services import agent as agent_service
from app.services import pipeline as pipeline_service

router = APIRouter(tags=["pipeline"])


@router.get("/leads", response_model=list[LeadSchema])
def list_leads(context=Depends(get_org_context), db: Session = Depends(get_db)):
    organization, _, _ = context
    leads = pipeline_service.list_leads(db, organization.id)
    return [LeadSchema.model_validate(lead) for lead in leads]


@router.post("/leads/import", response_model=LeadImportResult, status_code=status.HTTP_201_CREATED)
def import_leads(
    payload: LeadImportRequest,
    context: tuple[Organization, User, OrganizationMember] = Depends(
        require_roles("owner", "admin", "manager")
    ),
    db: Session = Depends(get_db),
):
    organization, user, _ = context
    return pipeline_service.import_leads(db, organization.id, user.id, payload)


@router.get("/leads/{lead_id}", response_model=LeadSchema)
def get_lead(
    lead_id: UUID,
    context=Depends(get_org_context),
    db: Session = Depends(get_db),
):
    organization, _, _ = context
    return LeadSchema.model_validate(pipeline_service.get_lead(db, organization.id, lead_id))


@router.post("/pipeline/investigate", response_model=AgentTaskSchema)
def investigate(
    payload: PipelineInvestigateRequest,
    context=Depends(get_org_context),
    db: Session = Depends(get_db),
):
    organization, user, _ = context
    request = payload.request or "Find all high-value leads that haven't received a follow-up in 48 hours."
    return AgentTaskSchema.model_validate(
        agent_service.create_task(db, organization.id, user.id, request)
    )
