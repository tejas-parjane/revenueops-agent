from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class NormalizedLead:
    external_id: str
    name: str
    email: str | None
    company: str | None
    deal_value: float
    stage: str | None
    owner: str | None
    last_activity_at: datetime | None
    notes: str | None
    raw_data: dict[str, Any]


class IntegrationError(Exception):
    pass


class CredentialError(IntegrationError):
    pass


class RateLimitError(IntegrationError):
    pass


class ExternalTimeoutError(IntegrationError):
    pass


class ExternalAPIError(IntegrationError):
    pass


class BaseIntegrationAdapter(ABC):
    provider: str

    def __init__(self, credentials: dict[str, Any] | None = None):
        self.credentials = credentials or {}

    def check_connection(self) -> bool:
        if self.credentials.get("expired"):
            raise CredentialError(f"{self.provider} credentials have expired")
        return True

    @abstractmethod
    def fetch_leads(self, organization_id: str) -> list[NormalizedLead]:
        raise NotImplementedError

    @abstractmethod
    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def update_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def verify_action(self, action_type: str, reference: str) -> bool:
        raise NotImplementedError
