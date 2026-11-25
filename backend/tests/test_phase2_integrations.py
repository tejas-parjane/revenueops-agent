from app.core.config import settings
from app.integrations import http
from app.integrations.live_gmail import LiveGmailAdapter
from app.integrations.live_hubspot import LiveHubSpotAdapter
from app.integrations.mock_hubspot import MockHubSpotAdapter
from app.integrations.registry import get_adapter
from app.services import integration as integration_service
from tests.conftest import register


def test_live_connect_uses_provider_authorization_url(client, monkeypatch):
    monkeypatch.setattr(settings, "hubspot_client_id", "hubspot-client")
    monkeypatch.setattr(settings, "hubspot_client_secret", "hubspot-secret")
    monkeypatch.setattr(
        settings,
        "hubspot_redirect_uri",
        "https://revenueops-api-8iwn.onrender.com/api/v1/integrations/hubspot/oauth/callback",
    )
    _, headers = register(client)

    response = client.get("/api/v1/integrations/hubspot/connect", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["mode"] == "live"
    assert "app.hubspot.com/oauth/authorize" in payload["authorization_url"]
    assert payload["state"] in payload["authorization_url"]

    wrong_flow = client.get(
        f"/api/v1/integrations/hubspot/callback?state={payload['state']}&external_account_id=mock-account",
        headers=headers,
    )
    assert wrong_flow.status_code == 400


def test_live_oauth_callback_is_single_use(client, monkeypatch):
    monkeypatch.setattr(settings, "hubspot_client_id", "hubspot-client")
    monkeypatch.setattr(settings, "hubspot_client_secret", "hubspot-secret")
    monkeypatch.setattr(
        settings,
        "hubspot_redirect_uri",
        "https://revenueops-api-8iwn.onrender.com/api/v1/integrations/hubspot/oauth/callback",
    )
    monkeypatch.setattr(
        integration_service,
        "exchange_code",
        lambda provider, code, redirect_uri: {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_in": 3600,
            "scope": "crm.objects.contacts.read",
        },
    )
    _, headers = register(client)
    connect = client.get("/api/v1/integrations/hubspot/connect", headers=headers).json()

    callback = client.get(
        f"/api/v1/integrations/hubspot/oauth/callback?state={connect['state']}&code=authorization-code"
    )
    assert callback.status_code == 200, callback.text
    assert callback.json()["mode"] == "live"
    assert callback.json()["external_account_id"].startswith("oauth-hubspot-")

    integrations = client.get("/api/v1/integrations", headers=headers).json()
    assert any(item["mode"] == "live" for item in integrations)

    replay = client.get(
        f"/api/v1/integrations/hubspot/oauth/callback?state={connect['state']}&code=authorization-code"
    )
    assert replay.status_code == 400


def test_registry_selects_mock_or_live_adapter():
    assert isinstance(get_adapter("hubspot", {"mode": "mock"}), MockHubSpotAdapter)
    assert isinstance(
        get_adapter("hubspot", {"mode": "live", "access_token": "token"}),
        LiveHubSpotAdapter,
    )


def test_live_hubspot_maps_external_leads(client, monkeypatch):
    def fake_request_json(method, url, headers=None, body=None, timeout=15.0):
        assert method == "GET"
        assert "crm/v3/objects/contacts" in url
        return 200, {
            "results": [
                {
                    "id": "101",
                    "properties": {
                        "firstname": "Dana",
                        "lastname": "Reed",
                        "email": "dana@example.com",
                        "company": "Northwind",
                        "dealvalue": "12500.50",
                        "hs_lastmodifieddate": "2026-11-20T10:00:00Z",
                    },
                }
            ]
        }, {}

    monkeypatch.setattr(http, "request_json", fake_request_json)
    adapter = LiveHubSpotAdapter({"mode": "live", "access_token": "token"})
    leads = adapter.fetch_leads("organization-id")

    assert len(leads) == 1
    assert leads[0].external_id == "101"
    assert leads[0].name == "Dana Reed"
    assert leads[0].deal_value == 12500.5
    assert leads[0].last_activity_at is not None


def test_live_gmail_send_is_idempotent(client, monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_request_json(method, url, headers=None, body=None, timeout=15.0):
        calls.append((method, url))
        if method == "GET":
            return 200, {"messages": [{"id": "existing-message"}]}, {}
        raise AssertionError("send should not be called when a message already exists")

    monkeypatch.setattr(http, "request_json", fake_request_json)
    result = LiveGmailAdapter({"mode": "live", "access_token": "token"}).send_email(
        {"to": "dana@example.com", "subject": "Follow-up", "body": "Hello"}
    )

    assert result["idempotent"] is True
    assert result["id"] == "existing-message"
    assert calls[0][0] == "GET"
