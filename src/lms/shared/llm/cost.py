"""Token usage and cost extraction from LiteLLM responses."""

from __future__ import annotations

from typing import Any

import structlog

from lms.shared.llm.models import LlmUsage

logger = structlog.get_logger(__name__)


def extract_usage(response: Any) -> LlmUsage | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion = int(getattr(usage, "completion_tokens", 0) or 0)
    total = int(getattr(usage, "total_tokens", 0) or prompt + completion)
    return LlmUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=total,
    )


def extract_cost_usd(response: Any) -> float | None:
    try:
        from litellm import completion_cost

        cost = completion_cost(completion_response=response)
        if cost is None:
            return None
        return float(cost)
    except (ImportError, TypeError, ValueError, AttributeError) as exc:
        logger.debug("llm_cost_extraction_failed", error=str(exc))
        return None
