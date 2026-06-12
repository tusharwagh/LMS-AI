from __future__ import annotations

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET = "change-me-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_debug: bool = False
    app_secret_key: str = _DEFAULT_SECRET

    database_url: str = "postgresql+psycopg://lms:lms@localhost:5432/lms"

    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 480

    library_timezone: str = "Asia/Kolkata"

    cors_origins: str = "*"

    # Security hardening (see .cursor/rules/security-and-hardening.md)
    security_hsts_enabled: bool = False
    rate_limit_enabled: bool = True
    auth_rate_limit_max: int = 10
    auth_rate_limit_window_seconds: int = 900
    api_rate_limit_max: int = 100
    api_rate_limit_window_seconds: int = 900

    # Phase 8 — agent desk (MVP.md §2.2, ADR-025–028)
    agent_issue_enabled: bool = False
    agent_mock_llm: bool = True
    groq_api_key: str | None = None
    llm_model: str = "llama-3.3-70b-versatile"
    llm_model_fast: str = "llama-3.1-8b-instant"
    llm_fallback_enabled: bool = False
    hf_token: str | None = None
    llm_fallback_model: str = "Qwen/Qwen2.5-72B-Instruct"
    llm_fallback_provider: str = "together"
    agent_max_tool_calls_per_turn: int = 5
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def validate_production_security(self) -> Settings:
        if not self.is_production:
            return self
        if self.app_secret_key == _DEFAULT_SECRET:
            raise ValueError("APP_SECRET_KEY must be changed in production")
        if self.cors_origins.strip() == "*":
            raise ValueError("CORS_ORIGINS must list explicit origins in production (not *)")
        if self.app_debug:
            raise ValueError("APP_DEBUG must be false in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
