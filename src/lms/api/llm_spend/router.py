"""Staff LLM spend reporting API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from lms.platform.auth.rbac import require_staff
from lms.shared.auth.deps import DbSession
from lms.shared.llm.spend_queries import LlmSpendQueryService
from lms.shared.llm.spend_schemas import LlmSpendLogListResponse, LlmSpendSummaryResponse

router = APIRouter(prefix="/llm-spend", dependencies=[require_staff])


def _service(session: DbSession) -> LlmSpendQueryService:
    return LlmSpendQueryService(session)


@router.get("/logs", response_model=LlmSpendLogListResponse)
def list_llm_spend_logs(
    service: Annotated[LlmSpendQueryService, Depends(_service)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    from_date: Annotated[datetime | None, Query(description="Inclusive start (UTC)")] = None,
    to_date: Annotated[datetime | None, Query(description="Inclusive end (UTC)")] = None,
    purpose: Annotated[str | None, Query(max_length=64)] = None,
    model: Annotated[str | None, Query(max_length=255)] = None,
    session_id: Annotated[str | None, Query(max_length=128)] = None,
    operator_id: Annotated[str | None, Query(max_length=128)] = None,
) -> LlmSpendLogListResponse:
    return service.list_logs(
        limit=limit,
        offset=offset,
        from_date=from_date,
        to_date=to_date,
        purpose=purpose,
        model=model,
        session_id=session_id,
        operator_id=operator_id,
    )


@router.get("/summary", response_model=LlmSpendSummaryResponse)
def summarize_llm_spend(
    service: Annotated[LlmSpendQueryService, Depends(_service)],
    from_date: Annotated[datetime | None, Query(description="Inclusive start (UTC)")] = None,
    to_date: Annotated[datetime | None, Query(description="Inclusive end (UTC)")] = None,
    purpose: Annotated[str | None, Query(max_length=64)] = None,
    model: Annotated[str | None, Query(max_length=255)] = None,
    session_id: Annotated[str | None, Query(max_length=128)] = None,
    operator_id: Annotated[str | None, Query(max_length=128)] = None,
) -> LlmSpendSummaryResponse:
    return service.summarize(
        from_date=from_date,
        to_date=to_date,
        purpose=purpose,
        model=model,
        session_id=session_id,
        operator_id=operator_id,
    )
