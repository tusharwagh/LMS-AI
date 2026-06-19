"""Input guardrails before LiteLLM provider calls."""

from __future__ import annotations

from lms.config import Settings
from lms.shared.llm.models import LlmGuardrailError

_ALLOWED_ROLES = frozenset({"system", "user", "assistant"})


def validate_completion_request(
    settings: Settings,
    *,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> None:
    if not messages:
        raise LlmGuardrailError("At least one message is required")

    total_chars = 0
    for index, message in enumerate(messages):
        role = message.get("role")
        if role not in _ALLOWED_ROLES:
            raise LlmGuardrailError(f"Unsupported message role at index {index}: {role!r}")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LlmGuardrailError(f"Message content at index {index} must be non-empty text")
        total_chars += len(content)

    if total_chars > settings.llm_max_prompt_chars:
        raise LlmGuardrailError(
            f"Prompt exceeds maximum length ({settings.llm_max_prompt_chars} characters)"
        )

    cap = settings.llm_max_tokens_cap
    if max_tokens < 1 or max_tokens > cap:
        raise LlmGuardrailError(f"max_tokens must be between 1 and {cap}")
