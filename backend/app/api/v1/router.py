from fastapi import APIRouter

from app.api.v1 import (
    agent,
    approvals,
    auth,
    dashboard,
    executions,
    integrations,
    leads,
    organizations,
)

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(organizations.router)
router.include_router(integrations.router)
router.include_router(leads.router)
router.include_router(agent.router)
router.include_router(approvals.router)
router.include_router(executions.router)
router.include_router(dashboard.router)
