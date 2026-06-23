"""Tests for agent Langfuse tracing (G13)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lms.config import Settings
from lms.shared.observability.tracing import LangfuseTracing


@pytest.fixture
def langfuse_settings() -> Settings:
    return Settings(
        _env_file=None,
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
        langfuse_host="https://us.cloud.langfuse.com",
    )


def test_tracing_without_keys_uses_structlog_only() -> None:
    tracing = LangfuseTracing(
        Settings(_env_file=None, langfuse_public_key=None, langfuse_secret_key=None)
    )
    assert tracing._client is None
    with tracing.tool_span(
        tool_name="search_patrons",
        session_id="sess-1",
        operator_id="op-1",
        agent_id="agent-1",
    ):
        pass
    with tracing.turn_span(
        session_id="sess-1",
        operator_id="op-1",
        agent_id="agent-1",
        action="message",
    ):
        pass


def test_tracing_creates_langfuse_client(langfuse_settings: Settings) -> None:
    mock_client = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=None)
    mock_cm.__exit__ = MagicMock(return_value=False)
    mock_client.start_as_current_observation.return_value = mock_cm

    with patch("langfuse.Langfuse", return_value=mock_client) as mock_ctor:
        tracing = LangfuseTracing(langfuse_settings)

    mock_ctor.assert_called_once_with(
        public_key="pk-test",
        secret_key="sk-test",
        base_url="https://us.cloud.langfuse.com",
    )
    assert tracing._client is mock_client

    with tracing.tool_span(
        tool_name="validate_issue",
        session_id="sess-2",
        operator_id="op-2",
        agent_id="agent-1",
    ):
        pass

    mock_client.start_as_current_observation.assert_called_once()
    call_kwargs = mock_client.start_as_current_observation.call_args.kwargs
    assert call_kwargs["name"] == "tool:validate_issue"
    assert call_kwargs["as_type"] == "tool"
    assert call_kwargs["metadata"]["session_id"] == "sess-2"


def test_turn_span_flushes_on_exit(langfuse_settings: Settings) -> None:
    mock_client = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=None)
    mock_cm.__exit__ = MagicMock(return_value=False)
    mock_client.start_as_current_observation.return_value = mock_cm

    with patch("langfuse.Langfuse", return_value=mock_client):
        tracing = LangfuseTracing(langfuse_settings)

    with tracing.turn_span(
        session_id="sess-3",
        operator_id="op-3",
        agent_id="agent-1",
        action="resume_approved",
    ):
        pass

    mock_client.flush.assert_called_once()


def test_settings_reads_langfuse_base_url_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://us.cloud.langfuse.com")
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    settings = Settings(_env_file=None)
    assert settings.langfuse_host == "https://us.cloud.langfuse.com"
