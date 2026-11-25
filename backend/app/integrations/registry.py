from typing import Any

from app.integrations.base import BaseIntegrationAdapter, CredentialError
from app.integrations.live_gmail import LiveGmailAdapter
from app.integrations.live_hubspot import LiveHubSpotAdapter
from app.integrations.live_sheets import LiveGoogleSheetsAdapter
from app.integrations.mock_gmail import MockGmailAdapter
from app.integrations.mock_hubspot import MockHubSpotAdapter
from app.integrations.mock_sheets import MockGoogleSheetsAdapter

PROVIDER_METADATA: dict[str, dict[str, Any]] = {
    "hubspot": {
        "display_name": "HubSpot",
        "permissions": ["crm.objects.contacts.read", "crm.objects.deals.read", "tasks.write"],
    },
    "gmail": {
        "display_name": "Gmail",
        "permissions": ["gmail.metadata.readonly", "gmail.drafts", "gmail.send"],
    },
    "google_sheets": {
        "display_name": "Google Sheets",
        "permissions": ["spreadsheets.readonly", "spreadsheets.values.update"],
    },
}

MOCK_ADAPTERS = {
    "hubspot": MockHubSpotAdapter,
    "gmail": MockGmailAdapter,
    "google_sheets": MockGoogleSheetsAdapter,
}

LIVE_ADAPTERS = {
    "hubspot": LiveHubSpotAdapter,
    "gmail": LiveGmailAdapter,
    "google_sheets": LiveGoogleSheetsAdapter,
}


def get_adapter(provider: str, credentials: dict[str, Any] | None = None) -> BaseIntegrationAdapter:
    credentials = credentials or {}
    mode = str(credentials.get("mode") or "").strip().lower()
    has_live_credentials = mode == "live" or bool(
        credentials.get("access_token") or credentials.get("refresh_token")
    )
    adapters = LIVE_ADAPTERS if has_live_credentials else MOCK_ADAPTERS
    adapter_class = adapters.get(provider)
    if adapter_class is None:
        raise CredentialError(f"Unsupported integration provider: {provider}")
    return adapter_class(credentials)


def provider_display_name(provider: str) -> str:
    return PROVIDER_METADATA.get(provider, {}).get("display_name", provider)
