from typing import Any
from urllib.parse import urlencode

from app.core.config import settings
from app.integrations.base import CredentialError
from app.integrations.http import request_json

SCOPES = {
    "hubspot": "crm.objects.contacts.read crm.objects.deals.read tasks.write",
    "gmail": "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.compose",
    "google_sheets": "https://www.googleapis.com/auth/spreadsheets",
}
AUTHORIZE_URLS = {
    "hubspot": "https://app.hubspot.com/oauth/authorize",
    "gmail": "https://accounts.google.com/o/oauth2/v2/auth",
    "google_sheets": "https://accounts.google.com/o/oauth2/v2/auth",
}
TOKEN_URLS = {
    "hubspot": "https://api.hubapi.com/oauth/v1/token",
    "gmail": "https://oauth2.googleapis.com/token",
    "google_sheets": "https://oauth2.googleapis.com/token",
}


def _config(provider: str) -> dict[str, str] | None:
    prefix = provider.upper()
    client_id = getattr(settings, f"{prefix.lower()}_client_id", None)
    client_secret = getattr(settings, f"{prefix.lower()}_client_secret", None)
    redirect_uri = getattr(settings, f"{prefix.lower()}_redirect_uri", None)
    if not (client_id and client_secret and redirect_uri):
        return None
    return {
        "client_id": str(client_id),
        "client_secret": str(client_secret),
        "redirect_uri": str(redirect_uri),
        "authorize_url": AUTHORIZE_URLS[provider],
        "token_url": TOKEN_URLS[provider],
        "scope": SCOPES[provider],
    }


def provider_mode(provider: str) -> str:
    if settings.integration_mode == "mock":
        return "mock"
    if settings.integration_mode == "live":
        return "live"
    return "live" if _config(provider) else "mock"


def require_config(provider: str) -> dict[str, str]:
    config = _config(provider)
    if config is None:
        raise CredentialError(f"Live OAuth is not configured for {provider}")
    return config


def authorization_url(provider: str, state: str, redirect_uri: str | None = None) -> str:
    config = require_config(provider)
    params: dict[str, str] = {
        "client_id": config["client_id"],
        "redirect_uri": redirect_uri or config["redirect_uri"],
        "scope": config["scope"],
        "state": state,
    }
    if provider in {"gmail", "google_sheets"}:
        params["response_type"] = "code"
        params["access_type"] = "offline"
        params["prompt"] = "consent"
    return f"{config['authorize_url']}?{urlencode(params)}"


def redirect_uri(provider: str) -> str:
    return require_config(provider)["redirect_uri"]


def exchange_code(provider: str, code: str, redirect_uri: str | None = None) -> dict[str, Any]:
    config = require_config(provider)
    _, payload, _ = request_json(
        "POST",
        config["token_url"],
        body={
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri or config["redirect_uri"],
        },
    )
    access_token = payload.get("access_token")
    if not access_token:
        raise CredentialError("OAuth provider did not return an access token")
    return {
        "access_token": str(access_token),
        "refresh_token": payload.get("refresh_token"),
        "token_type": str(payload.get("token_type") or "Bearer"),
        "scope": str(payload.get("scope") or config["scope"]),
        "expires_in": payload.get("expires_in"),
    }


def refresh_access_token(provider: str, refresh_token: str) -> dict[str, Any]:
    config = require_config(provider)
    _, payload, _ = request_json(
        "POST",
        config["token_url"],
        body={
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    access_token = payload.get("access_token")
    if not access_token:
        raise CredentialError("OAuth provider did not return a refreshed access token")
    return {
        "access_token": str(access_token),
        "refresh_token": payload.get("refresh_token") or refresh_token,
        "token_type": str(payload.get("token_type") or "Bearer"),
        "scope": str(payload.get("scope") or config["scope"]),
        "expires_in": payload.get("expires_in"),
    }
