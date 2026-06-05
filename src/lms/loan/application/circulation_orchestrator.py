"""Cross-context write coordinator for CheckoutHolding / ReturnHolding (ADR-002)."""

from uuid import UUID

from sqlalchemy.orm import Session

from lms.loan.domain.ports import HoldingLendabilityPort, PatronEligibilityPort, PolicyResolverPort


class CirculationOrchestrator:
    def __init__(
        self,
        session: Session,
        patron_eligibility: PatronEligibilityPort,
        holding_lendability: HoldingLendabilityPort,
        policy_resolver: PolicyResolverPort,
    ) -> None:
        self._session = session
        self._patron_eligibility = patron_eligibility
        self._holding_lendability = holding_lendability
        self._policy_resolver = policy_resolver

    def checkout(self, patron_id: UUID, holding_id: UUID, *, idempotency_key: str) -> None:
        """Single transaction + row lock pattern — MVP.md §13.2."""
        raise NotImplementedError("Phase 4 — Circulation kernel")

    def return_holding(
        self,
        *,
        holding_id: UUID | None = None,
        loan_id: UUID | None = None,
        idempotency_key: str,
    ) -> None:
        raise NotImplementedError("Phase 4 — Circulation kernel")
