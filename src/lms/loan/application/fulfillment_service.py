"""CirculationFulfillment aggregate service (ADR-022)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from lms.api.errors import AppError, ErrorCode
from lms.loan.domain.enums import (
    FulfillmentDirection,
    FulfillmentMode,
    FulfillmentStatus,
)
from lms.loan.infrastructure.models.models import CirculationFulfillmentModel, LoanModel

_ALLOWED_TRANSITIONS: dict[FulfillmentStatus, frozenset[FulfillmentStatus]] = {
    FulfillmentStatus.REQUESTED: frozenset(
        {FulfillmentStatus.READY, FulfillmentStatus.CANCELLED}
    ),
    FulfillmentStatus.READY: frozenset(
        {FulfillmentStatus.IN_TRANSIT, FulfillmentStatus.COMPLETED, FulfillmentStatus.CANCELLED}
    ),
    FulfillmentStatus.IN_TRANSIT: frozenset(
        {FulfillmentStatus.COMPLETED, FulfillmentStatus.CANCELLED}
    ),
}


class FulfillmentService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_issue_fulfillment(
        self,
        *,
        loan_id: UUID,
        holding_id: UUID,
        mode: FulfillmentMode,
        destination_notes: str | None = None,
        destination_class_section_id: UUID | None = None,
        destination_contact: str | None = None,
    ) -> CirculationFulfillmentModel:
        loan = self._require_open_loan(loan_id)
        if loan.holding_id != holding_id:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "Loan holding does not match fulfillment holding",
                status_code=422,
            )
        row = CirculationFulfillmentModel(
            loan_id=loan_id,
            holding_id=holding_id,
            direction=FulfillmentDirection.ISSUE,
            mode=mode,
            status=FulfillmentStatus.REQUESTED,
            destination_notes=destination_notes,
            destination_class_section_id=destination_class_section_id,
            destination_contact=destination_contact,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def initiate_return_pickup(
        self,
        *,
        loan_id: UUID,
        destination_notes: str | None = None,
        destination_class_section_id: UUID | None = None,
        destination_contact: str | None = None,
    ) -> CirculationFulfillmentModel:
        loan = self._require_open_loan(loan_id)
        row = CirculationFulfillmentModel(
            loan_id=loan_id,
            holding_id=loan.holding_id,
            direction=FulfillmentDirection.RETURN,
            mode=FulfillmentMode.PICKUP_POINT,
            status=FulfillmentStatus.REQUESTED,
            destination_notes=destination_notes,
            destination_class_section_id=destination_class_section_id,
            destination_contact=destination_contact,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def transition(
        self,
        fulfillment_id: UUID,
        target_status: FulfillmentStatus,
    ) -> CirculationFulfillmentModel:
        row = self._get_fulfillment(fulfillment_id)
        current = FulfillmentStatus(row.status)
        if current == target_status:
            return row
        allowed = _ALLOWED_TRANSITIONS.get(current, frozenset())
        if target_status not in allowed:
            raise AppError(
                ErrorCode.DOMAIN_RULE_VIOLATION,
                f"Cannot transition fulfillment from {current} to {target_status}",
                status_code=422,
            )
        if target_status == FulfillmentStatus.COMPLETED:
            if row.direction == FulfillmentDirection.ISSUE:
                self._require_open_loan(row.loan_id)  # type: ignore[arg-type]
            elif row.direction == FulfillmentDirection.RETURN:
                self._require_open_loan(row.loan_id)  # type: ignore[arg-type]
        row.status = target_status
        self._session.flush()
        return row

    def get_fulfillment(self, fulfillment_id: UUID) -> CirculationFulfillmentModel:
        return self._get_fulfillment(fulfillment_id)

    def cancel_issue_fulfillments_for_loan(self, loan_id: UUID) -> bool:
        """Cancel open ISSUE fulfillments (not already COMPLETED/CANCELLED)."""
        rows = list(
            self._session.scalars(
                select(CirculationFulfillmentModel).where(
                    CirculationFulfillmentModel.loan_id == loan_id,
                    CirculationFulfillmentModel.direction == FulfillmentDirection.ISSUE,
                )
            )
        )
        cancelled = False
        for row in rows:
            status = FulfillmentStatus(row.status)
            if status in (FulfillmentStatus.COMPLETED, FulfillmentStatus.CANCELLED):
                continue
            row.status = FulfillmentStatus.CANCELLED
            cancelled = True
        if cancelled:
            self._session.flush()
        return cancelled

    def _require_open_loan(self, loan_id: UUID) -> LoanModel:
        loan = self._session.get(LoanModel, loan_id)
        if loan is None:
            raise AppError(ErrorCode.NOT_FOUND, "Loan not found", status_code=404)
        if loan.returned_at is not None:
            raise AppError(
                ErrorCode.DOMAIN_RULE_VIOLATION,
                "Loan is already closed",
                status_code=422,
            )
        return loan

    def _get_fulfillment(self, fulfillment_id: UUID) -> CirculationFulfillmentModel:
        row = self._session.get(CirculationFulfillmentModel, fulfillment_id)
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, "Fulfillment not found", status_code=404)
        return row
