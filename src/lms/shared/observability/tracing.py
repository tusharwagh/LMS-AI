"""Optional Langfuse spans and structured audit logging (org-python-platform)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, cast

from langfuse_tracing import LangfuseTracing as _LangfuseTracing

from lms.config import Settings

__all__ = ["AgentTracing", "LangfuseTracing"]


class LangfuseTracing:
    """Structured audit logging; Langfuse spans when keys are configured."""

    def __init__(self, settings: Settings) -> None:
        self._inner = _LangfuseTracing(settings.to_langfuse_tracing_settings())

    @property
    def _client(self) -> Any | None:
        return self._inner._client

    def flush(self) -> None:
        self._inner.flush()

    def auth_ok(self) -> bool:
        return cast(bool, self._inner.auth_ok())

    @contextmanager
    def tool_span(
        self,
        *,
        tool_name: str,
        session_id: str,
        operator_id: str,
        agent_id: str,
    ) -> Iterator[None]:
        with self._inner.tool_span(
            tool_name=tool_name,
            session_id=session_id,
            operator_id=operator_id,
            agent_id=agent_id,
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
        with self._inner.turn_span(
            session_id=session_id,
            operator_id=operator_id,
            agent_id=agent_id,
            action=action,
        ):
            yield

    @contextmanager
    def intent_span(
        self,
        *,
        session_id: str,
        operator_id: str,
        agent_id: str,
    ) -> Iterator[None]:
        with self._inner.intent_span(
            session_id=session_id,
            operator_id=operator_id,
            agent_id=agent_id,
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
        self._inner.hitl_event(
            session_id=session_id,
            operator_id=operator_id,
            agent_id=agent_id,
            decision=decision,
            kind=kind,
        )


AgentTracing = LangfuseTracing
