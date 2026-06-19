"""LiteLLM gateway data types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class LlmEndpoint:
    """One LiteLLM completion target in the provider chain."""

    provider: str
    model: str
    api_key: str | None
    api_base: str | None = None


@dataclass(frozen=True, slots=True)
class LlmUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True, slots=True)
class LlmCompletionResult:
    """Outcome of a gateway completion (live or cache)."""

    response: Any
    endpoint: LlmEndpoint
    purpose: str
    cached: bool = False
    fallback_index: int = 0
    cost_usd: float | None = None
    usage: LlmUsage | None = None


class LlmGatewayError(RuntimeError):
    """Base gateway failure."""


class LlmGuardrailError(LlmGatewayError):
    """Input or output failed gateway guardrails."""


class LlmRateLimitError(LlmGatewayError):
    """Gateway rate budget exceeded."""
