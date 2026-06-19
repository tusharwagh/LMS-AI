"""IssueAgentCoordinator — SOP-bound desk agent (ADR-021, ADR-025)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from lms.agent import messages as desk
from lms.agent.intent_parser import LLMIntentParser
from lms.agent.masking import redact_for_audit, sanitize_approval_details
from lms.agent.schemas import IntentAction, ParsedIntent
from lms.agent.session import (
    AgentIssueSession,
    DeskFlow,
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
    ReturnTools,
    ToolResult,
)
from lms.agent.tracing import AgentTracing
from lms.api.errors import AppError, ErrorCode
from lms.api.workflows.return_book import ReturnBookWorkflow
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
    AGENT_ID = "LMS Desk Circulation Agent"

    def __init__(
        self,
        session: Session,
        *,
        workflow: SearchAndIssueWorkflow,
        return_workflow: ReturnBookWorkflow,
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
        self._return_workflow = return_workflow
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
        redacted_user = redact_for_audit(message)
        agent_session.messages.append({"role": "user", "content": redacted_user})

        if agent_session.pending_approval is not None:
            block_msg = desk.pending_approval_blocks_message(
                agent_session.pending_approval.summary,
            )
            agent_session.messages.append({"role": "assistant", "content": block_msg})
            self._store.save(agent_session)
            return self._result(
                agent_session,
                block_msg,
                pending=self._pending_payload(agent_session.pending_approval),
            )

        tools = self._issue_tools_for(agent_session)
        return_tools = self._return_tools_for(agent_session)
        has_pending = agent_session.pending_approval is not None
        with self._tracing.turn_span(
            session_id=str(session_id),
            operator_id=operator_id,
            agent_id=self.AGENT_ID,
            action="message",
        ):
            intent = self._parser.parse_with_context(
                message,
                has_pending_approval=has_pending,
                has_return_candidates=bool(agent_session.slots.return_candidates),
                has_catalog_candidates=bool(agent_session.slots.catalog_candidates),
                has_patron_candidates=bool(agent_session.slots.patron_candidates),
                has_selected_copy_no_patron=(
                    agent_session.slots.holding_id is not None
                    and agent_session.slots.patron_id is None
                    and not agent_session.slots.guided_catalog_active
                ),
                ready_to_issue=agent_session.slots.has_patron_and_holding,
                has_pending_book_criteria_prompt=agent_session.slots.awaiting_book_criteria,
                has_pending_patron_prompt=agent_session.slots.awaiting_patron,
                has_pending_desk_patron=agent_session.slots.awaiting_desk_patron,
                has_pending_desk_next_action=agent_session.slots.awaiting_desk_next_action,
                has_pending_desk_return_pick=agent_session.slots.awaiting_desk_return_pick,
                has_pending_catalog_criteria=agent_session.slots.awaiting_catalog_criteria,
                has_pending_patron_lookup=agent_session.slots.awaiting_patron_lookup,
                has_guided_issue_context=(
                    agent_session.slots.guided_issue_active
                    and agent_session.slots.loan_id is None
                    and agent_session.pending_approval is None
                ),
                has_guided_return_context=(
                    agent_session.slots.guided_return_active
                    and agent_session.pending_approval is None
                ),
                has_guided_catalog_context=(
                    agent_session.slots.guided_catalog_active
                    and agent_session.pending_approval is None
                ),
                has_guided_patron_lookup_context=(
                    agent_session.slots.guided_patron_lookup_active
                    and agent_session.pending_approval is None
                ),
                trace_session_id=str(session_id),
                trace_operator_id=operator_id,
            )
            reply = self._apply_intent(
                agent_session,
                tools,
                return_tools,
                intent,
                user_message=message,
            )

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

        tools = self._issue_tools_for(agent_session)
        return_tools = self._return_tools_for(agent_session)
        with self._tracing.turn_span(
            session_id=str(session_id),
            operator_id=operator_id,
            agent_id=self.AGENT_ID,
            action="resume_approved" if approved else "resume_denied",
        ):
            self._tracing.hitl_event(
                session_id=str(session_id),
                operator_id=operator_id,
                agent_id=self.AGENT_ID,
                decision="approved" if approved else "denied",
                kind=pending.kind.value,
            )
            if not approved:
                kind = pending.kind
                agent_session.pending_approval = None
                return self._complete_turn(agent_session, desk.approval_denied(kind))

            result_msg = self._execute_pending(
                agent_session,
                tools,
                return_tools,
                pending,
                operator_id=operator_id,
            )
            agent_session.pending_approval = None
            return self._complete_turn(agent_session, result_msg)

    def _apply_intent(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        return_tools: ReturnTools,
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
                message = self._handle_search_catalog(agent_session, tools, intent, slots)
            case IntentAction.SELECT_CATALOG_COPY:
                message = self._run_tool(
                    agent_session,
                    "select_catalog_copy",
                    lambda: tools.select_catalog_copy(
                        slots,
                        holding_barcode=intent.holding_barcode,
                        title_query=intent.catalog_query,
                        copy_pseudonym=intent.copy_pseudonym,
                    ),
                ).message
            case IntentAction.SELECT_BARCODE:
                if slots.patron_id is None:
                    message = self._run_tool(
                        agent_session,
                        "select_catalog_copy",
                        lambda: tools.select_catalog_copy(
                            slots,
                            holding_barcode=intent.holding_barcode or "",
                        ),
                    ).message
                else:
                    message = self._run_tool(
                        agent_session,
                        "select_barcode",
                        lambda: tools.select_barcode(
                            slots,
                            intent.holding_barcode or "",
                            action=intent.action,
                        ),
                    ).message
            case IntentAction.ISSUE_TO_PATRON:
                return self._handle_issue_to_patron(
                    agent_session, tools, intent, slots, user_message=user_message
                )
            case IntentAction.START_ISSUE_TO_PATRON:
                return self._handle_start_issue_to_patron(
                    agent_session, tools, intent, slots
                )
            case IntentAction.PROVIDE_PATRON_FOR_ISSUE:
                return self._handle_provide_patron_for_issue(
                    agent_session, tools, intent, slots
                )
            case IntentAction.PROVIDE_BOOK_CRITERIA:
                return self._handle_provide_book_criteria(
                    agent_session, tools, intent, slots, user_message=user_message
                )
            case IntentAction.START_RETURN:
                return self._handle_start_return(
                    agent_session, tools, return_tools, intent, slots
                )
            case IntentAction.START_PATRON_DESK:
                return self._handle_start_patron_desk(
                    agent_session, tools, return_tools, intent, slots
                )
            case IntentAction.PROVIDE_PATRON_FOR_DESK:
                return self._handle_provide_patron_for_desk(
                    agent_session, tools, return_tools, intent, slots, user_message=user_message
                )
            case IntentAction.DESK_START_RETURN:
                return self._handle_desk_start_return(
                    agent_session, tools, return_tools, slots
                )
            case IntentAction.DESK_START_ISSUE:
                return self._handle_desk_start_issue(agent_session, slots)
            case IntentAction.DESK_START_CATALOG:
                return self._handle_desk_start_catalog(agent_session, slots)
            case IntentAction.DESK_SESSION_DONE:
                return self._handle_desk_session_done(agent_session, slots)
            case IntentAction.START_CATALOG_SEARCH:
                return self._handle_start_catalog_search(agent_session, slots)
            case IntentAction.PROVIDE_CATALOG_CRITERIA:
                return self._handle_provide_catalog_criteria(
                    agent_session, tools, intent, slots, user_message=user_message
                )
            case IntentAction.START_PATRON_LOOKUP:
                return self._handle_start_patron_lookup(agent_session, slots)
            case IntentAction.PROVIDE_PATRON_LOOKUP:
                return self._handle_provide_patron_lookup(
                    agent_session, tools, intent, slots
                )
            case IntentAction.SELECT_PATRON:
                message = self._run_tool(
                    agent_session,
                    "select_patron",
                    lambda: tools.select_patron(
                        slots,
                        patron_query=intent.patron_query,
                        card_barcode=intent.card_barcode,
                        external_ref=intent.external_ref,
                        patron_pseudonym=intent.patron_pseudonym,
                    ),
                ).message
            case IntentAction.DECLINE_CONTINUE:
                return self._handle_decline_continue(agent_session, slots)
            case IntentAction.SET_FULFILLMENT:
                message = desk.fulfillment_mode_set(slots.fulfillment_mode)
            case IntentAction.REQUEST_COMMIT:
                return self._handle_request_commit(agent_session, tools, intent, slots)
            case IntentAction.REQUEST_CANCEL_ISSUE:
                return self._request_cancel_approval(agent_session)
            case IntentAction.REQUEST_FULFILLMENT_TRANSITION:
                target = intent.fulfillment_status or FulfillmentStatus.IN_TRANSIT
                return self._request_fulfillment_approval(agent_session, tools, slots, target)
            case IntentAction.LOOKUP_RETURN:
                message = self._run_tool(
                    agent_session,
                    "lookup_return",
                    lambda: return_tools.lookup_return(
                        slots,
                        intent.holding_barcode or "",
                    ),
                ).message
            case IntentAction.SEARCH_RETURN:
                message = self._handle_search_return(agent_session, return_tools, intent, slots)
            case IntentAction.SELECT_RETURN_LOAN:
                return self._handle_select_return_loan(agent_session, return_tools, intent, slots)
            case IntentAction.REQUEST_COMMIT_RETURN:
                return self._request_return_commit_approval(agent_session)
            case IntentAction.REQUEST_RETURN_PICKUP:
                return self._request_return_pickup_approval(agent_session, intent)
            case IntentAction.CHAT:
                message = intent.reply_hint or desk.help_for_unknown_intent(user_message)
            case _:
                message = intent.reply_hint or desk.help_for_unknown_intent(user_message)

        return self._result(agent_session, message or desk.turn_acknowledged(user_message))

    def _handle_search_catalog(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        intent: ParsedIntent,
        slots: IssueSlots,
    ) -> str:
        query = intent.catalog_query or ""
        if slots.patron_id is None:
            return self._run_tool(
                agent_session,
                "search_catalog",
                lambda: tools.search_catalog(slots, query),
            ).message
        return self._run_tool(
            agent_session,
            "search_lendable",
            lambda: tools.search_lendable(slots, query, action=intent.action),
        ).message

    def _try_resolve_patron_query(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        slots: IssueSlots,
        patron_query: str,
    ) -> tuple[bool, str | None]:
        resolve = self._run_tool(
            agent_session,
            "resolve_patron",
            lambda: tools.resolve_patron(slots, display_name=patron_query),
        )
        if resolve.ok:
            return True, None
        matches = self._run_tool(
            agent_session,
            "search_patrons",
            lambda: tools.search_patrons(patron_query),
        )
        patrons_raw = matches.data.get("patrons", [])
        if isinstance(patrons_raw, list) and len(patrons_raw) == 1:
            pseudo = str(patrons_raw[0]["pseudonym"])
            patron_id = agent_session.pseudonyms.resolve_patron(pseudo)
            if patron_id is not None:
                resolve = self._run_tool(
                    agent_session,
                    "resolve_patron",
                    lambda: tools.resolve_patron(
                        slots,
                        patron_id=patron_id,
                        message_query=patron_query,
                    ),
                )
                if resolve.ok:
                    return True, None
        return False, resolve.message or matches.message

    def _handle_start_issue_to_patron(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        intent: ParsedIntent,
        slots: IssueSlots,
    ) -> AgentTurnResult:
        slots.active_flow = DeskFlow.ISSUE
        slots.guided_issue_active = True
        slots.catalog_candidates = []
        slots.holding_id = None
        slots.holding_barcode = None
        slots.catalog_title = None

        patron_query = intent.patron_query
        if not patron_query:
            slots.awaiting_patron = True
            slots.awaiting_book_criteria = False
            return self._result(agent_session, desk.guided_issue_ask_patron())

        slots.awaiting_patron = False
        slots.awaiting_book_criteria = True
        ok, err = self._try_resolve_patron_query(
            agent_session, tools, slots, patron_query
        )
        if not ok:
            slots.awaiting_book_criteria = False
            slots.guided_issue_active = False
            return self._result(agent_session, err or desk.patron_search_empty())

        return self._result(
            agent_session,
            desk.guided_issue_ask_book_criteria(patron_name=slots.patron_display_name),
        )

    def _handle_provide_patron_for_issue(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        intent: ParsedIntent,
        slots: IssueSlots,
    ) -> AgentTurnResult:
        if intent.card_barcode:
            resolve = self._run_tool(
                agent_session,
                "resolve_patron",
                lambda: tools.resolve_patron(slots, card_barcode=intent.card_barcode),
            )
            if not resolve.ok:
                return self._result(agent_session, resolve.message)
        elif intent.external_ref:
            resolve = self._run_tool(
                agent_session,
                "resolve_patron",
                lambda: tools.resolve_patron(slots, external_ref=intent.external_ref),
            )
            if not resolve.ok:
                return self._result(agent_session, resolve.message)
        elif intent.patron_query:
            ok, err = self._try_resolve_patron_query(
                agent_session, tools, slots, intent.patron_query
            )
            if not ok:
                return self._result(agent_session, err or desk.patron_search_empty())
        else:
            return self._result(agent_session, desk.guided_issue_ask_patron())

        slots.awaiting_patron = False
        slots.awaiting_book_criteria = True
        return self._result(
            agent_session,
            desk.guided_issue_ask_book_criteria(patron_name=slots.patron_display_name),
        )

    def _handle_provide_book_criteria(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        intent: ParsedIntent,
        slots: IssueSlots,
        *,
        user_message: str,
    ) -> AgentTurnResult:
        criteria = (intent.catalog_query or user_message).strip()
        if not criteria:
            return self._result(agent_session, desk.guided_issue_ask_book_criteria(
                patron_name=slots.patron_display_name
            ))

        result = self._run_tool(
            agent_session,
            "search_catalog",
            lambda: tools.search_catalog(slots, criteria),
        )
        if not result.ok:
            slots.awaiting_book_criteria = True
            return self._result(agent_session, desk.guided_issue_no_books_retry(criteria))
        return self._result(agent_session, result.message)

    def _handle_decline_continue(
        self,
        agent_session: AgentIssueSession,
        slots: IssueSlots,
    ) -> AgentTurnResult:
        if slots.guided_return_active or slots.awaiting_desk_patron:
            slots.awaiting_desk_patron = False
            slots.awaiting_desk_next_action = False
            slots.awaiting_desk_return_pick = False
            slots.desk_return_intent = False
            slots.guided_return_active = False
            slots.return_candidates = []
            return self._result(agent_session, desk.guided_desk_declined())
        if slots.guided_catalog_active or slots.awaiting_catalog_criteria:
            slots.awaiting_catalog_criteria = False
            slots.guided_catalog_active = False
            slots.catalog_candidates = []
            slots.holding_id = None
            slots.holding_barcode = None
            slots.catalog_title = None
            slots.issue_search_criteria = None
            return self._result(agent_session, desk.guided_catalog_declined())
        if slots.guided_patron_lookup_active or slots.awaiting_patron_lookup:
            slots.awaiting_patron_lookup = False
            slots.guided_patron_lookup_active = False
            slots.patron_candidates = []
            return self._result(agent_session, desk.guided_patron_lookup_declined())
        slots.awaiting_patron = False
        slots.awaiting_book_criteria = False
        slots.issue_search_criteria = None
        slots.guided_issue_active = False
        slots.catalog_candidates = []
        slots.holding_id = None
        slots.holding_barcode = None
        slots.catalog_title = None
        return self._result(agent_session, desk.guided_issue_declined())

    def _handle_start_return(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        return_tools: ReturnTools,
        intent: ParsedIntent,
        slots: IssueSlots,
    ) -> AgentTurnResult:
        slots.active_flow = DeskFlow.RETURN
        slots.guided_return_active = True
        slots.desk_return_intent = True
        slots.awaiting_desk_patron = False
        slots.awaiting_desk_next_action = False
        slots.awaiting_desk_return_pick = False
        slots.return_candidates = []
        slots.loan_id = None
        slots.holding_id = None
        slots.holding_barcode = None
        slots.catalog_title = None
        slots.due_date = None
        slots.is_overdue = None

        patron_query = intent.patron_query
        if patron_query and patron_query.strip().lower() in {"me", "myself"}:
            patron_query = None
        if not patron_query:
            slots.awaiting_desk_patron = True
            return self._result(agent_session, desk.guided_desk_ask_patron_for_return())
        return self._present_patron_at_desk(
            agent_session,
            tools,
            return_tools,
            slots,
            patron_query=patron_query,
        )

    def _handle_start_patron_desk(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        return_tools: ReturnTools,
        intent: ParsedIntent,
        slots: IssueSlots,
    ) -> AgentTurnResult:
        slots.active_flow = DeskFlow.RETURN
        slots.guided_return_active = True
        slots.desk_return_intent = False
        slots.awaiting_desk_patron = False
        slots.awaiting_desk_next_action = False
        slots.awaiting_desk_return_pick = False
        slots.return_candidates = []
        slots.loan_id = None
        slots.holding_id = None
        slots.holding_barcode = None
        slots.catalog_title = None
        slots.due_date = None
        slots.is_overdue = None

        patron_query = intent.patron_query
        if patron_query and patron_query.strip().lower() in {"me", "myself"}:
            patron_query = None
        if not patron_query:
            slots.awaiting_desk_patron = True
            return self._result(agent_session, desk.guided_desk_ask_patron())
        return self._present_patron_at_desk(
            agent_session,
            tools,
            return_tools,
            slots,
            patron_query=patron_query,
        )

    def _present_patron_at_desk(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        return_tools: ReturnTools,
        slots: IssueSlots,
        *,
        patron_query: str | None = None,
        card_barcode: str | None = None,
        external_ref: str | None = None,
        holding_barcode: str | None = None,
    ) -> AgentTurnResult:
        if holding_barcode:
            if slots.desk_return_intent:
                lookup = self._run_tool(
                    agent_session,
                    "lookup_return",
                    lambda: return_tools.lookup_return(slots, holding_barcode),
                )
                slots.awaiting_desk_patron = False
                slots.awaiting_desk_next_action = False
                slots.awaiting_desk_return_pick = False
                return self._result(agent_session, lookup.message)
            lookup = self._run_tool(
                agent_session,
                "lookup_return",
                lambda: return_tools.lookup_return(slots, holding_barcode),
            )
            if not lookup.ok:
                slots.awaiting_desk_patron = True
                return self._result(agent_session, lookup.message)
            slots.loan_id = None
            slots.holding_id = None
            slots.holding_barcode = None
            slots.catalog_title = None
            slots.due_date = None
            slots.is_overdue = None
            result = self._run_tool(
                agent_session,
                "list_patron_loans_at_desk",
                lambda: return_tools.list_patron_loans_at_desk(
                    slots, return_intent=slots.desk_return_intent
                ),
            )
        elif card_barcode or external_ref:
            result = self._run_tool(
                agent_session,
                "list_patron_loans_at_desk",
                lambda: return_tools.list_patron_loans_at_desk(
                    slots,
                    card_barcode=card_barcode,
                    external_ref=external_ref,
                    return_intent=slots.desk_return_intent,
                ),
            )
            if not result.ok:
                slots.awaiting_desk_patron = True
                return self._result(
                    agent_session,
                    desk.guided_desk_patron_not_found(card_barcode or external_ref or ""),
                )
        elif patron_query:
            ok, err = self._try_resolve_patron_query(
                agent_session, tools, slots, patron_query
            )
            if not ok:
                slots.awaiting_desk_patron = True
                return self._result(
                    agent_session,
                    err or desk.guided_desk_patron_not_found(patron_query),
                )
            result = self._run_tool(
                agent_session,
                "list_patron_loans_at_desk",
                lambda: return_tools.list_patron_loans_at_desk(
                    slots, return_intent=slots.desk_return_intent
                ),
            )
        else:
            slots.awaiting_desk_patron = True
            ask = (
                desk.guided_desk_ask_patron_for_return()
                if slots.desk_return_intent
                else desk.guided_desk_ask_patron()
            )
            return self._result(agent_session, ask)

        return self._finish_desk_list_present(agent_session, slots, result)

    def _finish_desk_list_present(
        self,
        agent_session: AgentIssueSession,
        slots: IssueSlots,
        result: ToolResult,
    ) -> AgentTurnResult:
        slots.awaiting_desk_patron = False
        data = result.data if result.ok else {}
        raw_count = data.get("count", 0)
        loan_count = raw_count if isinstance(raw_count, int) else 0
        if data.get("auto_selected") and data.get("return_intent"):
            slots.awaiting_desk_next_action = False
            slots.awaiting_desk_return_pick = False
        elif data.get("return_intent") and loan_count > 1:
            slots.awaiting_desk_return_pick = True
            slots.awaiting_desk_next_action = False
        else:
            slots.awaiting_desk_next_action = True
            slots.awaiting_desk_return_pick = False
        return self._result(agent_session, result.message)

    def _handle_desk_start_return(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        return_tools: ReturnTools,
        slots: IssueSlots,
    ) -> AgentTurnResult:
        slots.desk_return_intent = True
        slots.active_flow = DeskFlow.RETURN
        if slots.loan_id is not None and slots.due_date is not None:
            return self._result(
                agent_session,
                desk.return_single_candidate_ready(
                    slots.patron_display_name or "the patron",
                    slots.catalog_title or "copy",
                    slots.holding_barcode or "barcode",
                    due_date=slots.due_date,
                    is_overdue=bool(slots.is_overdue),
                ),
            )
        if slots.return_candidates:
            if len(slots.return_candidates) == 1 and slots.patron_id is not None:
                result = self._run_tool(
                    agent_session,
                    "list_patron_loans_at_desk",
                    lambda: return_tools.list_patron_loans_at_desk(
                        slots, return_intent=True
                    ),
                )
                return self._finish_desk_list_present(agent_session, slots, result)
            slots.awaiting_desk_return_pick = True
            slots.awaiting_desk_next_action = False
            patron_name = slots.patron_display_name or "the patron"
            return self._result(
                agent_session, desk.desk_return_pick_from_list(patron_name)
            )
        if slots.patron_id is not None:
            result = self._run_tool(
                agent_session,
                "list_patron_loans_at_desk",
                lambda: return_tools.list_patron_loans_at_desk(
                    slots, return_intent=True
                ),
            )
            return self._finish_desk_list_present(agent_session, slots, result)
        slots.awaiting_desk_patron = True
        slots.guided_return_active = True
        return self._result(agent_session, desk.guided_desk_ask_patron_for_return())

    def _handle_provide_patron_for_desk(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        return_tools: ReturnTools,
        intent: ParsedIntent,
        slots: IssueSlots,
        *,
        user_message: str,
    ) -> AgentTurnResult:
        if intent.card_barcode:
            return self._present_patron_at_desk(
                agent_session,
                tools,
                return_tools,
                slots,
                card_barcode=intent.card_barcode,
            )
        if intent.external_ref:
            return self._present_patron_at_desk(
                agent_session,
                tools,
                return_tools,
                slots,
                external_ref=intent.external_ref,
            )
        if intent.holding_barcode:
            return self._present_patron_at_desk(
                agent_session,
                tools,
                return_tools,
                slots,
                holding_barcode=intent.holding_barcode,
            )
        query = (intent.patron_query or user_message).strip()
        if not query:
            return self._result(agent_session, desk.guided_desk_ask_patron())
        return self._present_patron_at_desk(
            agent_session,
            tools,
            return_tools,
            slots,
            patron_query=query,
        )

    def _handle_desk_start_issue(
        self,
        agent_session: AgentIssueSession,
        slots: IssueSlots,
    ) -> AgentTurnResult:
        slots.active_flow = DeskFlow.ISSUE
        slots.guided_issue_active = True
        slots.awaiting_book_criteria = True
        slots.awaiting_desk_next_action = False
        slots.catalog_candidates = []
        slots.holding_id = None
        slots.holding_barcode = None
        slots.catalog_title = None
        return self._result(
            agent_session,
            desk.guided_issue_ask_book_criteria(patron_name=slots.patron_display_name),
        )

    def _handle_desk_start_catalog(
        self,
        agent_session: AgentIssueSession,
        slots: IssueSlots,
    ) -> AgentTurnResult:
        slots.guided_catalog_active = True
        slots.awaiting_catalog_criteria = True
        slots.awaiting_desk_next_action = False
        slots.catalog_candidates = []
        slots.holding_id = None
        slots.holding_barcode = None
        slots.catalog_title = None
        return self._result(agent_session, desk.guided_catalog_ask_criteria())

    def _handle_desk_session_done(
        self,
        agent_session: AgentIssueSession,
        slots: IssueSlots,
    ) -> AgentTurnResult:
        patron_name = slots.patron_display_name
        slots.guided_return_active = False
        slots.awaiting_desk_patron = False
        slots.awaiting_desk_next_action = False
        slots.awaiting_desk_return_pick = False
        slots.desk_return_intent = False
        slots.return_candidates = []
        slots.loan_id = None
        slots.holding_id = None
        slots.holding_barcode = None
        slots.catalog_title = None
        return self._result(agent_session, desk.desk_session_done(patron_name))

    def _resume_desk_after_subflow(
        self,
        agent_session: AgentIssueSession,
        return_tools: ReturnTools,
        slots: IssueSlots,
        *,
        lead_message: str,
    ) -> str:
        if not slots.guided_return_active or slots.patron_id is None:
            return lead_message
        refresh = self._run_tool(
            agent_session,
            "list_patron_loans_at_desk",
            lambda: return_tools.list_patron_loans_at_desk(slots),
        )
        slots.awaiting_desk_next_action = True
        slots.guided_issue_active = False
        slots.awaiting_book_criteria = False
        slots.guided_catalog_active = False
        slots.awaiting_catalog_criteria = False
        return f"{lead_message}\n\n{refresh.message}"

    def _handle_start_catalog_search(
        self,
        agent_session: AgentIssueSession,
        slots: IssueSlots,
    ) -> AgentTurnResult:
        slots.guided_catalog_active = True
        slots.awaiting_catalog_criteria = True
        slots.patron_id = None
        slots.patron_display_name = None
        slots.catalog_candidates = []
        slots.holding_id = None
        slots.holding_barcode = None
        slots.catalog_title = None
        slots.issue_search_criteria = None
        slots.guided_issue_active = False
        slots.awaiting_patron = False
        slots.awaiting_book_criteria = False
        return self._result(agent_session, desk.guided_catalog_ask_criteria())

    def _handle_provide_catalog_criteria(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        intent: ParsedIntent,
        slots: IssueSlots,
        *,
        user_message: str,
    ) -> AgentTurnResult:
        criteria = (intent.catalog_query or user_message).strip()
        if not criteria:
            return self._result(agent_session, desk.guided_catalog_ask_criteria())
        result = self._run_tool(
            agent_session,
            "search_catalog",
            lambda: tools.search_catalog(slots, criteria),
        )
        if not result.ok:
            slots.awaiting_catalog_criteria = True
            return self._result(agent_session, desk.guided_catalog_no_match_retry(criteria))
        if slots.guided_return_active and slots.patron_id is not None:
            slots.guided_catalog_active = False
            slots.awaiting_catalog_criteria = False
            slots.awaiting_desk_next_action = True
            patron_name = slots.patron_display_name or "the patron"
            message = (
                f"{result.message}\n\n"
                + desk.desk_next_actions_prompt(
                    patron_name=patron_name,
                    has_loans=bool(slots.return_candidates),
                )
            )
            return self._result(agent_session, message)
        return self._result(agent_session, result.message)

    def _handle_start_patron_lookup(
        self,
        agent_session: AgentIssueSession,
        slots: IssueSlots,
    ) -> AgentTurnResult:
        slots.guided_patron_lookup_active = True
        slots.awaiting_patron_lookup = True
        slots.patron_candidates = []
        slots.patron_id = None
        slots.patron_display_name = None
        return self._result(agent_session, desk.guided_patron_lookup_ask())

    def _handle_provide_patron_lookup(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        intent: ParsedIntent,
        slots: IssueSlots,
    ) -> AgentTurnResult:
        if intent.card_barcode:
            resolve = self._run_tool(
                agent_session,
                "resolve_patron",
                lambda: tools.resolve_patron(slots, card_barcode=intent.card_barcode),
            )
            if not resolve.ok:
                slots.awaiting_patron_lookup = True
                return self._result(agent_session, resolve.message)
            slots.awaiting_patron_lookup = False
            slots.guided_patron_lookup_active = False
            return self._result(
                agent_session,
                desk.guided_patron_found(
                    slots.patron_display_name or "patron",
                    card_barcode=intent.card_barcode,
                ),
            )
        if intent.external_ref:
            resolve = self._run_tool(
                agent_session,
                "resolve_patron",
                lambda: tools.resolve_patron(slots, external_ref=intent.external_ref),
            )
            if not resolve.ok:
                slots.awaiting_patron_lookup = True
                return self._result(agent_session, resolve.message)
            slots.awaiting_patron_lookup = False
            slots.guided_patron_lookup_active = False
            return self._result(
                agent_session,
                desk.guided_patron_found(
                    slots.patron_display_name or "patron",
                    external_ref=intent.external_ref,
                ),
            )
        if not intent.patron_query:
            return self._result(agent_session, desk.guided_patron_lookup_ask())

        patron_query = intent.patron_query
        resolve = self._run_tool(
            agent_session,
            "resolve_patron",
            lambda: tools.resolve_patron(slots, display_name=patron_query),
        )
        if resolve.ok:
            slots.awaiting_patron_lookup = False
            slots.guided_patron_lookup_active = False
            return self._result(
                agent_session,
                desk.guided_patron_found(
                    slots.patron_display_name or "patron",
                    query=patron_query,
                ),
            )
        matches = self._run_tool(
            agent_session,
            "search_patrons",
            lambda: tools.search_patrons(
                patron_query,
                slots=slots,
                guided_lookup=True,
            ),
        )
        if not matches.ok:
            slots.awaiting_patron_lookup = True
            return self._result(agent_session, matches.message)
        patrons_raw = matches.data.get("patrons", [])
        if isinstance(patrons_raw, list) and len(patrons_raw) == 1:
            pseudo = str(patrons_raw[0]["pseudonym"])
            patron_id = agent_session.pseudonyms.resolve_patron(pseudo)
            if patron_id is not None:
                resolve = self._run_tool(
                    agent_session,
                    "resolve_patron",
                    lambda: tools.resolve_patron(
                        slots,
                        patron_id=patron_id,
                        message_query=patron_query,
                    ),
                )
                if resolve.ok:
                    slots.awaiting_patron_lookup = False
                    slots.guided_patron_lookup_active = False
                    return self._result(
                        agent_session,
                        desk.guided_patron_found(
                            slots.patron_display_name or "patron",
                            query=patron_query,
                        ),
                    )
        slots.awaiting_patron_lookup = False
        return self._result(agent_session, matches.message)

    def _handle_issue_to_patron(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        intent: ParsedIntent,
        slots: IssueSlots,
        *,
        user_message: str,
    ) -> AgentTurnResult:
        if slots.holding_id is None:
            return self._result(
                agent_session,
                desk.missing_copy_for(IntentAction.ISSUE_TO_PATRON),
            )
        patron_query = intent.patron_query
        if not patron_query:
            return self._result(agent_session, desk.patron_search_empty())

        resolve = self._run_tool(
            agent_session,
            "resolve_patron",
            lambda: tools.resolve_patron(slots, display_name=patron_query),
        )
        if not resolve.ok:
            matches = self._run_tool(
                agent_session,
                "search_patrons",
                lambda: tools.search_patrons(patron_query),
            )
            patrons_raw = matches.data.get("patrons", [])
            if isinstance(patrons_raw, list) and len(patrons_raw) == 1:
                pseudo = str(patrons_raw[0]["pseudonym"])
                patron_id = agent_session.pseudonyms.resolve_patron(pseudo)
                if patron_id is not None:
                    resolve = self._run_tool(
                        agent_session,
                        "resolve_patron",
                        lambda: tools.resolve_patron(
                            slots,
                            patron_id=patron_id,
                            message_query=patron_query,
                        ),
                    )
            if not resolve.ok:
                return self._result(agent_session, resolve.message or matches.message)

        validation = self._run_tool(
            agent_session,
            "validate_issue",
            lambda: tools.validate_issue(slots, action=IntentAction.REQUEST_COMMIT),
        )
        if not validation.ok:
            return self._result(agent_session, validation.message)

        explicit_issue = bool(
            re.search(r"\b(?:issue|lend|checkout)\s+(?:it\s+)?to\b", user_message, re.I)
        )
        if explicit_issue:
            return self._request_commit_approval(agent_session)

        return self._result(
            agent_session,
            desk.issue_patron_resolved_ready(
                slots.patron_display_name or "patron",
                slots.catalog_title or "copy",
                slots.holding_barcode or "barcode",
                mode=slots.fulfillment_mode,
            ),
        )

    def _handle_search_return(
        self,
        agent_session: AgentIssueSession,
        return_tools: ReturnTools,
        intent: ParsedIntent,
        slots: IssueSlots,
    ) -> str:
        return self._run_tool(
            agent_session,
            "search_return_loans",
            lambda: return_tools.search_return_loans(
                slots,
                patron_query=intent.patron_query,
                card_barcode=intent.card_barcode,
                external_ref=intent.external_ref,
                title_query=intent.catalog_query,
            ),
        ).message

    def _handle_select_return_loan(
        self,
        agent_session: AgentIssueSession,
        return_tools: ReturnTools,
        intent: ParsedIntent,
        slots: IssueSlots,
    ) -> AgentTurnResult:
        selection = self._run_tool(
            agent_session,
            "select_return_loan",
            lambda: return_tools.select_return_loan(
                slots,
                holding_barcode=intent.holding_barcode,
                title_query=intent.catalog_query,
                loan_pseudonym=intent.loan_pseudonym,
            ),
        )
        if not selection.ok:
            return self._result(agent_session, selection.message)
        slots.awaiting_desk_return_pick = False
        candidate_raw = selection.data.get("candidate")
        if not isinstance(candidate_raw, dict):
            return self._result(agent_session, selection.message)
        return self._request_return_select_approval(
            agent_session,
            candidate_raw,
            summary=selection.message,
        )

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

    def _request_return_commit_approval(self, agent_session: AgentIssueSession) -> AgentTurnResult:
        slots = agent_session.slots
        if slots.loan_id is None:
            return self._result(agent_session, desk.missing_loan_for_return())

        summary = desk.return_commit_approval_summary(
            slots.patron_display_name or "patron",
            slots.catalog_title or "copy",
            slots.holding_barcode or "barcode",
        )
        self._set_pending_approval(
            agent_session,
            kind=PendingActionKind.COMMIT_RETURN,
            summary=summary,
            details={
                "patron_display_name": slots.patron_display_name,
                "catalog_title": slots.catalog_title,
                "holding_barcode": slots.holding_barcode,
            },
        )
        return self._result(
            agent_session,
            desk.return_commit_approval_prompt(summary),
            pending=self._pending_payload(agent_session.pending_approval),
        )

    def _request_return_pickup_approval(
        self,
        agent_session: AgentIssueSession,
        intent: ParsedIntent,
    ) -> AgentTurnResult:
        slots = agent_session.slots
        if slots.loan_id is None:
            return self._result(agent_session, desk.missing_loan_for_return())
        if intent.destination_notes:
            slots.destination_notes = intent.destination_notes

        summary = desk.return_pickup_approval_summary(
            slots.patron_display_name or "patron",
            slots.catalog_title or "copy",
            slots.holding_barcode or "barcode",
        )
        self._set_pending_approval(
            agent_session,
            kind=PendingActionKind.INITIATE_RETURN_PICKUP,
            summary=summary,
            details={
                "patron_display_name": slots.patron_display_name,
                "catalog_title": slots.catalog_title,
                "holding_barcode": slots.holding_barcode,
                "destination_notes": slots.destination_notes,
            },
        )
        return self._result(
            agent_session,
            desk.return_pickup_approval_prompt(summary),
            pending=self._pending_payload(agent_session.pending_approval),
        )

    def _request_return_select_approval(
        self,
        agent_session: AgentIssueSession,
        candidate: dict[str, object],
        *,
        summary: str,
    ) -> AgentTurnResult:
        self._set_pending_approval(
            agent_session,
            kind=PendingActionKind.SELECT_RETURN,
            summary=summary,
            details={"candidate": candidate},
        )
        return self._result(
            agent_session,
            desk.return_select_approval_prompt(summary),
            pending=self._pending_payload(agent_session.pending_approval),
        )

    def _execute_pending(
        self,
        agent_session: AgentIssueSession,
        tools: IssueTools,
        return_tools: ReturnTools,
        pending: PendingApproval,
        *,
        operator_id: str,
    ) -> str:
        slots = agent_session.slots
        if pending.kind == PendingActionKind.COMMIT_ISSUE:
            msg = self._run_tool(
                agent_session,
                "commit_issue",
                lambda: tools.commit_issue(
                    slots,
                    idempotency_key=pending.idempotency_key,
                    operator_id=operator_id,
                ),
            ).message
            if slots.guided_return_active:
                return self._resume_desk_after_subflow(
                    agent_session, return_tools, slots, lead_message=msg
                )
            slots.guided_issue_active = False
            slots.awaiting_patron = False
            slots.awaiting_book_criteria = False
            return msg
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
        if pending.kind == PendingActionKind.SELECT_RETURN:
            candidate_raw = pending.details.get("candidate")
            if not isinstance(candidate_raw, dict):
                raise AppError(
                    ErrorCode.RETRIABLE_ERROR,
                    "Missing return selection details",
                    status_code=500,
                )
            return self._run_tool(
                agent_session,
                "apply_return_selection",
                lambda: return_tools.apply_return_selection(slots, candidate_raw),
            ).message
        if pending.kind == PendingActionKind.COMMIT_RETURN:
            desk_patron_id = slots.patron_id
            desk_patron_name = slots.patron_display_name
            desk_active = slots.guided_return_active
            msg = self._run_tool(
                agent_session,
                "commit_desk_return",
                lambda: return_tools.commit_desk_return(
                    slots,
                    idempotency_key=pending.idempotency_key,
                ),
            ).message
            if desk_active and desk_patron_id is not None:
                slots.patron_id = desk_patron_id
                slots.patron_display_name = desk_patron_name
                slots.guided_return_active = True
                return self._resume_desk_after_subflow(
                    agent_session, return_tools, slots, lead_message=msg
                )
            slots.guided_return_active = False
            slots.awaiting_desk_patron = False
            slots.awaiting_desk_next_action = False
            return msg
        if pending.kind == PendingActionKind.INITIATE_RETURN_PICKUP:
            return self._run_tool(
                agent_session,
                "initiate_return_pickup",
                lambda: return_tools.initiate_return_pickup(
                    slots,
                    idempotency_key=pending.idempotency_key,
                    destination_notes=slots.destination_notes,
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

    def _issue_tools_for(self, agent_session: AgentIssueSession) -> IssueTools:
        return IssueTools(
            self._db,
            self._workflow,
            self._fulfillment,
            agent_session.pseudonyms,
        )

    def _return_tools_for(self, agent_session: AgentIssueSession) -> ReturnTools:
        return ReturnTools(
            self._db,
            self._return_workflow,
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
            "details": sanitize_approval_details(pending.details),
        }

    def session_summary(self, agent_session: AgentIssueSession) -> dict[str, Any]:
        return self._session_summary(agent_session)

    def _session_summary(self, agent_session: AgentIssueSession) -> dict[str, Any]:
        slots = agent_session.slots
        summary: dict[str, Any] = {
            "active_flow": slots.active_flow.value,
            "patron_display_name": slots.patron_display_name,
            "catalog_title": slots.catalog_title,
            "holding_barcode": slots.holding_barcode,
            "fulfillment_mode": slots.fulfillment_mode.value,
            "has_pending_approval": agent_session.pending_approval is not None,
        }
        if slots.due_date is not None:
            summary["due_date"] = slots.due_date.isoformat()
        if slots.is_overdue is not None:
            summary["is_overdue"] = slots.is_overdue
        if slots.return_candidates:
            summary["return_candidate_count"] = len(slots.return_candidates)
        if slots.catalog_candidates:
            summary["catalog_candidate_count"] = len(slots.catalog_candidates)
        if slots.awaiting_patron:
            summary["awaiting_patron"] = True
        if slots.awaiting_book_criteria:
            summary["awaiting_book_criteria"] = True
        if slots.issue_search_criteria:
            summary["issue_search_criteria"] = slots.issue_search_criteria
        if slots.guided_issue_active:
            summary["guided_issue_active"] = True
        if slots.guided_return_active:
            summary["guided_return_active"] = True
        if slots.guided_catalog_active:
            summary["guided_catalog_active"] = True
        if slots.guided_patron_lookup_active:
            summary["guided_patron_lookup_active"] = True
        if slots.awaiting_desk_patron:
            summary["awaiting_desk_patron"] = True
        if slots.awaiting_desk_next_action:
            summary["awaiting_desk_next_action"] = True
        if slots.awaiting_desk_return_pick:
            summary["awaiting_desk_return_pick"] = True
        if slots.desk_return_intent:
            summary["desk_return_intent"] = True
        if slots.awaiting_catalog_criteria:
            summary["awaiting_catalog_criteria"] = True
        if slots.awaiting_patron_lookup:
            summary["awaiting_patron_lookup"] = True
        if slots.patron_candidates:
            summary["patron_candidate_count"] = len(slots.patron_candidates)
        return summary

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
