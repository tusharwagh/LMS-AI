from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PatronTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    loan_rule_set_id: UUID | None
    created_at: datetime
    updated_at: datetime


class PatronTypeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    loan_rule_set_id: UUID | None = None


class PatronTypeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    loan_rule_set_id: UUID | None = None


class ClassSectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    grade: str
    section: str
    academic_year: str
    created_at: datetime
    updated_at: datetime


class ClassSectionCreate(BaseModel):
    grade: str = Field(min_length=1, max_length=32)
    section: str = Field(min_length=1, max_length=32)
    academic_year: str = Field(min_length=1, max_length=16)


class PatronBlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    patron_id: UUID
    reason_code: str
    active: bool
    start_at: datetime
    end_at: datetime | None
    notes: str | None


class PatronResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_ref: str | None
    display_name: str
    patron_type_id: UUID
    class_section_id: UUID | None
    status: str
    blocked: bool
    card_barcode: str | None
    created_at: datetime
    updated_at: datetime


class PatronDetailResponse(PatronResponse):
    patron_type_name: str
    class_section_label: str | None = None


class PatronCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)
    patron_type_id: UUID
    external_ref: str | None = Field(default=None, max_length=128)
    class_section_id: UUID | None = None
    card_barcode: str | None = Field(default=None, max_length=64)


class PatronUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    patron_type_id: UUID | None = None
    class_section_id: UUID | None = None
    external_ref: str | None = Field(default=None, max_length=128)
    card_barcode: str | None = Field(default=None, max_length=64)


class PatronBlockCreate(BaseModel):
    reason_code: str = Field(min_length=1, max_length=64)
    start_at: datetime
    end_at: datetime | None = None
    notes: str | None = None


class AssignClassSectionRequest(BaseModel):
    class_section_id: UUID


class AssignPatronToSectionRequest(BaseModel):
    patron_id: UUID
