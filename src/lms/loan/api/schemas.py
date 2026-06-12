from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LoanRuleSetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    max_active_loans: int
    loan_period_days: int
    calendar_policy: str
    created_at: datetime
    updated_at: datetime


class LoanRuleSetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    max_active_loans: int = Field(ge=0)
    loan_period_days: int = Field(ge=1)
    calendar_policy: str = "CALENDAR_DAYS"


class LoanRuleSetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    max_active_loans: int | None = Field(default=None, ge=0)
    loan_period_days: int | None = Field(default=None, ge=1)
    calendar_policy: str | None = None


class LoanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patron_id: UUID
    holding_id: UUID
    loan_rule_set_id: UUID | None
    checkout_at: datetime
    due_date: date
    returned_at: datetime | None
    checkout_operator_id: str | None
    created_at: datetime
    updated_at: datetime


class LoanDetailResponse(LoanResponse):
    patron_display_name: str
    holding_barcode: str
    catalog_title: str


class CheckoutRequest(BaseModel):
    patron_id: UUID
    holding_id: UUID


class ReturnRequest(BaseModel):
    holding_id: UUID | None = None
    loan_id: UUID | None = None

    @model_validator(mode="after")
    def require_lookup(self) -> "ReturnRequest":
        if not self.holding_id and not self.loan_id:
            raise ValueError("Either holding_id or loan_id is required")
        return self
