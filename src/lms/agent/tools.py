"""Allowlisted tools wrapping workflow services (ADR-025)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from lms.agent.masking import PseudonymMap, redact_for_audit
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
            return ToolResult(False, f"No patron found for {redact_for_audit(query)}.", {})
        msg = "; ".join(f"{i.pseudonym}: {i.display_name}" for i in items)
        return ToolResult(True, msg, {"patrons": [asdict(i) for i in items]})

    def resolve_patron(
        self,
        slots: IssueSlots,
        *,
        patron_id: UUID | None = None,
        card_barcode: str | None = None,
        external_ref: str | None = None,
        display_name: str | None = None,
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
                f"{pseudo} ({result.patron_display_name}) cannot borrow: "
                + "; ".join(violations),
                {"patron_pseudonym": pseudo},
            )
        return ToolResult(
            True,
            f"Patron {pseudo} ({result.patron_display_name}) is eligible to borrow.",
            {"patron_pseudonym": pseudo},
        )

    def search_lendable(self, slots: IssueSlots, query: str) -> ToolResult:
        if slots.patron_id is None:
            return ToolResult(False, "Identify a patron first.", {})
        result = self._workflow.start(patron_id=slots.patron_id, search_query=query)
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
            return ToolResult(False, f"No lendable copies for {query}.", {})
        if len(copies) == 1:
            only = copies[0]
            hid = self._resolve_holding_id(only.pseudonym)
            if hid:
                slots.holding_id = hid
                slots.holding_barcode = only.barcode
                slots.catalog_title = only.title
        msg = "; ".join(f"{c.pseudonym}: {c.title} · {c.barcode}" for c in copies[:5])
        return ToolResult(True, msg, {"copies": [asdict(c) for c in copies[:5]]})

    def select_barcode(self, slots: IssueSlots, barcode: str) -> ToolResult:
        if slots.patron_id is None:
            return ToolResult(False, "Identify a patron first.", {})
        try:
            result = self._workflow.find_lendable_copy_by_barcode(slots.patron_id, barcode)
        except AppError as exc:
            return ToolResult(False, exc.message, {})
        hit = result.search_results[0]
        copy = hit["lendable_copies"][0]
        hid = UUID(str(copy["holding_id"]))
        slots.holding_id = hid
        slots.holding_barcode = str(copy["barcode"])
        slots.catalog_title = str(hit["title"])
        pseudo = self._pseudonyms.holding(hid, slots.holding_barcode)
        return ToolResult(
            True,
            f"Selected {pseudo}: {slots.catalog_title} · {slots.holding_barcode}",
            {"copy_pseudonym": pseudo},
        )

    def validate_issue(self, slots: IssueSlots) -> ToolResult:
        if slots.patron_id is None or slots.holding_id is None:
            return ToolResult(False, "Need patron and copy before validating.", {})
        report = self._workflow.validate(slots.patron_id, slots.holding_id)
        return self._validation_result(report)

    def commit_issue(
        self,
        slots: IssueSlots,
        *,
        idempotency_key: str,
        operator_id: str | None,
    ) -> ToolResult:
        if slots.patron_id is None or slots.holding_id is None:
            return ToolResult(False, "Need patron and copy to commit.", {})
        result = self._workflow.commit(
            slots.patron_id,
            slots.holding_id,
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
        msg = f"Issue committed ({loan_label})."
        if result.fulfillment is not None:
            fl = self._pseudonyms.fulfillment(result.fulfillment.id)
            msg += f" Fulfillment {fl} is {result.fulfillment.status}."
        return ToolResult(True, msg, {"loan_pseudonym": loan_label})

    def get_fulfillment_status(self, slots: IssueSlots) -> ToolResult:
        fid = slots.fulfillment_id
        if fid is None and slots.loan_id is not None:
            row = self._fulfillment.get_issue_fulfillment_for_loan(slots.loan_id)
            if row is not None:
                fid = row.id
                slots.fulfillment_id = fid
        if fid is None:
            return ToolResult(False, "No fulfillment in this session.", {})
        row = self._fulfillment.get_fulfillment(fid)
        label = self._pseudonyms.fulfillment(row.id)
        return ToolResult(
            True,
            f"Fulfillment {label} status is {row.status}.",
            {"fulfillment_pseudonym": label, "status": str(row.status)},
        )

    def transition_fulfillment(
        self,
        slots: IssueSlots,
        target_status: FulfillmentStatus,
        *,
        idempotency_key: str,
    ) -> ToolResult:
        if slots.fulfillment_id is None:
            return ToolResult(False, "No fulfillment to transition.", {})
        row = self._fulfillment.transition(
            slots.fulfillment_id,
            target_status,
            idempotency_key=idempotency_key,
        )
        self._session.commit()
        label = self._pseudonyms.fulfillment(row.id)
        return ToolResult(True, f"Fulfillment {label} is now {row.status}.", {})

    def cancel_issue(
        self,
        slots: IssueSlots,
        *,
        idempotency_key: str,
    ) -> ToolResult:
        if slots.loan_id is None:
            return ToolResult(False, "No open loan in this session to cancel.", {})
        result = self._workflow.cancel_issue(slots.loan_id, idempotency_key=idempotency_key)
        self._session.commit()
        loan_label = self._pseudonyms.loan(result.loan.id)
        slots.loan_id = None
        slots.fulfillment_id = None
        slots.fulfillment_target_status = None
        msg = f"Issue cancelled ({loan_label})."
        if result.fulfillment_cancelled:
            msg += " Fulfillment cancelled."
        return ToolResult(True, msg, {"loan_pseudonym": loan_label})

    def _validation_result(self, report: ValidationReport) -> ToolResult:
        if report.is_valid:
            return ToolResult(True, "Ready to issue.", {"valid": True})
        msgs = [v.message for v in report.violations]
        return ToolResult(False, "; ".join(msgs), {"valid": False, "violations": msgs})

    def _resolve_holding_id(self, pseudonym: str) -> UUID | None:
        return self._pseudonyms.resolve_holding(pseudonym)
