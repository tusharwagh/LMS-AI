"""PatronEligibilityPort adapter (ADR-004)."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from lms.loan.domain.ports import PatronEligibilitySnapshot
from lms.reference.application.service import ReferenceService
from lms.reference.domain.enums import PatronStatus
from lms.reference.infrastructure.models.models import PatronBlockModel, PatronModel


class PatronEligibilityAdapter:
    """Implements loan.domain.ports.PatronEligibilityPort."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def check(self, patron_id: UUID) -> PatronEligibilitySnapshot:
        patron = self._session.get(PatronModel, patron_id)
        if patron is None:
            raise ValueError(f"Patron {patron_id} not found")

        now = datetime.now(UTC)
        active_block = self._session.scalar(
            select(PatronBlockModel).where(
                PatronBlockModel.patron_id == patron_id,
                PatronBlockModel.active.is_(True),
            )
        )
        is_blocked = patron.blocked or (
            active_block is not None and ReferenceService.is_patron_blocked_now(active_block, now)
        )

        open_loan_count = self._session.scalar(
            text("SELECT COUNT(*) FROM loans WHERE patron_id = :patron_id AND returned_at IS NULL"),
            {"patron_id": patron_id},
        )
        open_loan_count = int(open_loan_count or 0)

        return PatronEligibilitySnapshot(
            patron_id=patron_id,
            is_active=patron.status == PatronStatus.ACTIVE,
            is_blocked=is_blocked,
            open_loan_count=open_loan_count,
            patron_type_id=patron.patron_type_id,
        )
