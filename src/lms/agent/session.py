"""Agent session models and in-memory store."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from lms.agent.masking import PseudonymMap
from lms.loan.domain.enums import FulfillmentMode, FulfillmentStatus


class DeskFlow(StrEnum):
    ISSUE = "issue"
    RETURN = "return"


class PendingActionKind(StrEnum):
    COMMIT_ISSUE = "commit_issue"
    TRANSITION_FULFILLMENT = "transition_fulfillment"
    CANCEL_ISSUE = "cancel_issue"
    COMMIT_RETURN = "commit_return"
    SELECT_RETURN = "select_return"
    INITIATE_RETURN_PICKUP = "initiate_return_pickup"


@dataclass
class IssueSlots:
    active_flow: DeskFlow = DeskFlow.ISSUE
    patron_id: UUID | None = None
    patron_display_name: str | None = None
    holding_id: UUID | None = None
    holding_barcode: str | None = None
    catalog_title: str | None = None
    fulfillment_mode: FulfillmentMode = FulfillmentMode.DESK
    destination_notes: str | None = None
    loan_id: UUID | None = None
    fulfillment_id: UUID | None = None
    fulfillment_target_status: FulfillmentStatus | None = None
    due_date: date | None = None
    is_overdue: bool | None = None
    return_candidates: list[dict[str, Any]] = field(default_factory=list)
    catalog_candidates: list[dict[str, Any]] = field(default_factory=list)
    patron_candidates: list[dict[str, Any]] = field(default_factory=list)
    awaiting_patron: bool = False
    awaiting_book_criteria: bool = False
    awaiting_desk_patron: bool = False
    awaiting_desk_next_action: bool = False
    awaiting_desk_return_pick: bool = False
    desk_return_intent: bool = False
    awaiting_catalog_criteria: bool = False
    awaiting_patron_lookup: bool = False
    issue_search_criteria: str | None = None
    guided_issue_active: bool = False
    guided_return_active: bool = False
    guided_catalog_active: bool = False
    guided_patron_lookup_active: bool = False

    @property
    def has_patron_and_holding(self) -> bool:
        return self.patron_id is not None and self.holding_id is not None


@dataclass
class PendingApproval:
    kind: PendingActionKind
    summary: str
    details: dict[str, Any]
    idempotency_key: str


@dataclass
class AgentIssueSession:
    session_id: UUID
    operator_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    messages: list[dict[str, str]] = field(default_factory=list)
    slots: IssueSlots = field(default_factory=IssueSlots)
    pseudonyms: PseudonymMap = field(default_factory=PseudonymMap)
    pending_approval: PendingApproval | None = None
    tool_calls_this_turn: int = 0


class SessionStore:
    """In-memory session store for agent threads (MVP single-process).

    Twelve-Factor VI note: production horizontal scale requires a durable backing
    service (Postgres/Redis) for session + HITL state. Until then, run one API worker
    per desk deployment or accept session loss on restart.
    """

    def __init__(self) -> None:
        self._sessions: dict[UUID, AgentIssueSession] = {}

    def create(self, operator_id: str) -> AgentIssueSession:
        session = AgentIssueSession(session_id=uuid4(), operator_id=operator_id)
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: UUID) -> AgentIssueSession | None:
        return self._sessions.get(session_id)

    def save(self, session: AgentIssueSession) -> None:
        session.updated_at = datetime.now(UTC)
        self._sessions[session.session_id] = session


# Shared store for the API process (MVP).
session_store = SessionStore()
