"""Idempotent LiteLLM global setup — cache, callbacks, Langfuse, spend logging."""

from __future__ import annotations

import os
from typing import Any

import structlog

from lms.config import Settings
from lms.shared.llm.spend import LlmSpendLogger

logger = structlog.get_logger(__name__)

_CONFIGURED_FINGERPRINT: str | None = None
_SPEND_LOGGER: LlmSpendLogger | None = None


def _settings_fingerprint(settings: Settings) -> str:
    return "|".join(
        [
            str(settings.llm_cache_enabled),
            str(settings.llm_cache_type),
            str(settings.llm_cache_ttl_seconds),
            str(settings.llm_cache_redis_url or ""),
            str(settings.langfuse_public_key or ""),
            str(settings.langfuse_secret_key or ""),
            str(settings.langfuse_host or ""),
            str(settings.database_url),
        ]
    )


def configure_litellm(settings: Settings) -> None:
    """Configure LiteLLM once per process for the current settings fingerprint."""
    global _CONFIGURED_FINGERPRINT, _SPEND_LOGGER

    fingerprint = _settings_fingerprint(settings)
    if _CONFIGURED_FINGERPRINT == fingerprint:
        return

    import litellm
    from litellm.caching.caching import Cache

    litellm.suppress_debug_info = True

    if settings.llm_cache_enabled:
        cache_type = settings.llm_cache_type.strip().lower()
        cache_kwargs: dict[str, Any] = {"type": cache_type, "ttl": settings.llm_cache_ttl_seconds}
        if cache_type == "redis" and settings.llm_cache_redis_url:
            cache_kwargs["host"] = settings.llm_cache_redis_url
        litellm.cache = Cache(**cache_kwargs)
    else:
        litellm.cache = None

    _configure_langfuse(settings)
    _register_spend_logger(settings)

    _CONFIGURED_FINGERPRINT = fingerprint
    logger.debug("litellm_configured", cache_enabled=settings.llm_cache_enabled)


def _configure_langfuse(settings: Settings) -> None:
    import litellm

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return

    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    if settings.langfuse_host:
        os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)

    for callback_list in (litellm.success_callback, litellm.failure_callback):
        if "langfuse" not in callback_list:
            callback_list.append("langfuse")


def _register_spend_logger(settings: Settings) -> None:
    global _SPEND_LOGGER

    import litellm

    if _SPEND_LOGGER is None:
        _SPEND_LOGGER = LlmSpendLogger()

    if _SPEND_LOGGER not in litellm.callbacks:
        litellm.callbacks.append(_SPEND_LOGGER)
