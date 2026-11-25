from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_org_context
from app.schemas.dashboard import ActivityItem, OverviewResponse, PipelineRiskSchema
from app.services import dashboard as dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=OverviewResponse)
def overview(context=Depends(get_org_context), db: Session = Depends(get_db)):
    organization, _, _ = context
    return dashboard_service.get_overview(db, organization.id)


@router.get("/pipeline-risks", response_model=list[PipelineRiskSchema])
def pipeline_risks(context=Depends(get_org_context), db: Session = Depends(get_db)):
    organization, _, _ = context
    return dashboard_service.get_pipeline_risks(db, organization.id)


@router.get("/activity", response_model=list[ActivityItem])
def activity(context=Depends(get_org_context), db: Session = Depends(get_db)):
    organization, _, _ = context
    return dashboard_service.build_activity(db, organization.id)
