from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router
from app.core.config import settings
from app.core.logging import RequestContextMiddleware, configure_logging
from app.db.base import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_create_tables or settings.environment == "test":
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="RevenueOps Agent API",
    version="1.0.0",
    description="Evidence-backed revenue operations investigation and approved action execution.",
    lifespan=lifespan,
)

configure_logging(settings.log_level)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "environment": settings.environment}
