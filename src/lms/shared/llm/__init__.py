"""LiteLLM gateway — multi-provider routing, fallbacks, cache, guardrails, cost."""

from lms.shared.llm.gateway import LlmGateway, completion_with_fallback
from lms.shared.llm.models import (
    LlmCompletionResult,
    LlmEndpoint,
    LlmGatewayError,
    LlmGuardrailError,
    LlmRateLimitError,
    LlmUsage,
)
from lms.shared.llm.routing import (
    RouterConfig,
    build_router_config,
    iter_llm_endpoints,
    litellm_model_id,
    llm_live_enabled,
)

__all__ = [
    "LlmCompletionResult",
    "LlmEndpoint",
    "LlmGateway",
    "LlmGatewayError",
    "LlmGuardrailError",
    "LlmRateLimitError",
    "LlmUsage",
    "RouterConfig",
    "build_router_config",
    "completion_with_fallback",
    "iter_llm_endpoints",
    "litellm_model_id",
    "llm_live_enabled",
]
