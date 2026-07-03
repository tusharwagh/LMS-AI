"""LiteLLM gateway — Router routing, fallbacks, cache, guardrails, spend tracking."""

from __future__ import annotations

from typing import Any

import structlog
from litellm_gateway import LlmGateway as _PlatformLlmGateway

from lms.config import Settings
from lms.shared.llm.models import LlmCompletionResult, LlmEndpoint
from lms.shared.llm.nemo_guardrails import (
    NemoGuardrailsChecker,
    apply_output_content,
)
from lms.shared.llm.routing import RouterConfig
from lms.shared.llm.setup import configure_litellm

logger = structlog.get_logger(__name__)


class LlmGateway:
    """Central LiteLLM gateway for hosted completions (ADR-028)."""

    def __init__(
        self,
        settings: Settings,
        *,
        inner: _PlatformLlmGateway | None = None,
        router: Any | None = None,
        router_config: RouterConfig | None = None,
    ) -> None:
        self._settings = settings
        self._nemo_guardrails = NemoGuardrailsChecker.from_settings(settings)
        if inner is not None:
            self._inner = inner
        else:
            self._inner = _PlatformLlmGateway(
                settings.to_llm_gateway_settings(),
                router=router,
                router_config=router_config,
            )

    @classmethod
    def from_settings(cls, settings: Settings) -> LlmGateway:
        configure_litellm(settings)
        inner = _PlatformLlmGateway.from_settings(settings.to_llm_gateway_settings())
        return cls(settings, inner=inner)

    @property
    def _router(self) -> Any | None:
        return self._inner._router

    @_router.setter
    def _router(self, value: Any | None) -> None:
        self._inner._router = value

    def complete(
        self,
        *,
        messages: list[dict[str, str]],
        max_tokens: int = 256,
        temperature: float = 0,
        purpose: str = "completion",
        use_cache: bool = True,
        session_id: str | None = None,
        operator_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LlmCompletionResult:
        """Run guardrails, Router completion (or proxy pass-through), cost tracking."""
        self._nemo_guardrails.validate_input(messages, purpose=purpose)

        result = self._inner.complete(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            purpose=purpose,
            use_cache=use_cache,
            session_id=session_id,
            operator_id=operator_id,
            metadata=metadata,
        )

        assistant_content = result.response.choices[0].message.content or ""
        validated_content = self._nemo_guardrails.validate_output(
            messages,
            assistant_content,
            purpose=purpose,
        )
        if validated_content != assistant_content:
            apply_output_content(result.response, validated_content)

        usage = result.usage
        logger.info(
            "llm_completion_ok",
            purpose=purpose,
            provider=result.endpoint.provider,
            model=result.endpoint.model,
            fallback_index=result.fallback_index,
            cached=result.cached,
            cost_usd=result.cost_usd,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            proxy=bool(self._settings.llm_proxy_url),
            nemo_guardrails=self._nemo_guardrails.enabled,
        )
        return result


def completion_with_fallback(
    settings: Settings,
    *,
    messages: list[dict[str, str]],
    max_tokens: int = 256,
    temperature: float = 0,
    purpose: str = "intent_parse",
) -> tuple[Any, LlmEndpoint]:
    """Backward-compatible helper returning (response, endpoint)."""
    result = LlmGateway.from_settings(settings).complete(
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        purpose=purpose,
    )
    return result.response, result.endpoint
