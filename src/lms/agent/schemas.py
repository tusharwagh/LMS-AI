"""Agent desk API and intent schemas."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from lms.loan.domain.enums import FulfillmentMode, FulfillmentStatus


class IntentAction(StrEnum):
    CHAT = "chat"
    SEARCH_PATRON = "search_patron"
    SEARCH_CATALOG = "search_catalog"
    SELECT_BARCODE = "select_barcode"
    SET_FULFILLMENT = "set_fulfillment"
    REQUEST_COMMIT = "request_commit"
    REQUEST_CANCEL_ISSUE = "request_cancel_issue"
    REQUEST_FULFILLMENT_TRANSITION = "request_fulfillment_transition"
    APPROVE = "approve"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class ParsedIntent:
    action: IntentAction
    patron_query: str | None = None
    card_barcode: str | None = None
    external_ref: str | None = None
    catalog_query: str | None = None
    holding_barcode: str | None = None
    fulfillment_mode: FulfillmentMode | None = None
    destination_notes: str | None = None
    fulfillment_status: FulfillmentStatus | None = None
    reply_hint: str | None = None


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
