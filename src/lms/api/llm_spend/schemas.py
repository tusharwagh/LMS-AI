"""LLM spend reporting API schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LlmSpendLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    purpose: str
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float | None
    cached: bool
    session_id: str | None
    operator_id: str | None
    created_at: datetime


class LlmSpendLogListResponse(BaseModel):
    items: list[LlmSpendLogResponse]
    total: int
    limit: int
    offset: int


class LlmSpendSummaryGroup(BaseModel):
    purpose: str
    model: str
    provider: str
    request_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float


class LlmSpendSummaryResponse(BaseModel):
    groups: list[LlmSpendSummaryGroup]
    total_cost_usd: float
    total_requests: int
    total_tokens: int
