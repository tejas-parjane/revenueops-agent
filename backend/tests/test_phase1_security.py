from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import Settings
from app.db.session import SessionLocal
from app.models.entities import ActionExecution
from tests.conftest import create_task, register


def test_production_requires_real_secrets():
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            jwt_secret_key="dev-jwt-secret-change-me",
            token_encryption_key="dev-encryption-key-change-me",
        )


def test_oauth_state_is_tenant_bound_and_single_use(client):
    _, headers = register(client)
    _, other_headers = register(client)
    connect = client.get("/api/v1/integrations/hubspot/connect", headers=headers)
    assert connect.status_code == 200, connect.text
    state = connect.json()["state"]

    wrong_org = client.get(
        f"/api/v1/integrations/hubspot/callback?state={state}&external_account_id=wrong-org",
        headers=other_headers,
    )
    assert wrong_org.status_code == 400

    callback = client.get(
        f"/api/v1/integrations/hubspot/callback?state={state}&external_account_id=owner-account",
        headers=headers,
    )
    assert callback.status_code == 200, callback.text

    replay = client.get(
        f"/api/v1/integrations/hubspot/callback?state={state}&external_account_id=owner-account",
        headers=headers,
    )
    assert replay.status_code == 400


def test_approval_edit_is_schema_validated(client):
    _, headers = register(client)
    create_task(client, headers)
    approvals = client.get("/api/v1/approvals", headers=headers).json()
    approval = next(
        item for item in approvals if item["recommendation"]["proposed_action"]["type"] == "send_email"
    )
    action = dict(approval["recommendation"]["proposed_action"])

    invalid = dict(action, to="attacker@example.com")
    response = client.post(
        f"/api/v1/approvals/{approval['id']}/approve",
        headers=headers,
        json={
            "edited_payload": invalid,
            "expected_hash": approval["action_hash"],
        },
    )
    assert response.status_code == 422, response.text

    extra_field = dict(action, internal_note="should not be accepted")
    response = client.post(
        f"/api/v1/approvals/{approval['id']}/approve",
        headers=headers,
        json={
            "edited_payload": extra_field,
            "expected_hash": approval["action_hash"],
        },
    )
    assert response.status_code == 422, response.text
    assert client.get("/api/v1/executions", headers=headers).json() == []


def test_cross_tenant_approval_and_execution_access_is_denied(client):
    _, headers_a = register(client)
    _, headers_b = register(client)
    create_task(client, headers_a)
    approval = client.get("/api/v1/approvals", headers=headers_a).json()[0]

    assert client.get("/api/v1/approvals", headers=headers_b).json() == []
    denied = client.post(
        f"/api/v1/approvals/{approval['id']}/approve",
        headers=headers_b,
        json={},
    )
    assert denied.status_code == 404

    approved = client.post(
        f"/api/v1/approvals/{approval['id']}/approve",
        headers=headers_a,
        json={"expected_hash": approval["action_hash"]},
    )
    assert approved.status_code == 200, approved.text
    execution_id = approved.json()["id"]
    assert client.get(f"/api/v1/executions/{execution_id}", headers=headers_b).status_code == 404


def test_uncertain_execution_requires_explicit_acknowledgement(client):
    _, headers = register(client)
    create_task(client, headers)
    approval = client.get("/api/v1/approvals", headers=headers).json()[0]
    approved = client.post(
        f"/api/v1/approvals/{approval['id']}/approve",
        headers=headers,
        json={"expected_hash": approval["action_hash"]},
    )
    assert approved.status_code == 200, approved.text
    execution_id = UUID(approved.json()["id"])

    db = SessionLocal()
    execution = db.scalar(select(ActionExecution).where(ActionExecution.id == execution_id))
    execution.status = "uncertain"
    execution.response_payload = {}
    db.commit()
    db.close()

    blocked = client.post(f"/api/v1/executions/{execution_id}/retry", headers=headers)
    assert blocked.status_code == 409

    retried = client.post(
        f"/api/v1/executions/{execution_id}/retry",
        headers=headers,
        json={"acknowledge_uncertain": True, "note": "Verified manually with CRM owner"},
    )
    assert retried.status_code == 200, retried.text
