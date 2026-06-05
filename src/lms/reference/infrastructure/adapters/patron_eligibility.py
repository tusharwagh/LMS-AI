"""PatronEligibilityPort adapter (ADR-004)."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class PatronEligibility:
    patron_id: UUID
    is_active: bool
    is_blocked: bool
    open_loan_count: int
    patron_type_id: UUID


class PatronEligibilityAdapter:
    """Implements loan.domain.ports.PatronEligibilityPort."""

    def check(self, patron_id: UUID) -> PatronEligibility:
        raise NotImplementedError("Phase 1 — Reference")
