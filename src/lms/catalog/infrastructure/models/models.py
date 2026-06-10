import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lms.catalog.domain.enums import CatalogingStatus, HoldingStatus
from lms.shared.db.base import Base
from lms.shared.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class CatalogModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "catalogs"

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(512), nullable=True)
    isbn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    subject_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    call_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ddc: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cataloging_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=CatalogingStatus.DRAFT
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    holdings: Mapped[list["HoldingModel"]] = relationship(back_populates="catalog")


class HoldingModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "holdings"

    catalog_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalogs.id"), nullable=False
    )
    barcode: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    accession_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    shelf_location: Mapped[str | None] = mapped_column(String(128), nullable=True)
    holding_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=HoldingStatus.AVAILABLE
    )
    circulating: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    catalog: Mapped[CatalogModel] = relationship(back_populates="holdings")
