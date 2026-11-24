from tests.conftest import create_task, register


def test_register_creates_organization_and_seeds_leads(client):
    _, headers = register(client)
    leads = client.get("/api/v1/leads", headers=headers)
    assert leads.status_code == 200
    assert len(leads.json()) >= 6
    integrations = client.get("/api/v1/integrations", headers=headers).json()
    assert {item["provider"] for item in integrations} == {"hubspot", "gmail", "google_sheets"}


def test_login_returns_token(client):
    payload, _ = register(client)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": payload["user"]["email"], "password": "password123"},
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_agent_identifies_neglected_high_value_lead_with_evidence(client):
    _, headers = register(client)
    task = create_task(client, headers)
    assert task["status"] == "completed"

    detail = client.get(f"/api/v1/agent/tasks/{task['id']}", headers=headers).json()
    assert detail["status"] == "completed"
    assert detail["data_sources"]

    neglected = [item for item in detail["findings"] if item["type"] == "neglected_lead"]
    assert neglected
    assert any(item["priority"] == "high" for item in neglected)
    assert all(item["evidence"] for item in neglected)

    emails = [
        item for item in detail["recommendations"] if item["proposed_action"]["type"] == "send_email"
    ]
    assert emails
    assert emails[0]["proposed_action"]["to"]
