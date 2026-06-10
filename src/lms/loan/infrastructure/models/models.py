import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from lms.loan.domain.enums import CalendarPolicy
from lms.shared.db.base import Base
from lms.shared.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class LoanRuleSetModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "loan_rule_sets"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    max_active_loans: Mapped[int] = mapped_column(Integer, nullable=False)
    loan_period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    calendar_policy: Mapped[str] = mapped_column(
        String(32), nullable=False, default=CalendarPolicy.CALENDAR_DAYS
    )


class LoanModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "loans"

    patron_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patrons.id"), nullable=False
    )
    holding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("holdings.id"), nullable=False
    )
    loan_rule_set_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("loan_rule_sets.id"), nullable=True
    )
    checkout_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checkout_operator_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class CirculationFulfillmentModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "circulation_fulfillments"

    loan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("loans.id"), nullable=True
    )
    holding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("holdings.id"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    destination_notes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    destination_class_section_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("class_sections.id"), nullable=True
    )
    destination_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)
