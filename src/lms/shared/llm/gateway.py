"""LiteLLM gateway — Router routing, fallbacks, cache, guardrails, spend tracking."""

from __future__ import annotations

from typing import Any

import structlog

from lms.config import Settings
from lms.shared.llm.cost import extract_cost_usd, extract_usage
from lms.shared.llm.guardrails import validate_completion_request
from lms.shared.llm.models import (
    LlmCompletionResult,
    LlmEndpoint,
    LlmGatewayError,
    LlmRateLimitError,
)
from lms.shared.llm.nemo_guardrails import (
    NemoGuardrailsChecker,
    apply_output_content,
)
from lms.shared.llm.routing import (
    RouterConfig,
    build_router_config,
    is_cached_response,
    iter_llm_endpoints,
    resolve_endpoint_from_response,
)
from lms.shared.llm.setup import configure_litellm

logger = structlog.get_logger(__name__)


class LlmGateway:
    """Central LiteLLM gateway for hosted completions (ADR-028)."""

    def __init__(
        self,
        settings: Settings,
        *,
        router: Any | None = None,
        router_config: RouterConfig | None = None,
    ) -> None:
        self._settings = settings
        self._router = router
        self._router_config = router_config
        self._nemo_guardrails = NemoGuardrailsChecker.from_settings(settings)

    @classmethod
    def from_settings(cls, settings: Settings) -> LlmGateway:
        configure_litellm(settings)
        router_config = build_router_config(settings)
        router = None
        if router_config.model_list and not settings.llm_proxy_url:
            from litellm.router import Router

            router = Router(
                model_list=router_config.model_list,
                fallbacks=router_config.fallbacks,
                num_retries=0,
                cache_responses=router_config.cache_responses,
            )
        return cls(settings, router=router, router_config=router_config)

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
        validate_completion_request(
            self._settings,
            messages=messages,
            max_tokens=max_tokens,
        )
        self._nemo_guardrails.validate_input(messages, purpose=purpose)

        router_config = self._router_config or build_router_config(self._settings)
        if not router_config.endpoints and not self._settings.llm_proxy_url:
            raise LlmGatewayError(
                "No LLM provider configured — set GROQ_API_KEY, OPENAI_API_KEY, "
                "or LLM_PROVIDERS with a matching API key"
            )

        request_metadata: dict[str, Any] = {"purpose": purpose}
        if session_id:
            request_metadata["session_id"] = session_id
        if operator_id:
            request_metadata["operator_id"] = operator_id
        if metadata:
            request_metadata.update(metadata)

        completion_kwargs: dict[str, Any] = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "metadata": request_metadata,
        }
        if not use_cache:
            completion_kwargs["caching"] = False

        try:
            if self._settings.llm_proxy_url:
                response = self._complete_via_proxy(completion_kwargs)
                endpoint = next(iter_llm_endpoints(self._settings), None)
                if endpoint is None:
                    endpoint = LlmEndpoint(
                        provider=self._settings.llm_provider,
                        model=self._settings.llm_model,
                        api_key=None,
                    )
                fallback_index = 0
            else:
                if self._router is None:
                    raise LlmGatewayError("LiteLLM Router is not configured")
                response = self._router.completion(
                    model=router_config.primary_model,
                    **completion_kwargs,
                )
                endpoint, fallback_index = resolve_endpoint_from_response(
                    response,
                    endpoints=router_config.endpoints,
                    model_names=router_config.model_names,
                )
        except Exception as exc:
            if _is_rate_limit_error(exc):
                raise LlmRateLimitError(
                    "LLM gateway rate limit exceeded — retry after the current window"
                ) from exc
            raise

        cached = is_cached_response(response)
        request_metadata["cached"] = cached
        usage = extract_usage(response)
        cost_usd = 0.0 if cached else extract_cost_usd(response)

        assistant_content = response.choices[0].message.content or ""
        validated_content = self._nemo_guardrails.validate_output(
            messages,
            assistant_content,
            purpose=purpose,
        )
        if validated_content != assistant_content:
            apply_output_content(response, validated_content)

        logger.info(
            "llm_completion_ok",
            purpose=purpose,
            provider=endpoint.provider,
            model=endpoint.model,
            fallback_index=fallback_index,
            cached=cached,
            cost_usd=cost_usd,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            proxy=bool(self._settings.llm_proxy_url),
            nemo_guardrails=self._nemo_guardrails.enabled,
        )

        return LlmCompletionResult(
            response=response,
            endpoint=endpoint,
            purpose=purpose,
            cached=cached,
            fallback_index=fallback_index,
            cost_usd=cost_usd,
            usage=usage,
        )

    def _complete_via_proxy(self, completion_kwargs: dict[str, Any]) -> Any:
        import litellm

        from lms.shared.llm.routing import litellm_model_id

        proxy_url = self._settings.llm_proxy_url
        if not proxy_url:
            raise LlmGatewayError("LLM_PROXY_URL is not configured")

        model = litellm_model_id(self._settings.llm_provider, self._settings.llm_model)
        kwargs = {
            **completion_kwargs,
            "model": model,
            "api_base": proxy_url.rstrip("/"),
        }
        if self._settings.llm_proxy_api_key:
            kwargs["api_key"] = self._settings.llm_proxy_api_key
        return litellm.completion(**kwargs)


def _is_rate_limit_error(exc: BaseException) -> bool:
    name = type(exc).__name__.lower()
    if "ratelimit" in name or "budget" in name:
        return True
    message = str(exc).lower()
    return "rate limit" in message or "rpm" in message


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
