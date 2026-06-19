"""Hosted LLM routing via LiteLLM — multi-provider primary + fallback chain (ADR-028)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator

import structlog

from lms.config import Settings

logger = structlog.get_logger(__name__)

# LiteLLM provider slug → env key on Settings (extend when adding providers).
_PROVIDER_API_KEYS: dict[str, str] = {
    "groq": "groq_api_key",
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "together": "together_api_key",
    "together_ai": "together_api_key",
    "huggingface": "hf_token",
    "hf": "hf_token",
}

# Short name → LiteLLM model prefix (when model id has no `/`).
_LITELLM_PREFIX: dict[str, str] = {
    "groq": "groq",
    "openai": "openai",
    "anthropic": "anthropic",
    "together": "together_ai",
    "together_ai": "together_ai",
    "huggingface": "huggingface",
    "hf": "huggingface",
}


@dataclass(frozen=True, slots=True)
class LlmEndpoint:
    """One LiteLLM completion target."""

    provider: str
    model: str
    api_key: str | None
    api_base: str | None = None


def llm_live_enabled(settings: Settings) -> bool:
    """True when mock is off and at least one provider is configured."""
    if settings.agent_mock_llm:
        return False
    return any(_api_key_for(provider, settings) for provider, _ in _provider_specs(settings))


def litellm_model_id(provider: str, model: str) -> str:
    """Build a LiteLLM model string from provider + bare model id."""
    if "/" in model:
        return model
    prefix = _LITELLM_PREFIX.get(provider.lower())
    if prefix is None:
        raise ValueError(f"Unknown LLM provider: {provider}")
    return f"{prefix}/{model}"


def _api_key_for(provider: str, settings: Settings) -> str | None:
    key_attr = _PROVIDER_API_KEYS.get(provider.lower())
    if key_attr is None:
        return None
    return getattr(settings, key_attr, None)


def _api_base_for(provider: str, settings: Settings) -> str | None:
    if provider.lower() in {"azure", "azure_openai"}:
        return settings.azure_api_base
    return None


def _provider_specs(settings: Settings) -> list[tuple[str, str | None]]:
    """(provider_slug, optional_model_override) in try order."""
    if settings.llm_providers.strip():
        specs: list[tuple[str, str | None]] = []
        for raw in settings.llm_providers.split(","):
            piece = raw.strip()
            if not piece:
                continue
            if ":" in piece:
                prov, model = piece.split(":", 1)
                specs.append((prov.strip().lower(), model.strip()))
            else:
                specs.append((piece.lower(), None))
        return specs

    chain: list[tuple[str, str | None]] = [(settings.llm_provider.strip().lower(), None)]
    if settings.llm_fallback_enabled:
        chain.append(
            (
                settings.llm_fallback_provider.strip().lower(),
                settings.llm_fallback_model,
            )
        )
    return chain


def iter_llm_endpoints(settings: Settings) -> Iterator[LlmEndpoint]:
    """Yield configured endpoints in order (primary, then fallbacks)."""
    specs = _provider_specs(settings)
    for index, (provider, model_override) in enumerate(specs):
        api_key = _api_key_for(provider, settings)
        if not api_key:
            logger.debug("llm_provider_skipped_no_key", provider=provider)
            continue
        if model_override:
            model = model_override
        elif index == 0:
            model = settings.llm_model
        elif (
            provider == settings.llm_fallback_provider.strip().lower()
            and settings.llm_fallback_model
        ):
            model = settings.llm_fallback_model
        else:
            model = settings.llm_model
        try:
            litellm_model = litellm_model_id(provider, model)
        except ValueError:
            logger.warning("llm_provider_unknown", provider=provider)
            continue
        yield LlmEndpoint(
            provider=provider,
            model=litellm_model,
            api_key=api_key,
            api_base=_api_base_for(provider, settings),
        )


def completion_with_fallback(
    settings: Settings,
    *,
    messages: list[dict[str, str]],
    max_tokens: int = 256,
    temperature: float = 0,
) -> tuple[Any, LlmEndpoint]:
    """Call LiteLLM completion; try each configured provider in order."""
    import litellm

    endpoints = list(iter_llm_endpoints(settings))
    if not endpoints:
        raise RuntimeError(
            "No LLM provider configured — set GROQ_API_KEY, OPENAI_API_KEY, "
            "or LLM_PROVIDERS with a matching API key"
        )

    last_error: BaseException | None = None
    for endpoint in endpoints:
        kwargs: dict[str, Any] = {
            "model": endpoint.model,
            "api_key": endpoint.api_key,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if endpoint.api_base:
            kwargs["api_base"] = endpoint.api_base
        try:
            response = litellm.completion(**kwargs)
            logger.info("llm_completion_ok", provider=endpoint.provider, model=endpoint.model)
            return response, endpoint
        except Exception as exc:
            last_error = exc
            logger.warning(
                "llm_provider_failed",
                provider=endpoint.provider,
                model=endpoint.model,
                error=str(exc),
            )
    assert last_error is not None
    raise last_error
