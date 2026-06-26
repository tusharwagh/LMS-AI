"""Shared test helpers."""

from __future__ import annotations

import uuid

from lms.config import Settings

# Explicit defaults so unit tests ignore developer shell / .env LLM keys.
_LLM_ISOLATION_DEFAULTS: dict[str, object] = {
    "groq_api_key": None,
    "openai_api_key": None,
    "anthropic_api_key": None,
    "together_api_key": None,
    "azure_api_key": None,
    "azure_api_base": None,
    "hf_token": None,
    "llm_providers": "",
    "llm_proxy_url": None,
    "llm_proxy_api_key": None,
    "langfuse_public_key": None,
    "langfuse_secret_key": None,
    "langfuse_host": None,
    "agent_mock_llm": False,
    "nemo_guardrails_enabled": False,
    "nemo_guardrails_config_path": "guardrails/nemoguards",
}


def isolated_settings(**overrides: object) -> Settings:
    """Build Settings without .env or ambient LLM provider configuration."""
    values = {**_LLM_ISOLATION_DEFAULTS, **overrides}
    return Settings(_env_file=None, **values)


def unique_tag(prefix: str = "") -> str:
    tag = uuid.uuid4().hex[:8]
    return f"{prefix}{tag}" if prefix else tag
