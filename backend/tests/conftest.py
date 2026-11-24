import os
from pathlib import Path
from uuid import UUID, uuid4

os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./revenueops_test.db"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret"
os.environ["TOKEN_ENCRYPTION_KEY"] = "test-encryption-key"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["EXECUTION_RETRY_DELAY_SECONDS"] = "0"
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["CORS_ORIGINS"] = "http://localhost:5173"
os.environ["LOG_LEVEL"] = "WARNING"

Path("revenueops_test.db").unlink(missing_ok=True)

import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine, get_db
from app.main import app
from app.models.entities import OrganizationMember, User

Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def reset_database():
    yield
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def client():
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def register(client: TestClient, email: str | None = None):
    email = email or f"user-{uuid4().hex[:10]}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Test Manager",
            "organization_name": f"Org {uuid4().hex[:6]}",
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    return payload, {"Authorization": f"Bearer {payload['access_token']}"}


def create_task(client: TestClient, headers: dict[str, str], request: str | None = None) -> dict:
    response = client.post(
        "/api/v1/agent/tasks",
        headers=headers,
        json={"user_request": request or "Find all high-value leads that haven't received a follow-up in 48 hours."},
    )
    assert response.status_code == 202, response.text
    return response.json()


def add_member(client: TestClient, headers: dict[str, str], role: str = "member") -> tuple[dict, dict[str, str]]:
    org = client.get("/api/v1/organizations/current", headers=headers).json()
    organization_id = UUID(org["id"])
    email = f"member-{uuid4().hex[:10]}@example.com"
    db = SessionLocal()
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        full_name="Test Member",
        active_organization_id=organization_id,
    )
    db.add(user)
    db.flush()
    db.add(OrganizationMember(organization_id=organization_id, user_id=user.id, role=role))
    db.commit()
    db.close()
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["user"]["id"] == str(user.id) or payload["user"]["email"] == email
    return payload, {"Authorization": f"Bearer {payload['access_token']}"}
