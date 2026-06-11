"""Staff desk workflow API (REQ-26, REQ-27)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header

from lms.api.composition import get_circulation_orchestrator
from lms.api.deps import DbSession
from lms.api.rbac import StaffAuth, require_staff
from lms.api.workflows.return_book import ReturnBookWorkflow
from lms.api.workflows.schemas import (
    FulfillmentResponse,
    FulfillmentTransitionRequest,
    IssueBackRequest,
    IssueBackResponse,
    IssueCancelRequest,
    IssueCancelResponse,
    IssueCommitRequest,
    IssueCommitResponse,
    IssueSearchHit,
    IssueSearchPatronsRequest,
    IssueSearchPatronsResponse,
    IssueStartRequest,
    IssueStartResponse,
    IssueValidateRequest,
    LendableCopySummary,
    PatronSummaryResponse,
    ReturnCommitRequest,
    ReturnCommitResponse,
    ReturnPickupConfirmRequest,
    ReturnPickupInitiateRequest,
    ReturnStartRequest,
    ReturnStartResponse,
    RuleViolationResponse,
    ValidationReportResponse,
)
from lms.api.workflows.search_and_issue import SearchAndIssueWorkflow
from lms.catalog.application.service import CatalogService
from lms.loan.application.circulation_orchestrator import CirculationOrchestrator
from lms.loan.application.fulfillment_service import FulfillmentService
from lms.loan.domain.enums import FulfillmentStatus
from lms.loan.domain.validation import ValidationReport

router = APIRouter(prefix="/workflows", dependencies=[require_staff])


def _issue_workflow(
    session: DbSession,
    orchestrator: Annotated[CirculationOrchestrator, Depends(get_circulation_orchestrator)],
) -> SearchAndIssueWorkflow:
    return SearchAndIssueWorkflow(session, orchestrator)


def _return_workflow(
    session: DbSession,
    orchestrator: Annotated[CirculationOrchestrator, Depends(get_circulation_orchestrator)],
) -> ReturnBookWorkflow:
    return ReturnBookWorkflow(session, orchestrator)


def _fulfillment_service(session: DbSession) -> FulfillmentService:
    return FulfillmentService(session)


def _to_validation_response(report: ValidationReport) -> ValidationReportResponse:
    return ValidationReportResponse(
        is_valid=report.is_valid,
        violations=[
            RuleViolationResponse(rule_id=v.rule_id, message=v.message) for v in report.violations
        ],
    )


@router.post("/issue/start", response_model=IssueStartResponse)
def issue_start(
    body: IssueStartRequest,
    workflow: Annotated[SearchAndIssueWorkflow, Depends(_issue_workflow)],
) -> IssueStartResponse:
    result = workflow.start(
        patron_id=body.patron_id,
        card_barcode=body.card_barcode,
        external_ref=body.external_ref,
        display_name=body.display_name,
        search_query=body.search_query,
    )
    return IssueStartResponse(
        patron_id=result.patron_id,
        patron_display_name=result.patron_display_name,
        patron_validation=_to_validation_response(result.patron_validation),
        search_results=[
            IssueSearchHit(
                catalog_id=UUID(hit["catalog_id"]),
                title=hit["title"],
                lendable_copies=[
                    LendableCopySummary(
                        holding_id=UUID(c["holding_id"]),
                        barcode=c["barcode"],
                        accession_number=c["accession_number"],
                        shelf_location=c["shelf_location"],
                    )
                    for c in hit["lendable_copies"]
                ],
            )
            for hit in result.search_results
        ],
    )


@router.post("/issue/search-patrons", response_model=IssueSearchPatronsResponse)
def issue_search_patrons(
    body: IssueSearchPatronsRequest,
    workflow: Annotated[SearchAndIssueWorkflow, Depends(_issue_workflow)],
) -> IssueSearchPatronsResponse:
    patrons = workflow.search_patrons(body.display_name, limit=body.limit)
    return IssueSearchPatronsResponse(
        patrons=[PatronSummaryResponse.model_validate(p) for p in patrons]
    )


@router.post("/issue/back", response_model=IssueBackResponse)
def issue_back(
    body: IssueBackRequest,
    workflow: Annotated[SearchAndIssueWorkflow, Depends(_issue_workflow)],
) -> IssueBackResponse:
    result = workflow.back_step(body.target_step, loan_id=body.loan_id)
    return IssueBackResponse(
        target_step=result.target_step,
        allowed=result.allowed,
        message=result.message,
    )


@router.post("/issue/cancel", response_model=IssueCancelResponse)
def issue_cancel(
    body: IssueCancelRequest,
    workflow: Annotated[SearchAndIssueWorkflow, Depends(_issue_workflow)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=64)],
) -> IssueCancelResponse:
    result = workflow.cancel_issue(body.loan_id, idempotency_key=idempotency_key)
    return IssueCancelResponse(
        loan_id=result.loan.id,
        returned_at=result.loan.returned_at,  # type: ignore[arg-type]
        holding_id=result.loan.holding_id,
        fulfillment_cancelled=result.fulfillment_cancelled,
    )


@router.post("/issue/validate", response_model=ValidationReportResponse)
def issue_validate(
    body: IssueValidateRequest,
    workflow: Annotated[SearchAndIssueWorkflow, Depends(_issue_workflow)],
) -> ValidationReportResponse:
    return _to_validation_response(workflow.validate(body.patron_id, body.holding_id))


@router.post("/issue/commit", response_model=IssueCommitResponse, status_code=201)
def issue_commit(
    body: IssueCommitRequest,
    workflow: Annotated[SearchAndIssueWorkflow, Depends(_issue_workflow)],
    auth: StaffAuth,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=64)],
) -> IssueCommitResponse:
    dest = body.destination
    result = workflow.commit(
        body.patron_id,
        body.holding_id,
        fulfillment_mode=body.fulfillment_mode,
        destination_notes=dest.notes if dest else None,
        destination_class_section_id=dest.class_section_id if dest else None,
        destination_contact=dest.contact if dest else None,
        idempotency_key=idempotency_key,
        operator_id=auth.subject,
    )
    fulfillment = (
        FulfillmentResponse.model_validate(result.fulfillment) if result.fulfillment else None
    )
    return IssueCommitResponse(
        loan_id=result.loan.id,
        patron_id=result.loan.patron_id,
        holding_id=result.loan.holding_id,
        due_date=result.loan.due_date,
        validation=_to_validation_response(result.validation),
        fulfillment=fulfillment,
    )


@router.post("/return/start", response_model=ReturnStartResponse)
def return_start(
    body: ReturnStartRequest,
    workflow: Annotated[ReturnBookWorkflow, Depends(_return_workflow)],
) -> ReturnStartResponse:
    result = workflow.start(barcode=body.barcode, loan_id=body.loan_id)
    return ReturnStartResponse(
        loan_id=result.loan_id,
        holding_id=result.holding_id,
        holding_barcode=result.holding_barcode,
        patron_id=result.patron_id,
        patron_display_name=result.patron_display_name,
        catalog_title=result.catalog_title,
        due_date=result.due_date,
        is_overdue=result.is_overdue,
        open_loans_for_patron=result.open_loans_for_patron,
    )


@router.post("/return/commit", response_model=ReturnCommitResponse)
def return_commit(
    body: ReturnCommitRequest,
    session: DbSession,
    workflow: Annotated[ReturnBookWorkflow, Depends(_return_workflow)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=64)],
) -> ReturnCommitResponse:
    holding_id: UUID | None = None
    loan_id = body.loan_id
    if body.barcode:
        holding = CatalogService(session).get_holding_by_barcode(body.barcode)
        holding_id = holding.id

    result = workflow.commit_desk(
        holding_id=holding_id,
        loan_id=loan_id,
        idempotency_key=idempotency_key,
    )
    return ReturnCommitResponse(
        loan_id=result.loan.id,
        returned_at=result.loan.returned_at,
        fulfillment=(
            FulfillmentResponse.model_validate(result.fulfillment) if result.fulfillment else None
        ),
    )


@router.post("/return/pickup/initiate", response_model=FulfillmentResponse, status_code=201)
def return_pickup_initiate(
    body: ReturnPickupInitiateRequest,
    workflow: Annotated[ReturnBookWorkflow, Depends(_return_workflow)],
) -> FulfillmentResponse:
    dest = body.destination
    row = workflow.initiate_pickup(
        body.loan_id,
        destination_notes=dest.notes if dest else None,
        destination_class_section_id=dest.class_section_id if dest else None,
        destination_contact=dest.contact if dest else None,
    )
    return FulfillmentResponse.model_validate(row)


@router.post("/return/pickup/confirm", response_model=ReturnCommitResponse)
def return_pickup_confirm(
    body: ReturnPickupConfirmRequest,
    workflow: Annotated[ReturnBookWorkflow, Depends(_return_workflow)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=64)],
) -> ReturnCommitResponse:
    result = workflow.confirm_pickup_received(
        body.fulfillment_id,
        idempotency_key=idempotency_key,
    )
    return ReturnCommitResponse(
        loan_id=result.loan.id,
        returned_at=result.loan.returned_at,
        fulfillment=(
            FulfillmentResponse.model_validate(result.fulfillment) if result.fulfillment else None
        ),
    )


@router.post("/fulfillment/{fulfillment_id}/transition", response_model=FulfillmentResponse)
def transition_fulfillment(
    fulfillment_id: UUID,
    body: FulfillmentTransitionRequest,
    service: Annotated[FulfillmentService, Depends(_fulfillment_service)],
    session: DbSession,
) -> FulfillmentResponse:
    row = service.transition(fulfillment_id, FulfillmentStatus(body.status))
    session.commit()
    session.refresh(row)
    return FulfillmentResponse.model_validate(row)
