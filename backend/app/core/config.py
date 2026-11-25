from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@postgres:5432/revenueops"
    jwt_secret_key: str = "dev-jwt-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    token_encryption_key: str = "dev-encryption-key-change-me"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"
    celery_task_always_eager: bool = False
    auto_create_tables: bool = False
    password_min_length: int = 8
    agent_inactivity_hours: int = 48
    agent_high_value_threshold: float = 10000.0
    approval_expiration_days: int = 7
    execution_max_retries: int = 3
    execution_retry_delay_seconds: float = 0.5
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    log_level: str = "INFO"
    integration_mode: str = "auto"
    agent_mode: str = "deterministic"
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.1
    llm_timeout_seconds: float = 20.0
    hubspot_client_id: str | None = None
    hubspot_client_secret: str | None = None
    hubspot_redirect_uri: str | None = None
    gmail_client_id: str | None = None
    gmail_client_secret: str | None = None
    gmail_redirect_uri: str | None = None
    google_sheets_client_id: str | None = None
    google_sheets_client_secret: str | None = None
    google_sheets_redirect_uri: str | None = None
    google_sheets_spreadsheet_id: str | None = None
    google_sheets_range: str = "Pipeline!A:G"

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @field_validator("integration_mode", mode="before")
    @classmethod
    def normalize_integration_mode(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized not in {"mock", "live", "auto"}:
                raise ValueError("integration_mode must be mock, live, or auto")
            return normalized
        return value

    @field_validator("agent_mode", mode="before")
    @classmethod
    def normalize_agent_mode(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized not in {"deterministic", "llm"}:
                raise ValueError("agent_mode must be deterministic or llm")
            return normalized
        return value

    @model_validator(mode="after")
    def enforce_production_secrets(self) -> "Settings":
        if self.environment.strip().lower() in {"production", "prod"}:
            if self.jwt_secret_key == "dev-jwt-secret-change-me":
                raise ValueError("JWT_SECRET_KEY must be changed in production")
            if self.token_encryption_key == "dev-encryption-key-change-me":
                raise ValueError("TOKEN_ENCRYPTION_KEY must be changed in production")
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
