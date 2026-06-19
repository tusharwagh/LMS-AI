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
    SELECT_CATALOG_COPY = "select_catalog_copy"
    SELECT_BARCODE = "select_barcode"
    SET_FULFILLMENT = "set_fulfillment"
    ISSUE_TO_PATRON = "issue_to_patron"
    START_ISSUE_TO_PATRON = "start_issue_to_patron"
    PROVIDE_PATRON_FOR_ISSUE = "provide_patron_for_issue"
    PROVIDE_BOOK_CRITERIA = "provide_book_criteria"
    START_RETURN = "start_return"
    START_PATRON_DESK = "start_patron_desk"
    PROVIDE_PATRON_FOR_DESK = "provide_patron_for_desk"
    DESK_START_RETURN = "desk_start_return"
    DESK_START_ISSUE = "desk_start_issue"
    DESK_START_CATALOG = "desk_start_catalog"
    DESK_SESSION_DONE = "desk_session_done"
    START_CATALOG_SEARCH = "start_catalog_search"
    PROVIDE_CATALOG_CRITERIA = "provide_catalog_criteria"
    START_PATRON_LOOKUP = "start_patron_lookup"
    PROVIDE_PATRON_LOOKUP = "provide_patron_lookup"
    SELECT_PATRON = "select_patron"
    DECLINE_CONTINUE = "decline_continue"
    REQUEST_COMMIT = "request_commit"
    REQUEST_CANCEL_ISSUE = "request_cancel_issue"
    REQUEST_FULFILLMENT_TRANSITION = "request_fulfillment_transition"
    LOOKUP_RETURN = "lookup_return"
    SEARCH_RETURN = "search_return"
    SELECT_RETURN_LOAN = "select_return_loan"
    REQUEST_COMMIT_RETURN = "request_commit_return"
    REQUEST_RETURN_PICKUP = "request_return_pickup"
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
    copy_pseudonym: str | None = None
    patron_pseudonym: str | None = None
    loan_pseudonym: str | None = None
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
        "AI-assisted desk — you approve all issues, returns, and deliveries. "
        "The assistant cannot change circulation without your confirmation."
    )


class AgentResumeRequest(BaseModel):
    approved: bool
