from typing import Any

from app.integrations.base import BaseIntegrationAdapter, CredentialError
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

ADAPTERS = {
    "hubspot": MockHubSpotAdapter,
    "gmail": MockGmailAdapter,
    "google_sheets": MockGoogleSheetsAdapter,
}


def get_adapter(provider: str, credentials: dict[str, Any] | None = None) -> BaseIntegrationAdapter:
    adapter_class = ADAPTERS.get(provider)
    if adapter_class is None:
        raise CredentialError(f"Unsupported integration provider: {provider}")
    return adapter_class(credentials)


def provider_display_name(provider: str) -> str:
    return PROVIDER_METADATA.get(provider, {}).get("display_name", provider)
