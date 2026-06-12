"""Agent desk API schemas."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentSessionResponse(BaseModel):
    session_id: UUID
    operator_id: str
    session_summary: dict[str, Any]


class AgentMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class PendingApprovalResponse(BaseModel):
    kind: str
    summary: str
    details: dict[str, Any]


class AgentMessageResponse(BaseModel):
    session_id: UUID
    assistant_message: str
    pending_approval: PendingApprovalResponse | None = None
    session_summary: dict[str, Any]
    agent_disclosure: str = (
        "AI-assisted desk — you approve all issues and deliveries. "
        "The assistant cannot change circulation without your confirmation."
    )


class AgentResumeRequest(BaseModel):
    approved: bool
