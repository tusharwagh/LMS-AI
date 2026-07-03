"""Input guardrails before LiteLLM provider calls."""

from __future__ import annotations

from litellm_gateway.guardrails import validate_completion_request as _validate

from lms.config import Settings

__all__ = ["validate_completion_request"]


def validate_completion_request(
    settings: Settings,
    *,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> None:
    _validate(
        settings.to_llm_gateway_settings(),
        messages=messages,
        max_tokens=max_tokens,
    )
