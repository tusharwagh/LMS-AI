"""Provider chain resolution and LiteLLM Router model_list construction."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import structlog

from lms.config import Settings
from lms.shared.llm.models import LlmEndpoint

logger = structlog.get_logger(__name__)

_PROVIDER_API_KEYS: dict[str, str] = {
    "groq": "groq_api_key",
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "together": "together_api_key",
    "together_ai": "together_api_key",
    "huggingface": "hf_token",
    "hf": "hf_token",
    "azure": "azure_api_key",
    "azure_openai": "azure_api_key",
}

_LITELLM_PREFIX: dict[str, str] = {
    "groq": "groq",
    "openai": "openai",
    "anthropic": "anthropic",
    "together": "together_ai",
    "together_ai": "together_ai",
    "huggingface": "huggingface",
    "hf": "huggingface",
}


def litellm_model_id(provider: str, model: str) -> str:
    """Build a LiteLLM model string from provider + bare model id."""
    if "/" in model:
        return model
    prefix = _LITELLM_PREFIX.get(provider.lower())
    if prefix is None:
        raise ValueError(f"Unknown LLM provider: {provider}")
    return f"{prefix}/{model}"


def llm_live_enabled(settings: Settings) -> bool:
    """True when mock is off and at least one provider is configured."""
    if settings.agent_mock_llm:
        return False
    return any(_api_key_for(provider, settings) for provider, _ in provider_specs(settings))


def _api_key_for(provider: str, settings: Settings) -> str | None:
    key_attr = _PROVIDER_API_KEYS.get(provider.lower())
    if key_attr is None:
        return None
    return getattr(settings, key_attr, None)


def _api_base_for(provider: str, settings: Settings) -> str | None:
    if provider.lower() in {"azure", "azure_openai"}:
        return settings.azure_api_base
    return None


def provider_specs(settings: Settings) -> list[tuple[str, str | None]]:
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
    specs = provider_specs(settings)
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


@dataclass(frozen=True, slots=True)
class RouterConfig:
    """LiteLLM Router inputs derived from Settings."""

    model_list: list[dict[str, Any]]
    primary_model: str
    model_names: tuple[str, ...]
    fallbacks: list[dict[str, list[str]]]
    endpoints: tuple[LlmEndpoint, ...]
    cache_responses: bool
    rpm: int | None


def _deployment_rpm(settings: Settings) -> int | None:
    if not settings.llm_rate_limit_enabled:
        return None
    window = max(1, settings.llm_rate_limit_window_seconds)
    return max(1, int(settings.llm_rate_limit_max * 60 / window))


def build_router_config(settings: Settings) -> RouterConfig:
    """Build model_list, primary alias, and fallbacks for litellm.Router."""
    endpoints = tuple(iter_llm_endpoints(settings))
    if not endpoints:
        return RouterConfig([], "", (), [], (), False, None)

    rpm = _deployment_rpm(settings)
    model_list: list[dict[str, Any]] = []
    model_names: list[str] = []
    for index, endpoint in enumerate(endpoints):
        name = f"lms-{endpoint.provider}-{index}"
        entry: dict[str, Any] = {
            "model_name": name,
            "litellm_params": {
                "model": endpoint.model,
                "api_key": endpoint.api_key,
            },
        }
        if endpoint.api_base:
            entry["litellm_params"]["api_base"] = endpoint.api_base
        if rpm is not None:
            entry["rpm"] = rpm
        model_list.append(entry)
        model_names.append(name)

    primary = model_names[0]
    fallbacks: list[dict[str, list[str]]] = []
    if len(model_names) > 1:
        fallbacks.append({primary: model_names[1:]})

    return RouterConfig(
        model_list=model_list,
        primary_model=primary,
        model_names=tuple(model_names),
        fallbacks=fallbacks,
        endpoints=endpoints,
        cache_responses=settings.llm_cache_enabled,
        rpm=rpm,
    )


def resolve_endpoint_from_response(
    response: Any,
    *,
    endpoints: tuple[LlmEndpoint, ...],
    model_names: tuple[str, ...],
) -> tuple[LlmEndpoint, int]:
    """Map a Router completion response back to the configured endpoint."""
    hidden = getattr(response, "_hidden_params", None) or {}
    model_id = hidden.get("model_id") if isinstance(hidden, dict) else None
    if isinstance(model_id, str) and model_id in model_names:
        index = model_names.index(model_id)
        return endpoints[index], index

    model_used = getattr(response, "model", None)
    if isinstance(model_used, str):
        for index, endpoint in enumerate(endpoints):
            if model_used == endpoint.model or model_used in endpoint.model:
                return endpoint, index

    return endpoints[0], 0


def is_cached_response(response: Any) -> bool:
    hidden = getattr(response, "_hidden_params", None) or {}
    if isinstance(hidden, dict) and (hidden.get("cache_hit") or hidden.get("cached")):
        return True
    return False
