from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET = "change-me-in-production"
_DEFAULT_DATABASE_URL = "postgresql+psycopg://lms:lms@localhost:5432/lms"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_debug: bool = False
    app_secret_key: str = _DEFAULT_SECRET

    database_url: str = _DEFAULT_DATABASE_URL

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
    # Primary provider: groq | openai | anthropic | together | huggingface
    llm_provider: str = "groq"
    # Optional chain, e.g. groq,openai or groq:model-id,together:model-id
    llm_providers: str = ""
    max_tokens: int | None = None
    temperature: float | None = None
    groq_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    together_api_key: str | None = None
    azure_api_key: str | None = None
    azure_api_base: str | None = None
    llm_model: str = "llama-3.3-70b-versatile"
    llm_model_fast: str = "llama-3.1-8b-instant"
    llm_fallback_enabled: bool = True
    hf_token: str | None = None
    llm_fallback_model: str = "Qwen/Qwen2.5-72B-Instruct"
    llm_fallback_provider: str = "together"
    agent_max_tool_calls_per_turn: int = 5
    # LiteLLM gateway (src/lms/shared/llm/)
    llm_cache_enabled: bool = True
    llm_cache_ttl_seconds: int = 600
    llm_rate_limit_enabled: bool = True
    llm_rate_limit_max: int = 120
    llm_rate_limit_window_seconds: int = 60
    llm_max_prompt_chars: int = 12000
    llm_max_tokens_cap: int = 4096
    llm_proxy_url: str | None = None
    llm_proxy_api_key: str | None = None
    llm_cache_type: str = "local"
    llm_cache_redis_url: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = Field(
        default="https://cloud.langfuse.com",
        validation_alias=AliasChoices("LANGFUSE_HOST", "LANGFUSE_BASE_URL"),
 
    )

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def has_llm_provider_key(self) -> bool:
        """True when at least one hosted LLM provider API key is configured."""
        return any(
            key
            for key in (
                self.groq_api_key,
                self.openai_api_key,
                self.anthropic_api_key,
                self.together_api_key,
                self.hf_token,
                self.azure_api_key,
            )
        )

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
        if self.database_url == _DEFAULT_DATABASE_URL:
            raise ValueError("DATABASE_URL must not use default dev credentials in production")
        if self.agent_issue_enabled:
            if self.agent_mock_llm:
                raise ValueError(
                    "AGENT_MOCK_LLM must be false when AGENT_ISSUE_ENABLED in production"
                )
            if not self.has_llm_provider_key():
                raise ValueError(
                    "At least one LLM provider API key is required when the agent is "
                    "enabled in production"
                )
            if not self.langfuse_public_key or not self.langfuse_secret_key:
                raise ValueError(
                    "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are required when the "
                    "agent is enabled in production"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
