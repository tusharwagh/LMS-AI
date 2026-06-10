"""HoldingLendabilityPort adapter (ADR-004)."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from lms.catalog.domain.enums import CatalogingStatus, HoldingStatus
from lms.catalog.infrastructure.models.models import CatalogModel, HoldingModel


@dataclass(frozen=True, slots=True)
class HoldingLendability:
    holding_id: UUID
    catalog_id: UUID
    is_published: bool
    holding_status: str
    circulating: bool
    is_lendable: bool


class HoldingLendabilityAdapter:
    """Implements loan.domain.ports.HoldingLendabilityPort."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def check(self, holding_id: UUID) -> HoldingLendability:
        holding = self._session.get(HoldingModel, holding_id)
        if holding is None:
            raise ValueError(f"Holding {holding_id} not found")
        catalog = self._session.get(CatalogModel, holding.catalog_id)
        if catalog is None:
            raise ValueError(f"Catalog for holding {holding_id} not found")
        return HoldingLendability(
            holding_id=holding_id,
            catalog_id=holding.catalog_id,
            is_published=catalog.cataloging_status == CatalogingStatus.PUBLISHED,
            holding_status=holding.holding_status,
            circulating=holding.circulating,
            is_lendable=(
                catalog.cataloging_status == CatalogingStatus.PUBLISHED
                and holding.circulating
                and holding.holding_status == HoldingStatus.AVAILABLE
            ),
        )
