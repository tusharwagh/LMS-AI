"""Optional Langfuse spans and structured audit for agent desk (G13)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import structlog

from lms.config import Settings

logger = structlog.get_logger(__name__)


class AgentTracing:
    """Structured audit logging; Langfuse spans when keys are configured."""

    def __init__(self, settings: Settings) -> None:
        self._client: Any | None = None
        if settings.langfuse_public_key and settings.langfuse_secret_key:
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    base_url=settings.langfuse_host,
                )
            except (ImportError, OSError, ValueError) as exc:
                logger.warning("langfuse_client_init_failed", error=str(exc))

    def flush(self) -> None:
        """Push buffered Langfuse events (no-op when client is disabled)."""
        if self._client is None:
            return
        try:
            self._client.flush()
        except (OSError, ValueError, RuntimeError) as exc:
            logger.warning("langfuse_flush_failed", error=str(exc))

    def auth_ok(self) -> bool:
        """Return True when Langfuse credentials authenticate (for ops validation)."""
        if self._client is None:
            return False
        try:
            self._client.auth_check()
            return True
        except (OSError, ValueError, RuntimeError):
            return False

    @contextmanager
    def tool_span(
        self,
        *,
        tool_name: str,
        session_id: str,
        operator_id: str,
        agent_id: str,
    ) -> Iterator[None]:
        logger.info(
            "agent_tool_call",
            tool=tool_name,
            session_id=session_id,
            operator_id=operator_id,
            agent_id=agent_id,
        )
        if self._client is None:
            yield
            return
        try:
            with self._client.start_as_current_observation(
                name=f"tool:{tool_name}",
                as_type="tool",
                metadata={
                    "session_id": session_id,
                    "operator_id": operator_id,
                    "agent_id": agent_id,
                },
            ):
                yield
        except (ImportError, OSError, ValueError, RuntimeError) as exc:
            logger.warning("langfuse_tool_span_failed", tool=tool_name, error=str(exc))
            yield

    @contextmanager
    def turn_span(
        self,
        *,
        session_id: str,
        operator_id: str,
        agent_id: str,
        action: str,
    ) -> Iterator[None]:
        logger.info(
            "agent_turn",
            session_id=session_id,
            operator_id=operator_id,
            agent_id=agent_id,
            action=action,
        )
        if self._client is None:
            yield
            return
        try:
            with self._client.start_as_current_observation(
                name=f"turn:{action}",
                as_type="agent",
                metadata={
                    "session_id": session_id,
                    "operator_id": operator_id,
                    "agent_id": agent_id,
                },
            ):
                yield
        except (ImportError, OSError, ValueError, RuntimeError) as exc:
            logger.warning("langfuse_turn_span_failed", action=action, error=str(exc))
            yield
        finally:
            self.flush()
