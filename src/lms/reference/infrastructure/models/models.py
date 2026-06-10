import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lms.reference.domain.enums import PatronStatus
from lms.shared.db.base import Base
from lms.shared.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class PatronTypeModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "patron_types"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    loan_rule_set_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("loan_rule_sets.id"), nullable=True
    )

    patrons: Mapped[list["PatronModel"]] = relationship(back_populates="patron_type")


class ClassSectionModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "class_sections"
    __table_args__ = (
        UniqueConstraint("grade", "section", "academic_year", name="uq_class_section"),
    )

    grade: Mapped[str] = mapped_column(String(32), nullable=False)
    section: Mapped[str] = mapped_column(String(32), nullable=False)
    academic_year: Mapped[str] = mapped_column(String(16), nullable=False)

    patrons: Mapped[list["PatronModel"]] = relationship(back_populates="class_section")


class PatronModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "patrons"

    external_ref: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    patron_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patron_types.id"), nullable=False
    )
    class_section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_sections.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=PatronStatus.ACTIVE)
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    card_barcode: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)

    patron_type: Mapped[PatronTypeModel] = relationship(back_populates="patrons")
    class_section: Mapped[ClassSectionModel | None] = relationship(back_populates="patrons")
    blocks: Mapped[list["PatronBlockModel"]] = relationship(back_populates="patron")


class PatronBlockModel(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "patron_blocks"

    patron_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patrons.id"), nullable=False
    )
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    patron: Mapped[PatronModel] = relationship(back_populates="blocks")
