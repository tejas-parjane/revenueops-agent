from datetime import datetime, timedelta
from typing import Any

from app.core.time import as_utc, utcnow
from app.integrations import http
from app.integrations.base import BaseIntegrationAdapter, CredentialError
from app.integrations.oauth import refresh_access_token


class LiveAdapter(BaseIntegrationAdapter):
    def check_connection(self) -> bool:
        if self.credentials.get("expired"):
            raise CredentialError(f"{self.provider} credentials have expired")
        self._access_token()
        return True

    def _token_expired(self) -> bool:
        expires_at = self.credentials.get("expires_at")
        if not expires_at:
            return False
        try:
            parsed = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        except ValueError:
            return True
        return (as_utc(parsed) or utcnow()) <= utcnow() + timedelta(seconds=30)

    def _access_token(self) -> str:
        access_token = self.credentials.get("access_token")
        if access_token and not self._token_expired():
            return str(access_token)
        refresh_token = self.credentials.get("refresh_token")
        if not refresh_token:
            raise CredentialError(f"{self.provider} credentials are missing a refresh token")
        tokens = refresh_access_token(self.provider, str(refresh_token))
        expires_in = float(tokens.get("expires_in") or 3600)
        self.credentials.update(tokens)
        self.credentials["expires_at"] = (utcnow() + timedelta(seconds=expires_in)).isoformat()
        self.credentials["mode"] = "live"
        return str(tokens["access_token"])

    def _request(
        self,
        method: str,
        url: str,
        body: dict[str, Any] | None = None,
        timeout: float = 15.0,
    ) -> Any:
        _, payload, _ = http.request_json(
            method,
            url,
            headers={"Authorization": f"Bearer {self._access_token()}"},
            body=body,
            timeout=timeout,
        )
        return payload

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        return as_utc(parsed)
