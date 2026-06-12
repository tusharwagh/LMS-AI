"""IssueAgentCoordinator — SOP-bound desk agent (ADR-021, ADR-025)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from lms.agent.intent_parser import IntentAction, LLMIntentParser, ParsedIntent
from lms.agent.masking import redact_for_audit
from lms.agent.session import (
    AgentIssueSession,
    PendingActionKind,
    PendingApproval,
    SessionStore,
    session_store,
)
from lms.agent.tools import (
    AUTHORIZED_TOOL_NAMES,
    RESTRICTED_TOOL_NAMES,
    IssueTools,
)
from lms.api.composition import get_circulation_orchestrator
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
        settings: Settings | None = None,
        store: SessionStore | None = None,
    ) -> None:
        self._db = session
        self._settings = settings or get_settings()
        self._store = store or session_store
        orchestrator = get_circulation_orchestrator(session)
        self._workflow = SearchAndIssueWorkflow(session, orchestrator)
        self._fulfillment = FulfillmentService(session)
        self._parser = LLMIntentParser(self._settings)

    def start_session(self, operator_id: str) -> AgentIssueSession:
        self._ensure_enabled()
        return self._store.create(operator_id)

    def get_session(self, session_id: UUID) -> AgentIssueSession:
        self._ensure_enabled()
        found = self._store.get(session_id)
        if found is None:
            raise AppError(ErrorCode.NOT_FOUND, "Agent session not found", status_code=404)
        return found

    def handle_message(self, session_id: UUID, message: str, operator_id: str) -> AgentTurnResult:
        self._ensure_enabled()
        agent_session = self.get_session(session_id)
        if agent_session.operator_id != operator_id:
            raise AppError(
                ErrorCode.FORBIDDEN,
                "Session belongs to another operator",
                status_code=403,
            )

        agent_session.tool_calls_this_turn = 0
        agent_session.messages.append({"role": "user", "content": message})
        tools = IssueTools(
            self._db,
            self._workflow,
            self._fulfillment,
            agent_session.pseudonyms,
        )

        has_pending = agent_session.pending_approval is not None
        intent = self._parser.parse(message, has_pending_approval=has_pending)
        reply = self._apply_intent(agent_session, tools, intent, operator_id=operator_id)

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
        agent_session = self.get_session(session_id)
        if agent_session.operator_id != operator_id:
            raise AppError(
                ErrorCode.FORBIDDEN,
                "Session belongs to another operator",
                status_code=403,
            )
        pending = agent_session.pending_approval
        if pending is None:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "No pending approval for this session",
                status_code=422,
            )

        tools = IssueTools(
            self._db,
            self._workflow,
            self._fulfillment,
            agent_session.pseudonyms,
        )

        if not approved:
            agent_session.pending_approval = None
            msg = "Action cancelled. You can continue or use the wizard."
            agent_session.messages.append({"role": "assistant", "content": msg})
            self._store.save(agent_session)
            return AgentTurnResult(
                session_id=agent_session.session_id,
                assistant_message=msg,
                pending_approval=None,
                session_summary=self._session_summary(agent_session),
            )

        result_msg = self._execute_pending(agent_session, tools, pending, operator_id=operator_id)
        agent_session.pending_approval = None
        agent_session.messages.append({"role": "assistant", "content": result_msg})
        self._store.save(agent_session)
        return AgentTurnResult(
            session_id=agent_session.session_id,
            assistant_message=result_msg,
            pending_approval=None,
            session_summary=self._session_summary(agent_session),
        )

    def _apply_intent(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        intent: ParsedIntent,
        *,
        operator_id: str,
    ) -> AgentTurnResult:
        if intent.action in {IntentAction.APPROVE, IntentAction.DENY}:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "Use the resume endpoint to approve or deny pending actions",
                status_code=422,
            )

        slots = agent_session.slots

        if intent.fulfillment_mode is not None:
            slots.fulfillment_mode = intent.fulfillment_mode
        if intent.destination_notes:
            slots.destination_notes = intent.destination_notes

        tool_result_msg: str | None = None

        if intent.action == IntentAction.SEARCH_PATRON:
            if intent.card_barcode:
                res = self._run_tool(
                    agent_session,
                    "resolve_patron",
                    lambda: tools.resolve_patron(slots, card_barcode=intent.card_barcode),
                )
                tool_result_msg = res.message
            elif intent.external_ref:
                res = self._run_tool(
                    agent_session,
                    "resolve_patron",
                    lambda: tools.resolve_patron(slots, external_ref=intent.external_ref),
                )
                tool_result_msg = res.message
            elif intent.patron_query:
                matches = self._run_tool(
                    agent_session,
                    "search_patrons",
                    lambda: tools.search_patrons(intent.patron_query),
                )
                patrons = matches.data.get("patrons", [])
                if len(patrons) == 1:
                    pseudo = str(patrons[0]["pseudonym"])
                    pid = agent_session.pseudonyms.resolve_patron(pseudo)
                    if pid:
                        res = self._run_tool(
                            agent_session,
                            "resolve_patron",
                            lambda: tools.resolve_patron(slots, patron_id=pid),
                        )
                        tool_result_msg = res.message
                    else:
                        tool_result_msg = matches.message
                else:
                    tool_result_msg = matches.message
            else:
                tool_result_msg = "Provide a patron name, card, or admission number."
        elif intent.action == IntentAction.SEARCH_CATALOG:
            tool_result_msg = self._run_tool(
                agent_session,
                "search_lendable",
                lambda: tools.search_lendable(slots, intent.catalog_query or ""),
            ).message
        elif intent.action == IntentAction.SELECT_BARCODE:
            tool_result_msg = self._run_tool(
                agent_session,
                "select_barcode",
                lambda: tools.select_barcode(slots, intent.holding_barcode or ""),
            ).message
        elif intent.action == IntentAction.SET_FULFILLMENT:
            tool_result_msg = f"Fulfillment mode set to {slots.fulfillment_mode}."
        elif intent.action == IntentAction.REQUEST_COMMIT:
            if intent.patron_query:
                self._run_tool(
                    agent_session,
                    "resolve_patron",
                    lambda: tools.resolve_patron(slots, display_name=intent.patron_query),
                )
            if intent.catalog_query:
                self._run_tool(
                    agent_session,
                    "search_lendable",
                    lambda: tools.search_lendable(slots, intent.catalog_query),
                )
            validation = self._run_tool(
                agent_session,
                "validate_issue",
                lambda: tools.validate_issue(slots),
            )
            if not validation.ok:
                return self._result(agent_session, validation.message)
            return self._request_commit_approval(agent_session, operator_id)
        elif intent.action == IntentAction.REQUEST_CANCEL_ISSUE:
            return self._request_cancel_approval(agent_session)
        elif intent.action == IntentAction.REQUEST_FULFILLMENT_TRANSITION:
            status = intent.fulfillment_status or FulfillmentStatus.IN_TRANSIT
            return self._request_fulfillment_approval(agent_session, status, operator_id)
        else:
            tool_result_msg = intent.reply_hint or (
                "I can help issue a book. Try: "
                "'Issue [title] to [patron name], deliver to Class 5A' "
                "or identify a patron first."
            )

        return self._result(agent_session, tool_result_msg or "Done.")

    def _request_commit_approval(
        self,
        agent_session: AgentIssueSession,
        operator_id: str,
    ) -> AgentTurnResult:
        slots = agent_session.slots
        if slots.patron_id is None or slots.holding_id is None:
            return self._result(agent_session, "Need patron and copy before commit.")

        summary = (
            f"Issue {slots.catalog_title or 'copy'} "
            f"({slots.holding_barcode}) to {slots.patron_display_name} "
            f"via {slots.fulfillment_mode}."
        )
        idem = str(uuid4())
        agent_session.pending_approval = PendingApproval(
            kind=PendingActionKind.COMMIT_ISSUE,
            summary=summary,
            details={
                "patron_display_name": slots.patron_display_name,
                "catalog_title": slots.catalog_title,
                "holding_barcode": slots.holding_barcode,
                "fulfillment_mode": slots.fulfillment_mode.value,
            },
            idempotency_key=idem,
        )
        msg = summary + " Approve this issue?"
        return self._result(
            agent_session,
            msg,
            pending=self._pending_payload(agent_session.pending_approval),
        )

    def _request_cancel_approval(self, agent_session: AgentIssueSession) -> AgentTurnResult:
        slots = agent_session.slots
        if slots.loan_id is None:
            return self._result(agent_session, "No open loan in this session to cancel.")

        summary = (
            f"Cancel issue of {slots.catalog_title or 'copy'} "
            f"({slots.holding_barcode}) to {slots.patron_display_name}?"
        )
        idem = str(uuid4())
        agent_session.pending_approval = PendingApproval(
            kind=PendingActionKind.CANCEL_ISSUE,
            summary=summary,
            details={
                "patron_display_name": slots.patron_display_name,
                "catalog_title": slots.catalog_title,
                "holding_barcode": slots.holding_barcode,
            },
            idempotency_key=idem,
        )
        return self._result(
            agent_session,
            summary,
            pending=self._pending_payload(agent_session.pending_approval),
        )

    def _request_fulfillment_approval(
        self,
        agent_session: AgentIssueSession,
        target: FulfillmentStatus,
        operator_id: str,
    ) -> AgentTurnResult:
        slots = agent_session.slots
        status_result = IssueTools(
            self._db,
            self._workflow,
            self._fulfillment,
            agent_session.pseudonyms,
        ).get_fulfillment_status(slots)
        if not status_result.ok:
            return self._result(agent_session, status_result.message)

        summary = f"Transition fulfillment to {target.value}?"
        idem = str(uuid4())
        agent_session.pending_approval = PendingApproval(
            kind=PendingActionKind.TRANSITION_FULFILLMENT,
            summary=summary,
            details={"target_status": target.value},
            idempotency_key=idem,
        )
        slots.fulfillment_target_status = target
        return self._result(
            agent_session,
            summary,
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
            result = self._run_tool(
                agent_session,
                "commit_issue",
                lambda: tools.commit_issue(
                    slots,
                    idempotency_key=pending.idempotency_key,
                    operator_id=operator_id,
                ),
            )
            return result.message
        if pending.kind == PendingActionKind.TRANSITION_FULFILLMENT:
            target = slots.fulfillment_target_status or FulfillmentStatus.IN_TRANSIT
            result = self._run_tool(
                agent_session,
                "transition_fulfillment",
                lambda: tools.transition_fulfillment(
                    slots,
                    target,
                    idempotency_key=pending.idempotency_key,
                ),
            )
            return result.message
        if pending.kind == PendingActionKind.CANCEL_ISSUE:
            result = self._run_tool(
                agent_session,
                "cancel_issue",
                lambda: tools.cancel_issue(
                    slots,
                    idempotency_key=pending.idempotency_key,
                ),
            )
            return result.message
        raise AppError(ErrorCode.RETRIABLE_ERROR, "Unknown pending action", status_code=500)

    def _run_tool(self, agent_session: AgentIssueSession, name: str, fn):  # type: ignore[no-untyped-def]
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
        return fn()

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

    def _pending_payload(self, pending: PendingApproval) -> dict[str, Any]:
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

    def _ensure_enabled(self) -> None:
        if not self._settings.agent_issue_enabled:
            raise AppError(
                ErrorCode.FORBIDDEN,
                "Agent desk is disabled (set AGENT_ISSUE_ENABLED=true)",
                status_code=403,
            )
