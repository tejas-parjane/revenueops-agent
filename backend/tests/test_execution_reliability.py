from uuid import UUID

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.integrations.base import ExternalTimeoutError, RateLimitError
from app.models.entities import ActionExecution
from app.services import execution as execution_service
from tests.conftest import create_task, register


def test_rate_limit_is_retried(monkeypatch):
    monkeypatch.setattr(settings, "execution_max_retries", 3)
    monkeypatch.setattr(settings, "execution_retry_delay_seconds", 0)
    calls = 0

    def operation():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RateLimitError("slow down")
        return "ok"

    assert execution_service._with_retries(operation) == "ok"
    assert calls == 2


def test_external_timeout_is_not_retried(monkeypatch):
    monkeypatch.setattr(settings, "execution_max_retries", 3)
    monkeypatch.setattr(settings, "execution_retry_delay_seconds", 0)
    calls = 0

    def operation():
        nonlocal calls
        calls += 1
        raise ExternalTimeoutError("ambiguous write")

    with pytest.raises(ExternalTimeoutError):
        execution_service._with_retries(operation)
    assert calls == 1


def test_timeout_marks_execution_uncertain_without_repeated_adapter_call(client, monkeypatch):
    monkeypatch.setattr(settings, "execution_max_retries", 3)
    monkeypatch.setattr(settings, "execution_retry_delay_seconds", 0)
    calls = 0

    def timeout(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise ExternalTimeoutError("provider accepted the write but did not respond")

    monkeypatch.setattr(execution_service, "_call_adapter", timeout)
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
    try:
        execution = db.scalar(select(ActionExecution).where(ActionExecution.id == execution_id))
        assert execution.status == "uncertain"
        assert calls == 1
    finally:
        db.close()


def test_execution_claim_is_atomic(client):
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

    setup_db = SessionLocal()
    try:
        execution = setup_db.scalar(select(ActionExecution).where(ActionExecution.id == execution_id))
        execution.status = "pending"
        setup_db.commit()
    finally:
        setup_db.close()

    first_worker = SessionLocal()
    second_worker = SessionLocal()
    try:
        assert execution_service._claim_execution(first_worker, execution_id) is True
        assert execution_service._claim_execution(second_worker, execution_id) is False
    finally:
        first_worker.close()
        second_worker.close()
