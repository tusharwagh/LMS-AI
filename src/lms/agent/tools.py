"""Allowlisted tools wrapping workflow services (ADR-025)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from lms.agent import messages as desk
from lms.agent.masking import PseudonymMap
from lms.agent.schemas import IntentAction
from lms.agent.session import DeskFlow, IssueSlots
from lms.api.workflows.return_book import ReturnBookWorkflow, ReturnCandidate
from lms.api.workflows.search_and_issue import CatalogLendableCopy, SearchAndIssueWorkflow
from lms.loan.application.fulfillment_service import FulfillmentService
from lms.loan.domain.enums import FulfillmentStatus
from lms.loan.domain.validation import ValidationReport
from lms.shared.http.errors import AppError
from lms.shared.privacy.redaction import redact_for_audit

READ_TOOL_NAMES = frozenset(
    {
        "search_patrons",
        "resolve_patron",
        "search_lendable",
        "search_catalog",
        "select_catalog_copy",
        "select_patron",
        "select_barcode",
        "validate_issue",
        "get_fulfillment_status",
        "lookup_return",
        "search_return_loans",
        "list_patron_loans_at_desk",
        "select_return_loan",
    }
)
WRITE_TOOL_NAMES = frozenset(
    {
        "commit_issue",
        "transition_fulfillment",
        "cancel_issue",
        "commit_desk_return",
        "initiate_return_pickup",
        "apply_return_selection",
    }
)
AUTHORIZED_TOOL_NAMES = READ_TOOL_NAMES | WRITE_TOOL_NAMES
RESTRICTED_TOOL_NAMES = frozenset(
    {
        "direct_checkout",
        "direct_db",
        "admin_api",
        "remote_mcp",
    }
)


@dataclass(frozen=True, slots=True)
class CompactPatron:
    pseudonym: str
    display_name: str
    external_ref: str | None
    card_barcode: str | None


@dataclass(frozen=True, slots=True)
class CompactCopy:
    pseudonym: str
    barcode: str
    title: str
    shelf_location: str | None


@dataclass(frozen=True, slots=True)
class ToolResult:
    ok: bool
    message: str
    data: dict[str, object]


class IssueTools:
    def __init__(
        self,
        session: Session,
        workflow: SearchAndIssueWorkflow,
        fulfillment: FulfillmentService,
        pseudonyms: PseudonymMap,
    ) -> None:
        self._session = session
        self._workflow = workflow
        self._fulfillment = fulfillment
        self._pseudonyms = pseudonyms

    def search_patrons(
        self,
        query: str,
        *,
        limit: int = 5,
        slots: IssueSlots | None = None,
        guided_lookup: bool = False,
    ) -> ToolResult:
        patrons = self._workflow.search_patrons(query, limit=limit)
        items = [
            CompactPatron(
                pseudonym=self._pseudonyms.patron(p.id, p.display_name),
                display_name=p.display_name,
                external_ref=p.external_ref,
                card_barcode=p.card_barcode,
            )
            for p in patrons
        ]
        if not items:
            if guided_lookup:
                return ToolResult(
                    False,
                    desk.guided_patron_lookup_retry(redact_for_audit(query)),
                    {},
                )
            return ToolResult(
                False,
                desk.no_patron_found(redact_for_audit(query)),
                {},
            )
        if guided_lookup and len(items) > 1 and slots is not None:
            slots.patron_candidates = [asdict(i) for i in items]
            lines = [
                (i.pseudonym, i.display_name, i.card_barcode, i.external_ref)
                for i in items
            ]
            msg = desk.guided_patron_lookup_candidates_list(
                lines,
                query=redact_for_audit(query),
            )
            return ToolResult(
                True,
                msg,
                {"patrons": [asdict(i) for i in items], "count": len(items)},
            )
        if len(items) == 1:
            msg = desk.patron_eligible(items[0].display_name, query=redact_for_audit(query))
        else:
            msg = desk.patron_search_results(
                redact_for_audit(query),
                len(items),
                [i.display_name for i in items],
            )
        return ToolResult(True, msg, {"patrons": [asdict(i) for i in items]})

    def resolve_patron(
        self,
        slots: IssueSlots,
        *,
        patron_id: UUID | None = None,
        card_barcode: str | None = None,
        external_ref: str | None = None,
        display_name: str | None = None,
        message_query: str | None = None,
    ) -> ToolResult:
        try:
            result = self._workflow.start(
                patron_id=patron_id,
                card_barcode=card_barcode,
                external_ref=external_ref,
                display_name=display_name,
            )
        except AppError as exc:
            query_hint = display_name or card_barcode or external_ref or "patron"
            return ToolResult(False, desk.no_patron_found(str(query_hint)), {"error": exc.message})
        slots.patron_id = result.patron_id
        slots.patron_display_name = result.patron_display_name
        pseudo = self._pseudonyms.patron(result.patron_id, result.patron_display_name)
        violations = [v.message for v in result.patron_validation.violations]
        if violations:
            return ToolResult(
                False,
                desk.patron_cannot_borrow(
                    result.patron_display_name,
                    "; ".join(violations),
                ),
                {"patron_pseudonym": pseudo},
            )
        eligibility_query = message_query or display_name or card_barcode or external_ref
        return ToolResult(
            True,
            desk.patron_eligible(
                result.patron_display_name,
                query=redact_for_audit(eligibility_query) if eligibility_query else None,
            ),
            {"patron_pseudonym": pseudo},
        )

    def search_catalog(self, slots: IssueSlots, query: str) -> ToolResult:
        browse_only = slots.guided_catalog_active
        if not browse_only:
            slots.active_flow = DeskFlow.ISSUE
        slots.issue_search_criteria = query
        copies = self._workflow.search_catalog_lendable(query)
        slots.catalog_candidates = [self._catalog_copy_dict(c) for c in copies]
        if not copies:
            if browse_only:
                slots.awaiting_catalog_criteria = True
                return ToolResult(False, desk.guided_catalog_no_match_retry(query), {})
            slots.awaiting_book_criteria = True
            return ToolResult(False, desk.no_lendable_copies(query), {})
        if browse_only:
            slots.awaiting_catalog_criteria = False
        else:
            slots.awaiting_book_criteria = False
        if len(copies) == 1:
            self._apply_catalog_copy(slots, copies[0])
            slots.catalog_candidates = []
            only = copies[0]
            if browse_only:
                msg = desk.catalog_browse_single_copy(
                    only.catalog_title,
                    only.holding_barcode,
                    query,
                    shelf=only.shelf_location,
                )
            else:
                msg = self._catalog_copy_ready_message(slots, only, query, selected_from_list=False)
            return ToolResult(True, msg, {"count": 1, "auto_selected": True})
        items = [self._catalog_copy_line(c) for c in copies]
        if browse_only:
            msg = desk.catalog_browse_candidates_list(items, query=query)
        else:
            msg = desk.catalog_candidates_list(items, query=query)
        return ToolResult(
            True,
            msg,
            {"count": len(copies), "candidates": slots.catalog_candidates},
        )

    def select_catalog_copy(
        self,
        slots: IssueSlots,
        *,
        holding_barcode: str | None = None,
        title_query: str | None = None,
        copy_pseudonym: str | None = None,
    ) -> ToolResult:
        if not slots.catalog_candidates:
            if holding_barcode:
                return self._select_catalog_copy_by_barcode(slots, holding_barcode)
            return ToolResult(
                False,
                desk.catalog_selection_not_found(title_query or holding_barcode or ""),
                {},
            )
        candidates = [self._catalog_copy_from_dict(row) for row in slots.catalog_candidates]
        matches = self._filter_catalog_candidates(
            candidates,
            holding_barcode=holding_barcode,
            title_query=title_query,
            copy_pseudonym=copy_pseudonym,
        )
        hint = holding_barcode or title_query or copy_pseudonym or ""
        if not matches:
            return ToolResult(False, desk.catalog_selection_not_found(hint), {})
        if len(matches) > 1:
            slots.catalog_candidates = [self._catalog_copy_dict(c) for c in matches]
            items = [self._catalog_copy_line(c) for c in matches]
            list_msg = (
                desk.catalog_browse_candidates_list(items, query=hint)
                if slots.guided_catalog_active
                else desk.catalog_candidates_list(items, query=hint)
            )
            return ToolResult(
                False,
                list_msg,
                {"count": len(matches)},
            )
        copy = matches[0]
        self._apply_catalog_copy(slots, copy)
        slots.catalog_candidates = []
        slots.awaiting_book_criteria = False
        slots.awaiting_catalog_criteria = False
        if slots.guided_catalog_active:
            msg = desk.catalog_browse_copy_selected(copy.catalog_title, copy.holding_barcode)
        else:
            msg = self._catalog_copy_ready_message(
                slots, copy, title_query or holding_barcode or "", selected_from_list=True
            )
        return ToolResult(
            True,
            msg,
            {"copy_pseudonym": self._pseudonyms.holding(copy.holding_id, copy.holding_barcode)},
        )

    def select_patron(
        self,
        slots: IssueSlots,
        *,
        patron_query: str | None = None,
        card_barcode: str | None = None,
        external_ref: str | None = None,
        patron_pseudonym: str | None = None,
    ) -> ToolResult:
        if not slots.patron_candidates:
            return ToolResult(
                False,
                desk.patron_selection_not_found(
                    patron_query or card_barcode or external_ref or patron_pseudonym or ""
                ),
                {},
            )
        candidates = [self._patron_from_dict(row) for row in slots.patron_candidates]
        matches = self._filter_patron_candidates(
            candidates,
            patron_query=patron_query,
            card_barcode=card_barcode,
            external_ref=external_ref,
            patron_pseudonym=patron_pseudonym,
        )
        hint = patron_query or card_barcode or external_ref or patron_pseudonym or ""
        if not matches:
            return ToolResult(False, desk.patron_selection_not_found(hint), {})
        if len(matches) > 1:
            slots.patron_candidates = [asdict(m) for m in matches]
            lines = [
                (m.pseudonym, m.display_name, m.card_barcode, m.external_ref)
                for m in matches
            ]
            return ToolResult(
                False,
                desk.guided_patron_lookup_candidates_list(lines, query=hint),
                {"count": len(matches)},
            )
        patron = matches[0]
        patron_id = self._pseudonyms.resolve_patron(patron.pseudonym)
        if patron_id is None:
            return ToolResult(False, desk.patron_selection_not_found(hint), {})
        result = self._workflow.start(patron_id=patron_id)
        slots.patron_id = result.patron_id
        slots.patron_display_name = result.patron_display_name
        slots.patron_candidates = []
        slots.awaiting_patron_lookup = False
        violations = [v.message for v in result.patron_validation.violations]
        if violations:
            return ToolResult(
                False,
                desk.patron_cannot_borrow(
                    result.patron_display_name,
                    "; ".join(violations),
                ),
                {"patron_pseudonym": patron.pseudonym},
            )
        return ToolResult(
            True,
            desk.guided_patron_found(
                result.patron_display_name,
                card_barcode=patron.card_barcode,
                external_ref=patron.external_ref,
                query=hint if patron_query else None,
            ),
            {"patron_pseudonym": patron.pseudonym},
        )

    def search_lendable(
        self,
        slots: IssueSlots,
        query: str,
        *,
        action: IntentAction = IntentAction.SEARCH_CATALOG,
    ) -> ToolResult:
        patron_id = self._patron_id(slots, action)
        if isinstance(patron_id, ToolResult):
            return patron_id
        result = self._workflow.start(patron_id=patron_id, search_query=query)
        copies: list[CompactCopy] = []
        for hit in result.search_results:
            title = str(hit["title"])
            for copy in hit["lendable_copies"]:
                hid = UUID(str(copy["holding_id"]))
                copies.append(
                    CompactCopy(
                        pseudonym=self._pseudonyms.holding(hid, str(copy["barcode"])),
                        barcode=str(copy["barcode"]),
                        title=title,
                        shelf_location=copy.get("shelf_location"),
                    )
                )
        if not copies:
            return ToolResult(False, desk.no_lendable_copies(query), {})
        if len(copies) == 1:
            only = copies[0]
            resolved_hid = self._resolve_holding_id(only.pseudonym)
            if resolved_hid is not None:
                slots.holding_id = resolved_hid
                slots.holding_barcode = only.barcode
                slots.catalog_title = only.title
            msg = desk.single_copy_for_issue(only.title, only.barcode, query)
        else:
            msg = desk.catalog_search_results(
                query,
                len(copies),
                [c.title for c in copies[:5]],
            )
        return ToolResult(True, msg, {"copies": [asdict(c) for c in copies[:5]]})

    def select_barcode(
        self,
        slots: IssueSlots,
        barcode: str,
        *,
        action: IntentAction = IntentAction.SELECT_BARCODE,
    ) -> ToolResult:
        patron_id = self._patron_id(slots, action)
        if isinstance(patron_id, ToolResult):
            return patron_id
        try:
            result = self._workflow.find_lendable_copy_by_barcode(patron_id, barcode)
        except AppError as exc:
            return ToolResult(
                False,
                desk.barcode_not_available(barcode, exc.message),
                {},
            )
        hit = result.search_results[0]
        copy = hit["lendable_copies"][0]
        hid = UUID(str(copy["holding_id"]))
        slots.holding_id = hid
        slots.holding_barcode = str(copy["barcode"])
        slots.catalog_title = str(hit["title"])
        pseudo = self._pseudonyms.holding(hid, slots.holding_barcode)
        return ToolResult(
            True,
            desk.copy_selected(
                slots.catalog_title or "copy",
                slots.holding_barcode or barcode,
                scanned=barcode,
            ),
            {"copy_pseudonym": pseudo},
        )

    def validate_issue(
        self,
        slots: IssueSlots,
        *,
        action: IntentAction = IntentAction.REQUEST_COMMIT,
    ) -> ToolResult:
        pair = self._patron_and_holding(slots, action)
        if isinstance(pair, ToolResult):
            return pair
        patron_id, holding_id = pair
        report = self._workflow.validate(patron_id, holding_id)
        return self._validation_result(report, slots)

    def commit_issue(
        self,
        slots: IssueSlots,
        *,
        idempotency_key: str,
        operator_id: str | None,
    ) -> ToolResult:
        pair = self._patron_and_holding(slots, IntentAction.REQUEST_COMMIT)
        if isinstance(pair, ToolResult):
            return pair
        patron_id, holding_id = pair
        result = self._workflow.commit(
            patron_id,
            holding_id,
            fulfillment_mode=slots.fulfillment_mode,
            destination_notes=slots.destination_notes,
            idempotency_key=idempotency_key,
            operator_id=operator_id,
        )
        self._session.commit()
        slots.loan_id = result.loan.id
        if result.fulfillment is not None:
            slots.fulfillment_id = result.fulfillment.id
        loan_label = self._pseudonyms.loan(result.loan.id)
        delivery_status: str | None = None
        if result.fulfillment is not None:
            delivery_status = str(result.fulfillment.status).lower().replace("_", " ")
        msg = desk.issue_committed(
            slots.patron_display_name or "patron",
            slots.catalog_title or "copy",
            slots.holding_barcode or "barcode",
            delivery_status=delivery_status,
        )
        return ToolResult(True, msg, {"loan_pseudonym": loan_label})

    def get_fulfillment_status(self, slots: IssueSlots) -> ToolResult:
        fid = slots.fulfillment_id
        if fid is None and slots.loan_id is not None:
            row = self._fulfillment.get_issue_fulfillment_for_loan(slots.loan_id)
            if row is not None:
                fid = row.id
                slots.fulfillment_id = fid
        if fid is None:
            return ToolResult(False, desk.no_fulfillment_for_transition(), {})
        row = self._fulfillment.get_fulfillment(fid)
        status_label = str(row.status).lower().replace("_", " ")
        pseudo = self._pseudonyms.fulfillment(row.id)
        return ToolResult(
            True,
            desk.delivery_status_check(status_label, title=slots.catalog_title),
            {"fulfillment_pseudonym": pseudo, "status": str(row.status)},
        )

    def transition_fulfillment(
        self,
        slots: IssueSlots,
        target_status: FulfillmentStatus,
        *,
        idempotency_key: str,
    ) -> ToolResult:
        if slots.fulfillment_id is None:
            return ToolResult(False, desk.no_fulfillment_for_transition(), {})
        row = self._fulfillment.transition(
            slots.fulfillment_id,
            target_status,
            idempotency_key=idempotency_key,
        )
        self._session.commit()
        status_label = str(row.status).lower().replace("_", " ")
        return ToolResult(
            True,
            desk.delivery_updated(status_label, title=slots.catalog_title),
            {},
        )

    def cancel_issue(
        self,
        slots: IssueSlots,
        *,
        idempotency_key: str,
    ) -> ToolResult:
        if slots.loan_id is None:
            return ToolResult(False, desk.no_open_loan_for_cancel(), {})
        result = self._workflow.cancel_issue(slots.loan_id, idempotency_key=idempotency_key)
        self._session.commit()
        loan_label = self._pseudonyms.loan(result.loan.id)
        slots.loan_id = None
        slots.fulfillment_id = None
        slots.fulfillment_target_status = None
        msg = desk.issue_cancelled(
            slots.patron_display_name or "patron",
            slots.catalog_title or "copy",
            slots.holding_barcode or "barcode",
        )
        if result.fulfillment_cancelled:
            msg += " The delivery request was cancelled too."
        return ToolResult(True, msg, {"loan_pseudonym": loan_label})

    def _validation_result(self, report: ValidationReport, slots: IssueSlots) -> ToolResult:
        if report.is_valid:
            if slots.patron_display_name and slots.catalog_title and slots.holding_barcode:
                msg = desk.issue_ready(
                    slots.patron_display_name,
                    slots.catalog_title,
                    slots.holding_barcode,
                )
            else:
                msg = desk.ready_to_issue()
            return ToolResult(True, msg, {"valid": True})
        msgs = [v.message for v in report.violations]
        return ToolResult(
            False,
            desk.issue_blocked_for_commit("; ".join(msgs)),
            {"valid": False, "violations": msgs},
        )

    def _patron_id(self, slots: IssueSlots, action: IntentAction) -> UUID | ToolResult:
        if slots.patron_id is None:
            return ToolResult(False, desk.missing_patron_for(action), {})
        return slots.patron_id

    def _holding_id(self, slots: IssueSlots, action: IntentAction) -> UUID | ToolResult:
        if slots.holding_id is None:
            return ToolResult(False, desk.missing_copy_for(action), {})
        return slots.holding_id

    def _patron_and_holding(
        self,
        slots: IssueSlots,
        action: IntentAction,
    ) -> tuple[UUID, UUID] | ToolResult:
        patron_id = self._patron_id(slots, action)
        if isinstance(patron_id, ToolResult):
            return patron_id
        holding_id = self._holding_id(slots, action)
        if isinstance(holding_id, ToolResult):
            return holding_id
        return patron_id, holding_id

    def _resolve_holding_id(self, pseudonym: str) -> UUID | None:
        return self._pseudonyms.resolve_holding(pseudonym)

    def _select_catalog_copy_by_barcode(self, slots: IssueSlots, barcode: str) -> ToolResult:
        try:
            copies = self._workflow.search_catalog_lendable(barcode, limit=5)
        except AppError as exc:
            return ToolResult(False, desk.barcode_not_available(barcode, exc.message), {})
        needle = barcode.strip().lower()
        matches = [c for c in copies if c.holding_barcode.lower() == needle]
        if not matches:
            return ToolResult(False, desk.catalog_selection_not_found(barcode), {})
        copy = matches[0]
        self._apply_catalog_copy(slots, copy)
        slots.catalog_candidates = []
        slots.awaiting_book_criteria = False
        return ToolResult(
            True,
            self._catalog_copy_ready_message(slots, copy, barcode, selected_from_list=True),
            {},
        )

    def _catalog_copy_ready_message(
        self,
        slots: IssueSlots,
        copy: CatalogLendableCopy,
        query: str,
        *,
        selected_from_list: bool = False,
    ) -> str:
        if slots.guided_catalog_active:
            if selected_from_list:
                return desk.catalog_browse_copy_selected(copy.catalog_title, copy.holding_barcode)
            return desk.catalog_browse_single_copy(
                copy.catalog_title,
                copy.holding_barcode,
                query,
                shelf=copy.shelf_location,
            )
        if slots.patron_id and slots.patron_display_name:
            return desk.issue_patron_resolved_ready(
                slots.patron_display_name,
                copy.catalog_title,
                copy.holding_barcode,
                mode=slots.fulfillment_mode,
            )
        if selected_from_list:
            return desk.catalog_copy_selected_ask_patron(copy.catalog_title, copy.holding_barcode)
        return desk.catalog_single_copy_ask_issue(
            copy.catalog_title,
            copy.holding_barcode,
            query,
            shelf=copy.shelf_location,
        )

    def _apply_catalog_copy(self, slots: IssueSlots, copy: CatalogLendableCopy) -> None:
        slots.holding_id = copy.holding_id
        slots.holding_barcode = copy.holding_barcode
        slots.catalog_title = copy.catalog_title
        self._pseudonyms.holding(copy.holding_id, copy.holding_barcode)

    def _catalog_copy_dict(self, copy: CatalogLendableCopy) -> dict[str, object]:
        pseudo = self._pseudonyms.holding(copy.holding_id, copy.holding_barcode)
        return {
            "holding_id": str(copy.holding_id),
            "copy_pseudonym": pseudo,
            "holding_barcode": copy.holding_barcode,
            "catalog_title": copy.catalog_title,
            "shelf_location": copy.shelf_location,
        }

    def _catalog_copy_from_dict(self, row: dict[str, object]) -> CatalogLendableCopy:
        return CatalogLendableCopy(
            holding_id=UUID(str(row["holding_id"])),
            holding_barcode=str(row["holding_barcode"]),
            catalog_title=str(row["catalog_title"]),
            shelf_location=str(row["shelf_location"]) if row.get("shelf_location") else None,
        )

    def _catalog_copy_line(
        self, copy: CatalogLendableCopy
    ) -> tuple[str, str, str, str | None]:
        pseudo = self._pseudonyms.holding(copy.holding_id, copy.holding_barcode)
        return (pseudo, copy.catalog_title, copy.holding_barcode, copy.shelf_location)

    def _filter_catalog_candidates(
        self,
        candidates: list[CatalogLendableCopy],
        *,
        holding_barcode: str | None,
        title_query: str | None,
        copy_pseudonym: str | None,
    ) -> list[CatalogLendableCopy]:
        if copy_pseudonym:
            holding_id = self._pseudonyms.resolve_holding(copy_pseudonym.upper())
            if holding_id is None:
                return []
            return [c for c in candidates if c.holding_id == holding_id]
        if holding_barcode:
            needle = holding_barcode.strip().lower()
            return [c for c in candidates if c.holding_barcode.lower() == needle]
        if title_query:
            needle = title_query.strip().lower()
            return [c for c in candidates if needle in c.catalog_title.lower()]
        return []

    def _patron_from_dict(self, row: dict[str, object]) -> CompactPatron:
        return CompactPatron(
            pseudonym=str(row["pseudonym"]),
            display_name=str(row["display_name"]),
            external_ref=str(row["external_ref"]) if row.get("external_ref") else None,
            card_barcode=str(row["card_barcode"]) if row.get("card_barcode") else None,
        )

    def _filter_patron_candidates(
        self,
        candidates: list[CompactPatron],
        *,
        patron_query: str | None,
        card_barcode: str | None,
        external_ref: str | None,
        patron_pseudonym: str | None,
    ) -> list[CompactPatron]:
        if patron_pseudonym:
            needle = patron_pseudonym.upper()
            return [c for c in candidates if c.pseudonym.upper() == needle]
        if card_barcode:
            needle = card_barcode.strip().lower()
            return [
                c for c in candidates
                if c.card_barcode and c.card_barcode.lower() == needle
            ]
        if external_ref:
            needle = external_ref.strip().lower()
            return [
                c for c in candidates
                if c.external_ref and c.external_ref.lower() == needle
            ]
        if patron_query:
            needle = patron_query.strip().lower()
            return [c for c in candidates if needle in c.display_name.lower()]
        return []


class ReturnTools:
    def __init__(
        self,
        session: Session,
        workflow: ReturnBookWorkflow,
        pseudonyms: PseudonymMap,
    ) -> None:
        self._session = session
        self._workflow = workflow
        self._pseudonyms = pseudonyms

    def search_return_loans(
        self,
        slots: IssueSlots,
        *,
        patron_query: str | None = None,
        card_barcode: str | None = None,
        external_ref: str | None = None,
        title_query: str | None = None,
    ) -> ToolResult:
        try:
            candidates = self._workflow.search_candidates(
                patron_query=patron_query,
                card_barcode=card_barcode,
                external_ref=external_ref,
                title_query=title_query,
            )
        except AppError as exc:
            return ToolResult(False, desk.return_blocked(exc.message), {})
        slots.active_flow = DeskFlow.RETURN
        slots.return_candidates = [self._candidate_dict(c) for c in candidates]
        if not candidates:
            return ToolResult(
                False,
                desk.no_open_loans_for_return_search(
                    patron_query=patron_query or card_barcode or external_ref,
                    title_query=title_query,
                ),
                {},
            )
        if len(candidates) == 1:
            self._apply_candidate(slots, candidates[0])
            slots.return_candidates = []
            candidate = candidates[0]
            msg = desk.return_single_candidate_ready(
                candidate.patron_display_name,
                candidate.catalog_title,
                candidate.holding_barcode,
                due_date=candidate.due_date,
                is_overdue=candidate.is_overdue,
            )
            return ToolResult(True, msg, {"count": 1, "auto_selected": True})
        items = [self._candidate_line(c) for c in candidates]
        query_bits = [q for q in (patron_query, title_query) if q]
        query = " / ".join(query_bits) if query_bits else None
        return ToolResult(
            True,
            desk.return_candidates_list(items, query=query),
            {"count": len(candidates), "candidates": slots.return_candidates},
        )

    def list_patron_loans_at_desk(
        self,
        slots: IssueSlots,
        *,
        patron_query: str | None = None,
        card_barcode: str | None = None,
        external_ref: str | None = None,
        return_intent: bool = False,
    ) -> ToolResult:
        """List all open loans for a patron at the desk."""
        try:
            if slots.patron_id is not None and not patron_query and not card_barcode:
                patron_query = slots.patron_display_name
            candidates = self._workflow.search_candidates(
                patron_query=patron_query,
                card_barcode=card_barcode,
                external_ref=external_ref,
            )
        except AppError as exc:
            return ToolResult(False, desk.return_blocked(exc.message), {})
        slots.active_flow = DeskFlow.RETURN
        slots.return_candidates = [self._candidate_dict(c) for c in candidates]
        if candidates:
            first = candidates[0]
            slots.patron_id = first.patron_id
            slots.patron_display_name = first.patron_display_name
            self._pseudonyms.patron(first.patron_id, first.patron_display_name)
        patron_name = slots.patron_display_name or patron_query or "the patron"
        if not candidates:
            slots.loan_id = None
            slots.holding_id = None
            slots.holding_barcode = None
            slots.catalog_title = None
            slots.due_date = None
            slots.is_overdue = None
            if return_intent:
                msg = (
                    desk.desk_return_no_loans(patron_name)
                    + "\n\n"
                    + desk.desk_next_actions_prompt(
                        patron_name=patron_name, has_loans=False
                    )
                )
            else:
                msg = (
                    desk.desk_patron_no_loans(patron_name)
                    + "\n\n"
                    + desk.desk_next_actions_prompt(
                        patron_name=patron_name, has_loans=False
                    )
                )
            return ToolResult(True, msg, {"count": 0})
        if return_intent and len(candidates) == 1:
            only = candidates[0]
            self._apply_candidate(slots, only)
            slots.return_candidates = []
            msg = desk.desk_return_single_book_ready(
                only.patron_display_name,
                only.catalog_title,
                only.holding_barcode,
                due_date=only.due_date.isoformat(),
                is_overdue=only.is_overdue,
            )
            return ToolResult(
                True,
                msg,
                {"count": 1, "auto_selected": True, "return_intent": True},
            )
        slots.loan_id = None
        slots.holding_id = None
        slots.holding_barcode = None
        slots.catalog_title = None
        slots.due_date = None
        slots.is_overdue = None
        desk_items = [
            (
                self._pseudonyms.loan(c.loan_id),
                c.catalog_title,
                c.holding_barcode,
                c.due_date.isoformat(),
                c.is_overdue,
            )
            for c in candidates
        ]
        loans_msg = desk.desk_patron_loans_list(
            patron_name, desk_items, loan_count=len(candidates)
        )
        if return_intent:
            msg = loans_msg + "\n\n" + desk.desk_return_pick_from_list(patron_name)
        else:
            msg = loans_msg + "\n\n" + desk.desk_next_actions_prompt(
                patron_name=patron_name, has_loans=True
            )
        return ToolResult(
            True,
            msg,
            {
                "count": len(candidates),
                "candidates": slots.return_candidates,
                "return_intent": return_intent,
            },
        )

    def select_return_loan(
        self,
        slots: IssueSlots,
        *,
        holding_barcode: str | None = None,
        title_query: str | None = None,
        loan_pseudonym: str | None = None,
    ) -> ToolResult:
        if not slots.return_candidates:
            return ToolResult(False, desk.missing_loan_for_return(), {})
        candidates = [self._candidate_from_dict(row) for row in slots.return_candidates]
        matches = self._filter_candidates(
            candidates,
            holding_barcode=holding_barcode,
            title_query=title_query,
            loan_pseudonym=loan_pseudonym,
        )
        hint = holding_barcode or title_query or loan_pseudonym or ""
        if not matches:
            return ToolResult(False, desk.return_selection_not_found(hint), {})
        if len(matches) > 1:
            slots.return_candidates = [self._candidate_dict(c) for c in matches]
            items = [self._candidate_line(c) for c in matches]
            return ToolResult(
                False,
                desk.return_candidates_list(items, query=hint),
                {"count": len(matches)},
            )
        candidate = matches[0]
        return ToolResult(
            True,
            desk.return_select_approval_summary(
                candidate.patron_display_name,
                candidate.catalog_title,
                candidate.holding_barcode,
                due_date=candidate.due_date,
            ),
            {"candidate": self._candidate_dict(candidate)},
        )

    def apply_return_selection(self, slots: IssueSlots, candidate: dict[str, object]) -> ToolResult:
        parsed = self._candidate_from_dict(candidate)
        self._apply_candidate(slots, parsed)
        msg = desk.return_select_confirmed(
            parsed.catalog_title,
            parsed.holding_barcode,
            parsed.patron_display_name,
        )
        return ToolResult(True, msg, {"loan_id": str(parsed.loan_id)})

    def lookup_return(
        self,
        slots: IssueSlots,
        barcode: str,
        *,
        scanned: str | None = None,
    ) -> ToolResult:
        try:
            result = self._workflow.start(barcode=barcode)
        except AppError as exc:
            return ToolResult(
                False,
                desk.no_open_loan_for_return(barcode, exc.message),
                {},
            )
        slots.active_flow = DeskFlow.RETURN
        slots.loan_id = result.loan_id
        slots.holding_id = result.holding_id
        slots.holding_barcode = result.holding_barcode
        slots.patron_id = result.patron_id
        slots.patron_display_name = result.patron_display_name
        slots.catalog_title = result.catalog_title
        slots.due_date = result.due_date
        slots.is_overdue = result.is_overdue
        slots.fulfillment_id = None
        slots.fulfillment_target_status = None
        slots.return_candidates = []
        loan_label = self._pseudonyms.loan(result.loan_id)
        msg = desk.return_lookup_success(
            result.patron_display_name,
            result.catalog_title,
            result.holding_barcode,
            due_date=result.due_date,
            is_overdue=result.is_overdue,
            scanned=scanned or barcode,
            open_loans=result.open_loans_for_patron,
        )
        return ToolResult(
            True,
            msg,
            {
                "loan_pseudonym": loan_label,
                "is_overdue": result.is_overdue,
                "open_loans_for_patron": result.open_loans_for_patron,
            },
        )

    def commit_desk_return(
        self,
        slots: IssueSlots,
        *,
        idempotency_key: str,
    ) -> ToolResult:
        if slots.loan_id is None:
            return ToolResult(False, desk.missing_loan_for_return(), {})
        snapshot = self._snapshot_selection(slots)
        try:
            result = self._workflow.commit_desk(
                loan_id=slots.loan_id,
                holding_id=slots.holding_id,
                idempotency_key=idempotency_key,
            )
            self._session.commit()
        except AppError as exc:
            self._session.rollback()
            self._restore_selection(slots, snapshot)
            return ToolResult(False, desk.return_workflow_rolled_back(exc.message), {})
        loan_label = self._pseudonyms.loan(result.loan.id)
        msg = desk.return_committed(
            slots.patron_display_name or "patron",
            slots.catalog_title or "copy",
            slots.holding_barcode or "barcode",
        )
        self._clear_return_state(slots)
        return ToolResult(True, msg, {"loan_pseudonym": loan_label})

    def initiate_return_pickup(
        self,
        slots: IssueSlots,
        *,
        idempotency_key: str,
        destination_notes: str | None = None,
    ) -> ToolResult:
        if slots.loan_id is None:
            return ToolResult(False, desk.missing_loan_for_return(), {})
        snapshot = self._snapshot_selection(slots)
        try:
            fulfillment = self._workflow.initiate_pickup(
                slots.loan_id,
                destination_notes=destination_notes or slots.destination_notes,
                idempotency_key=idempotency_key,
            )
            self._session.commit()
        except AppError as exc:
            self._session.rollback()
            self._restore_selection(slots, snapshot)
            return ToolResult(False, desk.return_workflow_rolled_back(exc.message), {})
        slots.fulfillment_id = fulfillment.id
        status_label = str(fulfillment.status).lower().replace("_", " ")
        msg = desk.return_pickup_scheduled(
            slots.patron_display_name or "patron",
            slots.catalog_title or "copy",
            slots.holding_barcode or "barcode",
            status_label=status_label,
        )
        pseudo = self._pseudonyms.fulfillment(fulfillment.id)
        return ToolResult(True, msg, {"fulfillment_pseudonym": pseudo})

    def _apply_candidate(self, slots: IssueSlots, candidate: ReturnCandidate) -> None:
        slots.loan_id = candidate.loan_id
        slots.holding_id = candidate.holding_id
        slots.holding_barcode = candidate.holding_barcode
        slots.patron_id = candidate.patron_id
        slots.patron_display_name = candidate.patron_display_name
        slots.catalog_title = candidate.catalog_title
        slots.due_date = candidate.due_date
        slots.is_overdue = candidate.is_overdue
        slots.fulfillment_id = None
        slots.fulfillment_target_status = None
        self._pseudonyms.loan(candidate.loan_id)
        self._pseudonyms.holding(candidate.holding_id, candidate.holding_barcode)

    def _candidate_dict(self, candidate: ReturnCandidate) -> dict[str, object]:
        loan_label = self._pseudonyms.loan(candidate.loan_id)
        return {
            "loan_id": str(candidate.loan_id),
            "loan_pseudonym": loan_label,
            "holding_id": str(candidate.holding_id),
            "holding_barcode": candidate.holding_barcode,
            "patron_id": str(candidate.patron_id),
            "patron_display_name": candidate.patron_display_name,
            "catalog_title": candidate.catalog_title,
            "due_date": candidate.due_date.isoformat(),
            "is_overdue": candidate.is_overdue,
        }

    def _candidate_from_dict(self, row: dict[str, object]) -> ReturnCandidate:
        from datetime import date

        return ReturnCandidate(
            loan_id=UUID(str(row["loan_id"])),
            holding_id=UUID(str(row["holding_id"])),
            holding_barcode=str(row["holding_barcode"]),
            patron_id=UUID(str(row["patron_id"])),
            patron_display_name=str(row["patron_display_name"]),
            catalog_title=str(row["catalog_title"]),
            due_date=date.fromisoformat(str(row["due_date"])),
            is_overdue=bool(row["is_overdue"]),
        )

    def _candidate_line(
        self, candidate: ReturnCandidate
    ) -> tuple[str, str, str, str, str, bool]:
        loan_label = self._pseudonyms.loan(candidate.loan_id)
        return (
            loan_label,
            candidate.catalog_title,
            candidate.holding_barcode,
            candidate.patron_display_name,
            candidate.due_date.isoformat(),
            candidate.is_overdue,
        )

    def _filter_candidates(
        self,
        candidates: list[ReturnCandidate],
        *,
        holding_barcode: str | None,
        title_query: str | None,
        loan_pseudonym: str | None,
    ) -> list[ReturnCandidate]:
        if loan_pseudonym:
            loan_id = self._pseudonyms.resolve_loan(loan_pseudonym.upper())
            if loan_id is None:
                return []
            return [c for c in candidates if c.loan_id == loan_id]
        if holding_barcode:
            needle = holding_barcode.strip().lower()
            return [c for c in candidates if c.holding_barcode.lower() == needle]
        if title_query:
            needle = title_query.strip().lower()
            return [c for c in candidates if needle in c.catalog_title.lower()]
        return []

    def _snapshot_selection(self, slots: IssueSlots) -> dict[str, object | None]:
        return {
            "loan_id": slots.loan_id,
            "holding_id": slots.holding_id,
            "holding_barcode": slots.holding_barcode,
            "patron_id": slots.patron_id,
            "patron_display_name": slots.patron_display_name,
            "catalog_title": slots.catalog_title,
            "due_date": slots.due_date,
            "is_overdue": slots.is_overdue,
            "return_candidates": list(slots.return_candidates),
        }

    def _restore_selection(self, slots: IssueSlots, snapshot: dict[str, object | None]) -> None:
        slots.loan_id = snapshot["loan_id"]  # type: ignore[assignment]
        slots.holding_id = snapshot["holding_id"]  # type: ignore[assignment]
        slots.holding_barcode = snapshot["holding_barcode"]  # type: ignore[assignment]
        slots.patron_id = snapshot["patron_id"]  # type: ignore[assignment]
        slots.patron_display_name = snapshot["patron_display_name"]  # type: ignore[assignment]
        slots.catalog_title = snapshot["catalog_title"]  # type: ignore[assignment]
        slots.due_date = snapshot["due_date"]  # type: ignore[assignment]
        slots.is_overdue = snapshot["is_overdue"]  # type: ignore[assignment]
        raw_candidates = snapshot["return_candidates"]
        slots.return_candidates = list(raw_candidates) if isinstance(raw_candidates, list) else []

    def _clear_return_state(self, slots: IssueSlots) -> None:
        slots.loan_id = None
        slots.holding_id = None
        slots.holding_barcode = None
        slots.catalog_title = None
        slots.patron_id = None
        slots.patron_display_name = None
        slots.due_date = None
        slots.is_overdue = None
        slots.return_candidates = []
        slots.fulfillment_id = None
        slots.fulfillment_target_status = None
        slots.active_flow = DeskFlow.ISSUE
