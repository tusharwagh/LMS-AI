"""IssueAgentCoordinator — SOP-bound desk agent (ADR-021, ADR-025)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from lms.agent import messages as desk
from lms.agent.intent_parser import LLMIntentParser
from lms.agent.masking import redact_for_audit
from lms.agent.schemas import IntentAction, ParsedIntent
from lms.agent.session import (
    AgentIssueSession,
    IssueSlots,
    PendingActionKind,
    PendingApproval,
    SessionStore,
    session_store,
)
from lms.agent.tools import (
    AUTHORIZED_TOOL_NAMES,
    RESTRICTED_TOOL_NAMES,
    IssueTools,
    ToolResult,
)
from lms.agent.tracing import AgentTracing
from lms.api.errors import AppError, ErrorCode
from lms.api.workflows.search_and_issue import SearchAndIssueWorkflow
from lms.config import Settings, get_settings
from lms.loan.application.fulfillment_service import FulfillmentService
from lms.loan.domain.enums import FulfillmentStatus


@dataclass(frozen=True, slots=True)
class AgentTurnResult:
    session_id: UUID
    assistant_message: str
    pending_approval: dict[str, Any] | None
    session_summary: dict[str, Any]


class IssueAgentCoordinator:
    AGENT_ID = "LMS Desk Issue & Fulfillment Agent"

    def __init__(
        self,
        session: Session,
        *,
        workflow: SearchAndIssueWorkflow,
        fulfillment: FulfillmentService,
        parser: LLMIntentParser,
        settings: Settings | None = None,
        store: SessionStore | None = None,
        tracing: AgentTracing | None = None,
    ) -> None:
        self._db = session
        self._settings = settings or get_settings()
        self._store = store or session_store
        self._workflow = workflow
        self._fulfillment = fulfillment
        self._parser = parser
        self._tracing = tracing or AgentTracing(self._settings)

    def start_session(self, operator_id: str) -> AgentIssueSession:
        self._ensure_enabled()
        return self._store.create(operator_id)

    def get_session(self, session_id: UUID) -> AgentIssueSession:
        self._ensure_enabled()
        found = self._store.get(session_id)
        if found is None:
            raise AppError(ErrorCode.NOT_FOUND, "Agent session not found", status_code=404)
        return found

    def get_session_for_operator(self, session_id: UUID, operator_id: str) -> AgentIssueSession:
        agent_session = self.get_session(session_id)
        self._ensure_operator_owns_session(agent_session, operator_id)
        return agent_session

    def handle_message(self, session_id: UUID, message: str, operator_id: str) -> AgentTurnResult:
        self._ensure_enabled()
        agent_session = self.get_session_for_operator(session_id, operator_id)
        agent_session.tool_calls_this_turn = 0
        agent_session.messages.append({"role": "user", "content": message})

        tools = self._tools_for(agent_session)
        has_pending = agent_session.pending_approval is not None
        with self._tracing.turn_span(
            session_id=str(session_id),
            operator_id=operator_id,
            agent_id=self.AGENT_ID,
            action="message",
        ):
            intent = self._parser.parse(message, has_pending_approval=has_pending)
            reply = self._apply_intent(agent_session, tools, intent, user_message=message)

        agent_session.messages.append({"role": "assistant", "content": reply.assistant_message})
        self._store.save(agent_session)
        return reply

    def resume(
        self,
        session_id: UUID,
        *,
        approved: bool,
        operator_id: str,
    ) -> AgentTurnResult:
        self._ensure_enabled()
        agent_session = self.get_session_for_operator(session_id, operator_id)
        pending = agent_session.pending_approval
        if pending is None:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "No pending approval for this session",
                status_code=422,
            )

        tools = self._tools_for(agent_session)
        with self._tracing.turn_span(
            session_id=str(session_id),
            operator_id=operator_id,
            agent_id=self.AGENT_ID,
            action="resume_approved" if approved else "resume_denied",
        ):
            if not approved:
                kind = pending.kind
                agent_session.pending_approval = None
                return self._complete_turn(agent_session, desk.approval_denied(kind))

            result_msg = self._execute_pending(
                agent_session, tools, pending, operator_id=operator_id
            )
            agent_session.pending_approval = None
            return self._complete_turn(agent_session, result_msg)

    def _apply_intent(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        intent: ParsedIntent,
        *,
        user_message: str,
    ) -> AgentTurnResult:
        if intent.action in {IntentAction.APPROVE, IntentAction.DENY}:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "Use the resume endpoint to approve or deny pending actions",
                status_code=422,
            )

        slots = agent_session.slots
        self._apply_slot_updates(intent, slots)

        match intent.action:
            case IntentAction.SEARCH_PATRON:
                message = self._handle_search_patron(agent_session, tools, intent, slots)
            case IntentAction.SEARCH_CATALOG:
                message = self._run_tool(
                    agent_session,
                    "search_lendable",
                    lambda: tools.search_lendable(
                        slots,
                        intent.catalog_query or "",
                        action=intent.action,
                    ),
                ).message
            case IntentAction.SELECT_BARCODE:
                message = self._run_tool(
                    agent_session,
                    "select_barcode",
                    lambda: tools.select_barcode(
                        slots,
                        intent.holding_barcode or "",
                        action=intent.action,
                    ),
                ).message
            case IntentAction.SET_FULFILLMENT:
                message = desk.fulfillment_mode_set(slots.fulfillment_mode)
            case IntentAction.REQUEST_COMMIT:
                return self._handle_request_commit(agent_session, tools, intent, slots)
            case IntentAction.REQUEST_CANCEL_ISSUE:
                return self._request_cancel_approval(agent_session)
            case IntentAction.REQUEST_FULFILLMENT_TRANSITION:
                target = intent.fulfillment_status or FulfillmentStatus.IN_TRANSIT
                return self._request_fulfillment_approval(agent_session, tools, slots, target)
            case IntentAction.CHAT:
                message = intent.reply_hint or desk.help_for_unknown_intent(user_message)
            case _:
                message = intent.reply_hint or desk.help_for_unknown_intent(user_message)

        return self._result(agent_session, message or desk.turn_acknowledged(user_message))

    def _handle_search_patron(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        intent: ParsedIntent,
        slots: IssueSlots,
    ) -> str:
        if intent.card_barcode:
            return self._run_tool(
                agent_session,
                "resolve_patron",
                lambda: tools.resolve_patron(slots, card_barcode=intent.card_barcode),
            ).message
        if intent.external_ref:
            return self._run_tool(
                agent_session,
                "resolve_patron",
                lambda: tools.resolve_patron(slots, external_ref=intent.external_ref),
            ).message
        if not intent.patron_query:
            return desk.patron_search_empty()

        patron_query = intent.patron_query
        matches = self._run_tool(
            agent_session,
            "search_patrons",
            lambda: tools.search_patrons(patron_query),
        )
        patrons_raw = matches.data.get("patrons", [])
        if not isinstance(patrons_raw, list):
            return matches.message
        patrons: list[dict[str, object]] = patrons_raw
        if len(patrons) != 1:
            return matches.message

        pseudo = str(patrons[0]["pseudonym"])
        patron_id = agent_session.pseudonyms.resolve_patron(pseudo)
        if patron_id is None:
            return matches.message

        return self._run_tool(
            agent_session,
            "resolve_patron",
            lambda: tools.resolve_patron(
                slots,
                patron_id=patron_id,
                message_query=patron_query,
            ),
        ).message

    def _handle_request_commit(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        intent: ParsedIntent,
        slots: IssueSlots,
    ) -> AgentTurnResult:
        if intent.patron_query:
            self._run_tool(
                agent_session,
                "resolve_patron",
                lambda: tools.resolve_patron(slots, display_name=intent.patron_query),
            )
        if intent.catalog_query:
            catalog_query = intent.catalog_query
            self._run_tool(
                agent_session,
                "search_lendable",
                lambda: tools.search_lendable(
                    slots,
                    catalog_query,
                    action=intent.action,
                ),
            )
        validation = self._run_tool(
            agent_session,
            "validate_issue",
            lambda: tools.validate_issue(slots, action=intent.action),
        )
        if not validation.ok:
            return self._result(agent_session, validation.message)
        return self._request_commit_approval(agent_session)

    def _request_commit_approval(self, agent_session: AgentIssueSession) -> AgentTurnResult:
        slots = agent_session.slots
        if not slots.has_patron_and_holding:
            return self._result(
                agent_session,
                desk.missing_slots_for_commit(
                    missing_patron=slots.patron_id is None,
                    missing_copy=slots.holding_id is None,
                ),
            )

        summary = desk.commit_approval_summary(
            slots.patron_display_name or "patron",
            slots.catalog_title or "copy",
            slots.holding_barcode or "barcode",
            slots.fulfillment_mode,
        )
        self._set_pending_approval(
            agent_session,
            kind=PendingActionKind.COMMIT_ISSUE,
            summary=summary,
            details={
                "patron_display_name": slots.patron_display_name,
                "catalog_title": slots.catalog_title,
                "holding_barcode": slots.holding_barcode,
                "fulfillment_mode": slots.fulfillment_mode.value,
            },
        )
        return self._result(
            agent_session,
            desk.commit_approval_prompt(summary),
            pending=self._pending_payload(agent_session.pending_approval),
        )

    def _request_cancel_approval(self, agent_session: AgentIssueSession) -> AgentTurnResult:
        slots = agent_session.slots
        if slots.loan_id is None:
            return self._result(agent_session, desk.no_open_loan_for_cancel())

        summary = desk.cancel_approval_summary(
            slots.patron_display_name or "patron",
            slots.catalog_title or "copy",
            slots.holding_barcode or "barcode",
        )
        self._set_pending_approval(
            agent_session,
            kind=PendingActionKind.CANCEL_ISSUE,
            summary=summary,
            details={
                "patron_display_name": slots.patron_display_name,
                "catalog_title": slots.catalog_title,
                "holding_barcode": slots.holding_barcode,
            },
        )
        return self._result(
            agent_session,
            desk.cancel_approval_prompt(summary),
            pending=self._pending_payload(agent_session.pending_approval),
        )

    def _request_fulfillment_approval(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        slots: IssueSlots,
        target: FulfillmentStatus,
    ) -> AgentTurnResult:
        status_result = self._run_tool(
            agent_session,
            "get_fulfillment_status",
            lambda: tools.get_fulfillment_status(slots),
        )
        if not status_result.ok:
            return self._result(agent_session, status_result.message)

        prompt = desk.fulfillment_transition_prompt(
            target,
            title=slots.catalog_title,
        )
        self._set_pending_approval(
            agent_session,
            kind=PendingActionKind.TRANSITION_FULFILLMENT,
            summary=prompt,
            details={"target_status": target.value},
        )
        slots.fulfillment_target_status = target
        return self._result(
            agent_session,
            prompt,
            pending=self._pending_payload(agent_session.pending_approval),
        )

    def _execute_pending(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        pending: PendingApproval,
        *,
        operator_id: str,
    ) -> str:
        slots = agent_session.slots
        if pending.kind == PendingActionKind.COMMIT_ISSUE:
            return self._run_tool(
                agent_session,
                "commit_issue",
                lambda: tools.commit_issue(
                    slots,
                    idempotency_key=pending.idempotency_key,
                    operator_id=operator_id,
                ),
            ).message
        if pending.kind == PendingActionKind.TRANSITION_FULFILLMENT:
            target = slots.fulfillment_target_status or FulfillmentStatus.IN_TRANSIT
            return self._run_tool(
                agent_session,
                "transition_fulfillment",
                lambda: tools.transition_fulfillment(
                    slots,
                    target,
                    idempotency_key=pending.idempotency_key,
                ),
            ).message
        if pending.kind == PendingActionKind.CANCEL_ISSUE:
            return self._run_tool(
                agent_session,
                "cancel_issue",
                lambda: tools.cancel_issue(
                    slots,
                    idempotency_key=pending.idempotency_key,
                ),
            ).message
        raise AppError(ErrorCode.RETRIABLE_ERROR, "Unknown pending action", status_code=500)

    def _run_tool(
        self,
        agent_session: AgentIssueSession,
        name: str,
        fn: Callable[[], ToolResult],
    ) -> ToolResult:
        if name in RESTRICTED_TOOL_NAMES:
            raise AppError(ErrorCode.FORBIDDEN, f"Tool {name} is restricted", status_code=403)
        if name not in AUTHORIZED_TOOL_NAMES:
            raise AppError(ErrorCode.FORBIDDEN, f"Tool {name} is not authorized", status_code=403)
        agent_session.tool_calls_this_turn += 1
        if agent_session.tool_calls_this_turn > self._settings.agent_max_tool_calls_per_turn:
            raise AppError(
                ErrorCode.RATE_LIMIT_EXCEEDED,
                "Too many tool calls this turn",
                status_code=429,
            )
        with self._tracing.tool_span(
            tool_name=name,
            session_id=str(agent_session.session_id),
            operator_id=agent_session.operator_id,
            agent_id=self.AGENT_ID,
        ):
            return fn()

    def _tools_for(self, agent_session: AgentIssueSession) -> IssueTools:
        return IssueTools(
            self._db,
            self._workflow,
            self._fulfillment,
            agent_session.pseudonyms,
        )

    def _apply_slot_updates(self, intent: ParsedIntent, slots: IssueSlots) -> None:
        if intent.fulfillment_mode is not None:
            slots.fulfillment_mode = intent.fulfillment_mode
        if intent.destination_notes:
            slots.destination_notes = intent.destination_notes

    def _set_pending_approval(
        self,
        agent_session: AgentIssueSession,
        *,
        kind: PendingActionKind,
        summary: str,
        details: dict[str, Any],
    ) -> None:
        agent_session.pending_approval = PendingApproval(
            kind=kind,
            summary=summary,
            details=details,
            idempotency_key=str(uuid4()),
        )

    def _complete_turn(self, agent_session: AgentIssueSession, message: str) -> AgentTurnResult:
        redacted = redact_for_audit(message)
        agent_session.messages.append({"role": "assistant", "content": redacted})
        self._store.save(agent_session)
        return AgentTurnResult(
            session_id=agent_session.session_id,
            assistant_message=redacted,
            pending_approval=None,
            session_summary=self._session_summary(agent_session),
        )

    def _result(
        self,
        agent_session: AgentIssueSession,
        message: str,
        *,
        pending: dict[str, Any] | None = None,
    ) -> AgentTurnResult:
        return AgentTurnResult(
            session_id=agent_session.session_id,
            assistant_message=redact_for_audit(message),
            pending_approval=pending,
            session_summary=self._session_summary(agent_session),
        )

    def _pending_payload(self, pending: PendingApproval | None) -> dict[str, Any]:
        if pending is None:
            return {}
        return {
            "kind": pending.kind.value,
            "summary": pending.summary,
            "details": pending.details,
        }

    def session_summary(self, agent_session: AgentIssueSession) -> dict[str, Any]:
        return self._session_summary(agent_session)

    def _session_summary(self, agent_session: AgentIssueSession) -> dict[str, Any]:
        slots = agent_session.slots
        return {
            "patron_display_name": slots.patron_display_name,
            "catalog_title": slots.catalog_title,
            "holding_barcode": slots.holding_barcode,
            "fulfillment_mode": slots.fulfillment_mode.value,
            "has_pending_approval": agent_session.pending_approval is not None,
        }

    def _ensure_operator_owns_session(
        self,
        agent_session: AgentIssueSession,
        operator_id: str,
    ) -> None:
        if agent_session.operator_id != operator_id:
            raise AppError(
                ErrorCode.FORBIDDEN,
                "Session belongs to another operator",
                status_code=403,
            )

    def _ensure_enabled(self) -> None:
        if not self._settings.agent_issue_enabled:
            raise AppError(
                ErrorCode.FORBIDDEN,
                "Agent desk is disabled (set AGENT_ISSUE_ENABLED=true)",
                status_code=403,
            )
