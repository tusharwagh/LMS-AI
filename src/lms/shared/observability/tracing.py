"""Optional Langfuse spans and structured audit logging."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import structlog

from lms.config import Settings

logger = structlog.get_logger(__name__)


class LangfuseTracing:
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
    def _langfuse_observation(
        self,
        *,
        name: str,
        as_type: str,
        metadata: dict[str, Any],
        failure_event: str,
        **failure_context: Any,
    ) -> Iterator[None]:
        """Open a Langfuse observation when possible; always propagate body exceptions."""
        if self._client is None:
            yield
            return

        cm: Any | None = None
        try:
            cm = self._client.start_as_current_observation(
                name=name,
                as_type=as_type,
                metadata=metadata,
            )
            cm.__enter__()
        except (ImportError, OSError, ValueError, RuntimeError) as exc:
            logger.warning(failure_event, error=str(exc), **failure_context)
            cm = None

        try:
            yield
        finally:
            if cm is not None:
                try:
                    cm.__exit__(*sys.exc_info())
                except (ImportError, OSError, ValueError, RuntimeError) as exc:
                    logger.warning(failure_event, error=str(exc), **failure_context)

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
            args_redacted=True,
        )
        with self._langfuse_observation(
            name=f"tool:{tool_name}",
            as_type="tool",
            metadata={
                "session_id": session_id,
                "operator_id": operator_id,
                "agent_id": agent_id,
            },
            failure_event="langfuse_tool_span_failed",
            tool=tool_name,
        ):
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
        try:
            with self._langfuse_observation(
                name=f"turn:{action}",
                as_type="agent",
                metadata={
                    "session_id": session_id,
                    "operator_id": operator_id,
                    "agent_id": agent_id,
                },
                failure_event="langfuse_turn_span_failed",
                action=action,
            ):
                yield
        finally:
            self.flush()

    @contextmanager
    def intent_span(
        self,
        *,
        session_id: str,
        operator_id: str,
        agent_id: str,
    ) -> Iterator[None]:
        logger.info(
            "agent_intent_parse",
            session_id=session_id,
            operator_id=operator_id,
            agent_id=agent_id,
            args_redacted=True,
        )
        with self._langfuse_observation(
            name="intent:parse",
            as_type="generation",
            metadata={
                "session_id": session_id,
                "operator_id": operator_id,
                "agent_id": agent_id,
            },
            failure_event="langfuse_intent_span_failed",
        ):
            yield

    def hitl_event(
        self,
        *,
        session_id: str,
        operator_id: str,
        agent_id: str,
        decision: str,
        kind: str,
    ) -> None:
        logger.info(
            "agent_hitl",
            session_id=session_id,
            operator_id=operator_id,
            agent_id=agent_id,
            hitl_decision=decision,
            kind=kind,
        )
        if self._client is None:
            return
        try:
            self._client.create_event(
                name=f"hitl:{decision}",
                metadata={
                    "session_id": session_id,
                    "operator_id": operator_id,
                    "agent_id": agent_id,
                    "kind": kind,
                },
            )
        except (ImportError, OSError, ValueError, RuntimeError, AttributeError) as exc:
            logger.warning("langfuse_hitl_event_failed", error=str(exc))


# Backward-compatible alias for agent desk code.
AgentTracing = LangfuseTracing
