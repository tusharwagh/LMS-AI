"""LLM spend log queries for cost reporting."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from lms.shared.llm.spend import LlmSpendLog
from lms.shared.llm.spend_schemas import (
    LlmSpendLogListResponse,
    LlmSpendLogResponse,
    LlmSpendSummaryGroup,
    LlmSpendSummaryResponse,
)


class LlmSpendQueryService:
    """Read-only access to persisted LiteLLM spend rows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_logs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        purpose: str | None = None,
        model: str | None = None,
        session_id: str | None = None,
        operator_id: str | None = None,
    ) -> LlmSpendLogListResponse:
        query = select(LlmSpendLog)
        count_query = select(func.count()).select_from(LlmSpendLog)
        query, count_query = self._apply_filters(
            query,
            count_query,
            from_date=from_date,
            to_date=to_date,
            purpose=purpose,
            model=model,
            session_id=session_id,
            operator_id=operator_id,
        )

        total = int(self._session.scalar(count_query) or 0)
        rows = (
            self._session.scalars(
                query.order_by(LlmSpendLog.created_at.desc()).limit(limit).offset(offset)
            ).all()
        )
        return LlmSpendLogListResponse(
            items=[LlmSpendLogResponse.model_validate(row) for row in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def summarize(
        self,
        *,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        purpose: str | None = None,
        model: str | None = None,
        session_id: str | None = None,
        operator_id: str | None = None,
    ) -> LlmSpendSummaryResponse:
        query = select(
            LlmSpendLog.purpose,
            LlmSpendLog.model,
            LlmSpendLog.provider,
            func.count().label("request_count"),
            func.coalesce(func.sum(LlmSpendLog.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(LlmSpendLog.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(LlmSpendLog.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(LlmSpendLog.cost_usd), 0).label("cost_usd"),
        )
        count_query = select(func.count()).select_from(LlmSpendLog)
        query, count_query = self._apply_filters(
            query,
            count_query,
            from_date=from_date,
            to_date=to_date,
            purpose=purpose,
            model=model,
            session_id=session_id,
            operator_id=operator_id,
        )

        total_requests = int(self._session.scalar(count_query) or 0)
        rows = self._session.execute(
            query.group_by(LlmSpendLog.purpose, LlmSpendLog.model, LlmSpendLog.provider).order_by(
                LlmSpendLog.purpose,
                LlmSpendLog.model,
            )
        ).all()

        groups = [
            LlmSpendSummaryGroup(
                purpose=row.purpose,
                model=row.model,
                provider=row.provider,
                request_count=int(row.request_count),
                prompt_tokens=int(row.prompt_tokens),
                completion_tokens=int(row.completion_tokens),
                total_tokens=int(row.total_tokens),
                cost_usd=float(row.cost_usd),
            )
            for row in rows
        ]
        total_cost_usd = sum(group.cost_usd for group in groups)
        total_tokens = sum(group.total_tokens for group in groups)
        return LlmSpendSummaryResponse(
            groups=groups,
            total_cost_usd=total_cost_usd,
            total_requests=total_requests,
            total_tokens=total_tokens,
        )

    @staticmethod
    def _apply_filters(
        query: Select[Any],
        count_query: Select[Any],
        *,
        from_date: datetime | None,
        to_date: datetime | None,
        purpose: str | None,
        model: str | None,
        session_id: str | None,
        operator_id: str | None,
    ) -> tuple[Select[Any], Select[Any]]:
        filters = []
        if from_date is not None:
            filters.append(LlmSpendLog.created_at >= from_date)
        if to_date is not None:
            filters.append(LlmSpendLog.created_at <= to_date)
        if purpose is not None:
            filters.append(LlmSpendLog.purpose == purpose)
        if model is not None:
            filters.append(LlmSpendLog.model == model)
        if session_id is not None:
            filters.append(LlmSpendLog.session_id == session_id)
        if operator_id is not None:
            filters.append(LlmSpendLog.operator_id == operator_id)

        for clause in filters:
            query = query.where(clause)
            count_query = count_query.where(clause)
        return query, count_query
