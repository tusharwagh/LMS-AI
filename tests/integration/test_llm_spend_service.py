"""LLM spend query service — database integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from lms.shared.llm.spend import LlmSpendLog
from lms.shared.llm.spend_queries import LlmSpendQueryService

pytestmark = pytest.mark.integration


def _insert_log(
    session: Session,
    *,
    purpose: str = "intent_parse",
    model: str = "groq/test",
    provider: str = "groq",
    cost_usd: float = 0.001,
    session_id: str | None = "sess-1",
    operator_id: str | None = "lib-1",
    created_at: datetime | None = None,
) -> LlmSpendLog:
    row = LlmSpendLog(
        purpose=purpose,
        model=model,
        provider=provider,
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        cost_usd=cost_usd,
        cached=False,
        session_id=session_id,
        operator_id=operator_id,
        created_at=created_at or datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row


def test_llm_spend_staff_http_returns_paginated_shape(client: TestClient) -> None:
    response = client.get("/api/v1/llm-spend/logs", params={"limit": 5, "offset": 0})
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 5
    assert body["offset"] == 0
    assert isinstance(body["items"], list)
    assert isinstance(body["total"], int)


def test_llm_spend_service_filters_by_session_and_operator(db_session: Session) -> None:
    service = LlmSpendQueryService(db_session)
    _insert_log(db_session, session_id="sess-a", operator_id="op-a")
    _insert_log(db_session, session_id="sess-b", operator_id="op-b")

    result = service.list_logs(session_id="sess-a", limit=10, offset=0)
    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].session_id == "sess-a"
    assert result.items[0].operator_id == "op-a"


def test_llm_spend_service_summary_aggregates(db_session: Session) -> None:
    service = LlmSpendQueryService(db_session)
    now = datetime.now(UTC)
    summary_session = "summary-test-isolated"
    _insert_log(
        db_session,
        purpose="intent_parse",
        model="groq/a",
        cost_usd=0.002,
        session_id=summary_session,
        created_at=now - timedelta(hours=1),
    )
    _insert_log(
        db_session,
        purpose="intent_parse",
        model="groq/a",
        cost_usd=0.003,
        session_id=summary_session,
        created_at=now,
    )
    _insert_log(
        db_session,
        purpose="completion",
        model="openai/b",
        provider="openai",
        cost_usd=0.010,
        session_id=summary_session,
        created_at=now,
    )

    summary = service.summarize(
        from_date=now - timedelta(days=1),
        to_date=now + timedelta(minutes=1),
        session_id=summary_session,
    )
    assert summary.total_requests == 3
    assert summary.total_tokens == 45
    assert summary.total_cost_usd == pytest.approx(0.015)
    assert len(summary.groups) == 2
