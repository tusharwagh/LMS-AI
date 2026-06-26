"""NeMo Guardrails input/output checks around LiteLLM completions."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from lms.config import Settings
from lms.shared.llm.models import LlmGatewayError, LlmGuardrailError

if TYPE_CHECKING:
    from nemoguardrails import LLMRails

logger = structlog.get_logger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _resolve_config_path(config_path: str) -> Path:
    path = Path(config_path)
    if not path.is_absolute():
        path = _PROJECT_ROOT / path
    return path.resolve()


@lru_cache(maxsize=4)
def _load_llm_rails(config_path: str) -> LLMRails:
    try:
        from nemoguardrails import LLMRails, RailsConfig
    except ImportError as exc:
        raise LlmGatewayError(
            "NEMO_GUARDRAILS_ENABLED=true but nemoguardrails is not installed. "
            "Install with: pip install 'lms-ai[guardrails]'"
        ) from exc

    path = _resolve_config_path(config_path)
    if not path.is_dir():
        raise LlmGatewayError(f"NeMo Guardrails config directory not found: {path}")

    config = RailsConfig.from_path(str(path))
    return LLMRails(config)


def _last_user_message(messages: list[dict[str, str]]) -> dict[str, str] | None:
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return {"role": "user", "content": content}
    return None


class NemoGuardrailsChecker:
    """Runs NeMo input/output rails without replacing the LiteLLM provider call."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._rails: LLMRails | None = None
        if not settings.nemo_guardrails_enabled:
            return

        resolved = _resolve_config_path(settings.nemo_guardrails_config_path)
        self._rails = _load_llm_rails(str(resolved))

    @classmethod
    def from_settings(cls, settings: Settings) -> NemoGuardrailsChecker:
        return cls(settings)

    @property
    def enabled(self) -> bool:
        return self._rails is not None

    def validate_input(
        self,
        messages: list[dict[str, str]],
        *,
        purpose: str,
    ) -> None:
        if not self.enabled:
            return

        from nemoguardrails.rails.llm.options import RailStatus, RailType

        rails = self._rails
        assert rails is not None

        user_message = _last_user_message(messages)
        if user_message is None:
            return

        result = rails.check([user_message], rail_types=[RailType.INPUT])
        if result.status == RailStatus.BLOCKED:
            logger.warning(
                "nemo_guardrails_blocked",
                phase="input",
                purpose=purpose,
                rail=result.rail,
            )
            raise LlmGuardrailError(_blocked_message("input", result.rail, result.content))
        if result.status == RailStatus.MODIFIED:
            logger.info(
                "nemo_guardrails_modified",
                phase="input",
                purpose=purpose,
            )

    def validate_output(
        self,
        messages: list[dict[str, str]],
        assistant_content: str,
        *,
        purpose: str,
    ) -> str:
        if not self.enabled:
            return assistant_content

        from nemoguardrails.rails.llm.options import RailStatus, RailType

        rails = self._rails
        assert rails is not None

        user_message = _last_user_message(messages)
        if user_message is None:
            return assistant_content

        check_messages = [
            user_message,
            {"role": "assistant", "content": assistant_content},
        ]
        result = rails.check(check_messages, rail_types=[RailType.OUTPUT])
        if result.status == RailStatus.BLOCKED:
            logger.warning(
                "nemo_guardrails_blocked",
                phase="output",
                purpose=purpose,
                rail=result.rail,
            )
            raise LlmGuardrailError(_blocked_message("output", result.rail, result.content))
        if result.status == RailStatus.MODIFIED:
            logger.info(
                "nemo_guardrails_modified",
                phase="output",
                purpose=purpose,
            )
            return str(result.content)
        return assistant_content


def _blocked_message(phase: str, rail: str | None, content: str) -> str:
    rail_name = rail or "unknown"
    snippet = content.strip().replace("\n", " ")
    if len(snippet) > 160:
        snippet = f"{snippet[:157]}..."
    return f"NeMo Guardrails blocked {phase} ({rail_name}): {snippet}"


def apply_output_content(response: Any, content: str) -> None:
    """Replace assistant text on a LiteLLM-style completion response."""
    response.choices[0].message.content = content
