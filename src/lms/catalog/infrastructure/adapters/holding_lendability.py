"""HoldingLendabilityPort adapter (ADR-004)."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class HoldingLendability:
    holding_id: UUID
    catalog_id: UUID
    is_published: bool
    holding_status: str


class HoldingLendabilityAdapter:
    """Implements loan.domain.ports.HoldingLendabilityPort."""

    def check(self, holding_id: UUID) -> HoldingLendability:
        raise NotImplementedError("Phase 3 — Catalog")
