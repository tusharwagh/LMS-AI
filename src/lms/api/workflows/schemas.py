from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lms.loan.domain.enums import FulfillmentMode


class RuleViolationResponse(BaseModel):
    rule_id: str
    message: str


class ValidationReportResponse(BaseModel):
    is_valid: bool
    violations: list[RuleViolationResponse]


class FulfillmentDestination(BaseModel):
    notes: str | None = Field(default=None, max_length=512)
    class_section_id: UUID | None = None
    contact: str | None = Field(default=None, max_length=255)


class IssueStartRequest(BaseModel):
    patron_id: UUID | None = None
    card_barcode: str | None = Field(default=None, max_length=64)
    external_ref: str | None = Field(default=None, max_length=128)
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    search_query: str | None = Field(default=None, min_length=1, max_length=256)

    @model_validator(mode="after")
    def require_patron_lookup(self) -> "IssueStartRequest":
        if not any([self.patron_id, self.card_barcode, self.external_ref, self.display_name]):
            raise ValueError(
                "One of patron_id, card_barcode, external_ref, or display_name is required"
            )
        return self


class IssueSearchPatronsRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)
    limit: int = Field(default=20, ge=1, le=50)


class PatronSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    external_ref: str | None
    card_barcode: str | None
    status: str


class IssueSearchPatronsResponse(BaseModel):
    patrons: list[PatronSummaryResponse]


class IssueBackRequest(BaseModel):
    target_step: int = Field(ge=1, le=4)
    loan_id: UUID | None = None


class IssueBackResponse(BaseModel):
    target_step: int
    allowed: bool
    message: str


class IssueCancelRequest(BaseModel):
    loan_id: UUID


class IssueCancelResponse(BaseModel):
    loan_id: UUID
    returned_at: datetime
    holding_id: UUID
    fulfillment_cancelled: bool


class LendableCopySummary(BaseModel):
    holding_id: UUID
    barcode: str
    accession_number: str
    shelf_location: str | None


class IssueSearchHit(BaseModel):
    catalog_id: UUID
    title: str
    lendable_copies: list[LendableCopySummary]


class IssueStartResponse(BaseModel):
    patron_id: UUID
    patron_display_name: str
    patron_validation: ValidationReportResponse
    search_results: list[IssueSearchHit]


class IssueValidateRequest(BaseModel):
    patron_id: UUID
    holding_id: UUID


class IssueCommitRequest(BaseModel):
    patron_id: UUID
    holding_id: UUID
    fulfillment_mode: FulfillmentMode = FulfillmentMode.DESK
    destination: FulfillmentDestination | None = None


class FulfillmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    loan_id: UUID | None
    holding_id: UUID
    direction: str
    mode: str
    status: str
    destination_notes: str | None
    destination_class_section_id: UUID | None
    destination_contact: str | None
    created_at: datetime
    updated_at: datetime


class IssueCommitResponse(BaseModel):
    loan_id: UUID
    patron_id: UUID
    holding_id: UUID
    due_date: date
    validation: ValidationReportResponse
    fulfillment: FulfillmentResponse | None = None


class ReturnStartRequest(BaseModel):
    barcode: str | None = Field(default=None, max_length=64)
    loan_id: UUID | None = None

    @model_validator(mode="after")
    def require_lookup(self) -> "ReturnStartRequest":
        if not self.barcode and not self.loan_id:
            raise ValueError("Either barcode or loan_id is required")
        return self


class ReturnStartResponse(BaseModel):
    loan_id: UUID
    holding_id: UUID
    holding_barcode: str
    patron_id: UUID
    patron_display_name: str
    catalog_title: str
    due_date: date
    is_overdue: bool
    open_loans_for_patron: int


class ReturnCommitRequest(BaseModel):
    barcode: str | None = Field(default=None, max_length=64)
    loan_id: UUID | None = None

    @model_validator(mode="after")
    def require_lookup(self) -> "ReturnCommitRequest":
        if not self.barcode and not self.loan_id:
            raise ValueError("Either barcode or loan_id is required")
        return self


class ReturnCommitResponse(BaseModel):
    loan_id: UUID
    returned_at: datetime | None
    fulfillment: FulfillmentResponse | None = None


class ReturnPickupInitiateRequest(BaseModel):
    loan_id: UUID
    destination: FulfillmentDestination | None = None


class ReturnPickupConfirmRequest(BaseModel):
    fulfillment_id: UUID


class FulfillmentTransitionRequest(BaseModel):
    status: str = Field(min_length=1, max_length=16)
