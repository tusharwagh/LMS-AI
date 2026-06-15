"""Allowlisted tools wrapping workflow services (ADR-025)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from lms.agent import messages as desk
from lms.agent.masking import PseudonymMap, redact_for_audit
from lms.agent.schemas import IntentAction
from lms.agent.session import IssueSlots
from lms.api.errors import AppError
from lms.api.workflows.search_and_issue import SearchAndIssueWorkflow
from lms.loan.application.fulfillment_service import FulfillmentService
from lms.loan.domain.enums import FulfillmentStatus
from lms.loan.domain.validation import ValidationReport

READ_TOOL_NAMES = frozenset(
    {
        "search_patrons",
        "resolve_patron",
        "search_lendable",
        "select_barcode",
        "validate_issue",
        "get_fulfillment_status",
    }
)
WRITE_TOOL_NAMES = frozenset(
    {
        "commit_issue",
        "transition_fulfillment",
        "cancel_issue",
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

    def search_patrons(self, query: str, *, limit: int = 5) -> ToolResult:
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
            return ToolResult(
                False,
                desk.no_patron_found(redact_for_audit(query)),
                {},
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
        result = self._workflow.start(
            patron_id=patron_id,
            card_barcode=card_barcode,
            external_ref=external_ref,
            display_name=display_name,
        )
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
        query_hint = message_query or display_name or card_barcode or external_ref
        return ToolResult(
            True,
            desk.patron_eligible(
                result.patron_display_name,
                query=redact_for_audit(query_hint) if query_hint else None,
            ),
            {"patron_pseudonym": pseudo},
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
