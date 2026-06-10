from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CatalogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    subtitle: str | None
    isbn: str | None
    language: str
    subject_tags: list[str]
    call_number: str | None
    ddc: str | None
    cataloging_status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


class CatalogCreate(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    subtitle: str | None = Field(default=None, max_length=512)
    isbn: str | None = Field(default=None, max_length=20)
    language: str = Field(default="en", max_length=16)
    subject_tags: list[str] = Field(default_factory=list)
    call_number: str | None = Field(default=None, max_length=64)
    ddc: str | None = Field(default=None, max_length=32)
    notes: str | None = None


class CatalogUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=512)
    subtitle: str | None = Field(default=None, max_length=512)
    isbn: str | None = Field(default=None, max_length=20)
    language: str | None = Field(default=None, max_length=16)
    subject_tags: list[str] | None = None
    call_number: str | None = Field(default=None, max_length=64)
    ddc: str | None = Field(default=None, max_length=32)
    notes: str | None = None


class HoldingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    catalog_id: UUID
    barcode: str
    accession_number: str
    shelf_location: str | None
    holding_status: str
    circulating: bool
    created_at: datetime
    updated_at: datetime


class HoldingCreate(BaseModel):
    barcode: str = Field(min_length=1, max_length=64)
    accession_number: str = Field(min_length=1, max_length=64)
    shelf_location: str | None = Field(default=None, max_length=128)
    circulating: bool = True
