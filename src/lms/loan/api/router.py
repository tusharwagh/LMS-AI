"""Loan domain API — all routes require Bearer JWT; staff or admin role per endpoint."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query

from lms.api.composition import get_circulation_orchestrator
from lms.api.deps import DbSession
from lms.api.rbac import StaffAuth, require_admin, require_staff
from lms.loan.api.schemas import (
    CheckoutRequest,
    LoanDetailResponse,
    LoanResponse,
    LoanRuleSetCreate,
    LoanRuleSetResponse,
    LoanRuleSetUpdate,
    ReturnRequest,
)
from lms.loan.application.circulation_orchestrator import CirculationOrchestrator
from lms.loan.application.service import LoanDetailRow, LoanService

router = APIRouter(dependencies=[require_staff])


def _loan_service(session: DbSession) -> LoanService:
    return LoanService(session)


def _loan_detail_response(row: LoanDetailRow) -> LoanDetailResponse:
    return LoanDetailResponse(
        **LoanResponse.model_validate(row.loan).model_dump(),
        patron_display_name=row.patron_display_name,
        holding_barcode=row.holding_barcode,
        catalog_title=row.catalog_title,
    )


@router.post(
    "/loan-rule-sets",
    response_model=LoanRuleSetResponse,
    status_code=201,
    dependencies=[require_admin],
)
def configure_loan_rule_set(
    body: LoanRuleSetCreate,
    service: Annotated[LoanService, Depends(_loan_service)],
) -> LoanRuleSetResponse:
    return LoanRuleSetResponse.model_validate(service.configure_loan_rule_set(body))


@router.patch(
    "/loan-rule-sets/{rule_set_id}",
    response_model=LoanRuleSetResponse,
    dependencies=[require_admin],
)
def update_loan_rule_set(
    rule_set_id: UUID,
    body: LoanRuleSetUpdate,
    service: Annotated[LoanService, Depends(_loan_service)],
) -> LoanRuleSetResponse:
    return LoanRuleSetResponse.model_validate(service.update_loan_rule_set(rule_set_id, body))


@router.get("/loan-rule-sets", response_model=list[LoanRuleSetResponse])
def list_loan_rule_sets(
    service: Annotated[LoanService, Depends(_loan_service)],
) -> list[LoanRuleSetResponse]:
    return [
        LoanRuleSetResponse.model_validate(row) for row in service.list_loan_rule_sets()
    ]


@router.get("/loan-rule-sets/{rule_set_id}", response_model=LoanRuleSetResponse)
def get_loan_rule_set(
    rule_set_id: UUID,
    service: Annotated[LoanService, Depends(_loan_service)],
) -> LoanRuleSetResponse:
    return LoanRuleSetResponse.model_validate(service.get_loan_rule_set(rule_set_id))


@router.post("/checkouts", response_model=LoanResponse, status_code=201)
def checkout_holding(
    body: CheckoutRequest,
    orchestrator: Annotated[CirculationOrchestrator, Depends(get_circulation_orchestrator)],
    auth: StaffAuth,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=64)],
) -> LoanResponse:
    loan = orchestrator.checkout(
        body.patron_id,
        body.holding_id,
        idempotency_key=idempotency_key,
        operator_id=auth.subject,
    )
    return LoanResponse.model_validate(loan)


@router.post("/returns", response_model=LoanResponse)
def return_holding(
    body: ReturnRequest,
    orchestrator: Annotated[CirculationOrchestrator, Depends(get_circulation_orchestrator)],
    auth: StaffAuth,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=64)],
) -> LoanResponse:
    loan = orchestrator.return_holding(
        holding_id=body.holding_id,
        loan_id=body.loan_id,
        idempotency_key=idempotency_key,
    )
    return LoanResponse.model_validate(loan)


@router.get("/loans/open", response_model=list[LoanDetailResponse])
def list_open_loans_by_patron(
    service: Annotated[LoanService, Depends(_loan_service)],
    patron_id: Annotated[UUID, Query()],
) -> list[LoanDetailResponse]:
    return [
        _loan_detail_response(row)
        for row in service.list_open_loan_details_by_patron(patron_id)
    ]


@router.get("/loans/overdue", response_model=list[LoanDetailResponse])
def list_overdue_loans(
    service: Annotated[LoanService, Depends(_loan_service)],
) -> list[LoanDetailResponse]:
    return [_loan_detail_response(row) for row in service.list_overdue_loan_details()]
