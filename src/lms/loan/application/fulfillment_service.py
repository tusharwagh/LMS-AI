"""CirculationFulfillment aggregate service (ADR-022)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from lms.loan.domain.enums import (
    FulfillmentDirection,
    FulfillmentMode,
    FulfillmentStatus,
)
from lms.loan.infrastructure.models.models import CirculationFulfillmentModel, LoanModel
from lms.shared.http.errors import AppError, ErrorCode
from lms.shared.idempotency.service import (
    IdempotencyPayloadMismatchError,
    find_cached_response,
    store_response,
)

_ALLOWED_TRANSITIONS: dict[FulfillmentStatus, frozenset[FulfillmentStatus]] = {
    FulfillmentStatus.REQUESTED: frozenset({FulfillmentStatus.READY, FulfillmentStatus.CANCELLED}),
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
        *,
        idempotency_key: str,
    ) -> CirculationFulfillmentModel:
        payload = {
            "fulfillment_id": str(fulfillment_id),
            "status": target_status.value,
        }
        scope_key = f"fulfillment-transition:{fulfillment_id}"
        try:
            cached = find_cached_response(
                self._session,
                scope_key=scope_key,
                idempotency_key=idempotency_key,
                payload=payload,
            )
        except IdempotencyPayloadMismatchError as exc:
            raise AppError(
                ErrorCode.CONFLICT,
                "Idempotency key reused with different payload",
                status_code=409,
            ) from exc
        if cached is not None:
            status_code, body = cached
            if status_code != 200:
                raise AppError(
                    ErrorCode.CONFLICT,
                    "Idempotency key reused with different payload",
                    status_code=409,
                )
            cached_id = UUID(body["id"])
            if cached_id != fulfillment_id:
                raise AppError(
                    ErrorCode.RETRIABLE_ERROR,
                    "Cached fulfillment missing",
                    status_code=500,
                )
            return self._get_fulfillment(fulfillment_id)

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
        store_response(
            self._session,
            scope_key=scope_key,
            idempotency_key=idempotency_key,
            payload=payload,
            status_code=200,
            body={"id": str(row.id)},
        )
        return row

    def get_fulfillment(self, fulfillment_id: UUID) -> CirculationFulfillmentModel:
        return self._get_fulfillment(fulfillment_id)

    def get_issue_fulfillment_for_loan(self, loan_id: UUID) -> CirculationFulfillmentModel | None:
        row = self._session.scalar(
            select(CirculationFulfillmentModel).where(
                CirculationFulfillmentModel.loan_id == loan_id,
                CirculationFulfillmentModel.direction == FulfillmentDirection.ISSUE,
            )
        )
        return row

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
