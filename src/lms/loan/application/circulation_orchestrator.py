"""Cross-context write coordinator for CheckoutHolding / ReturnHolding (ADR-002)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from lms.api.errors import AppError, ErrorCode
from lms.loan.domain.ports import (
    HoldingCirculationPort,
    PatronEligibilityPort,
    PolicyResolverPort,
)
from lms.loan.infrastructure.models.models import LoanModel
from lms.shared.idempotency.service import (
    IdempotencyPayloadMismatchError,
    find_cached_response,
    store_response,
)
from lms.shared.time import utc_now


class CirculationOrchestrator:
    def __init__(
        self,
        session: Session,
        patron_eligibility: PatronEligibilityPort,
        holding_circulation: HoldingCirculationPort,
        policy_resolver: PolicyResolverPort,
    ) -> None:
        self._session = session
        self._patron_eligibility = patron_eligibility
        self._holding_circulation = holding_circulation
        self._policy_resolver = policy_resolver

    def checkout(
        self,
        patron_id: UUID,
        holding_id: UUID,
        *,
        idempotency_key: str,
        operator_id: str | None = None,
    ) -> LoanModel:
        payload = {"patron_id": str(patron_id), "holding_id": str(holding_id)}
        scope_key = f"checkout:{holding_id}"
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
            if status_code != 201:
                raise AppError(
                    ErrorCode.CONFLICT,
                    "Idempotency key reused with different payload",
                    status_code=409,
                )
            loan_id = UUID(body["id"])
            row = self._session.get(LoanModel, loan_id)
            if row is None:
                raise AppError(ErrorCode.RETRIABLE_ERROR, "Cached loan missing", status_code=500)
            return row

        eligibility = self._patron_eligibility.check(patron_id)
        if not eligibility.is_active:
            raise AppError(
                ErrorCode.DOMAIN_RULE_VIOLATION,
                "Patron is not active",
                status_code=422,
            )
        if eligibility.is_blocked:
            raise AppError(
                ErrorCode.DOMAIN_RULE_VIOLATION,
                "Patron is blocked from borrowing",
                status_code=422,
            )

        try:
            snapshot = self._holding_circulation.lock_for_checkout(holding_id)
        except ValueError as exc:
            raise AppError(ErrorCode.NOT_FOUND, str(exc), status_code=404) from exc

        if not snapshot.is_lendable:
            raise AppError(
                ErrorCode.DOMAIN_RULE_VIOLATION,
                "Holding is not available for checkout",
                status_code=422,
                details={"holding_status": snapshot.holding_status},
            )

        try:
            policy = self._policy_resolver.resolve(eligibility.patron_type_id)
        except ValueError as exc:
            raise AppError(ErrorCode.DOMAIN_RULE_VIOLATION, str(exc), status_code=422) from exc

        if eligibility.open_loan_count >= policy.max_active_loans:
            raise AppError(
                ErrorCode.DOMAIN_RULE_VIOLATION,
                "Patron has reached maximum active loans",
                status_code=422,
                details={"max_active_loans": policy.max_active_loans},
            )

        loan = LoanModel(
            patron_id=patron_id,
            holding_id=holding_id,
            loan_rule_set_id=policy.loan_rule_set_id,
            checkout_at=utc_now(),
            due_date=policy.due_date,
            checkout_operator_id=operator_id,
        )
        self._holding_circulation.mark_on_loan(holding_id)
        self._session.add(loan)
        self._session.flush()

        body = {"id": str(loan.id)}
        store_response(
            self._session,
            scope_key=scope_key,
            idempotency_key=idempotency_key,
            payload=payload,
            status_code=201,
            body=body,
        )
        self._session.commit()
        self._session.refresh(loan)
        return loan

    def return_holding(
        self,
        *,
        holding_id: UUID | None = None,
        loan_id: UUID | None = None,
        idempotency_key: str,
    ) -> LoanModel:
        if holding_id is None and loan_id is None:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                "Either holding_id or loan_id is required",
                status_code=422,
            )

        payload: dict[str, str] = {}
        if holding_id is not None:
            payload["holding_id"] = str(holding_id)
        if loan_id is not None:
            payload["loan_id"] = str(loan_id)

        scope_key = f"return:{holding_id or loan_id}"
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
                raise AppError(ErrorCode.CONFLICT, "Idempotency conflict", status_code=409)
            returned_loan_id = UUID(body["id"])
            row = self._session.get(LoanModel, returned_loan_id)
            if row is None:
                raise AppError(ErrorCode.RETRIABLE_ERROR, "Cached loan missing", status_code=500)
            return row

        if holding_id is not None:
            try:
                self._holding_circulation.lock_for_return(holding_id)
            except ValueError as exc:
                raise AppError(ErrorCode.NOT_FOUND, str(exc), status_code=404) from exc
            loan = self._session.scalar(
                select(LoanModel).where(
                    LoanModel.holding_id == holding_id,
                    LoanModel.returned_at.is_(None),
                )
            )
            resolved_holding_id = holding_id
        else:
            assert loan_id is not None
            loan = self._session.scalar(
                select(LoanModel).where(LoanModel.id == loan_id).with_for_update()
            )
            if loan is None:
                raise AppError(ErrorCode.NOT_FOUND, "Loan not found", status_code=404)
            resolved_holding_id = loan.holding_id
            try:
                self._holding_circulation.lock_for_return(resolved_holding_id)
            except ValueError as exc:
                raise AppError(ErrorCode.NOT_FOUND, str(exc), status_code=404) from exc

        if loan is None:
            raise AppError(ErrorCode.NOT_FOUND, "No open loan for holding", status_code=404)

        if loan.returned_at is not None:
            body = {"id": str(loan.id)}
            store_response(
                self._session,
                scope_key=scope_key,
                idempotency_key=idempotency_key,
                payload=payload,
                status_code=200,
                body=body,
            )
            self._session.commit()
            return loan

        loan.returned_at = utc_now()
        self._holding_circulation.mark_available(resolved_holding_id)

        self._session.flush()
        body = {"id": str(loan.id)}
        store_response(
            self._session,
            scope_key=scope_key,
            idempotency_key=idempotency_key,
            payload=payload,
            status_code=200,
            body=body,
        )
        self._session.commit()
        self._session.refresh(loan)
        return loan
