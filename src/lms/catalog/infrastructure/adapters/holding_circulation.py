"""HoldingCirculationPort adapter — catalog-side mutations for Loan (ADR-004)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from lms.catalog.domain.enums import CatalogingStatus, HoldingStatus
from lms.catalog.infrastructure.models.models import CatalogModel, HoldingModel
from lms.loan.domain.ports import HoldingSnapshot


class HoldingCirculationAdapter:
    def __init__(self, session: Session) -> None:
        self._session = session

    def lock_for_checkout(self, holding_id: UUID) -> HoldingSnapshot:
        holding = self._session.scalar(
            select(HoldingModel).where(HoldingModel.id == holding_id).with_for_update()
        )
        if holding is None:
            raise ValueError(f"Holding {holding_id} not found")
        catalog = self._session.get(CatalogModel, holding.catalog_id)
        if catalog is None:
            raise ValueError(f"Catalog for holding {holding_id} not found")
        is_published = catalog.cataloging_status == CatalogingStatus.PUBLISHED
        is_lendable = (
            is_published
            and holding.circulating
            and holding.holding_status == HoldingStatus.AVAILABLE
        )
        return HoldingSnapshot(
            holding_id=holding_id,
            catalog_id=holding.catalog_id,
            is_published=is_published,
            holding_status=holding.holding_status,
            circulating=holding.circulating,
            is_lendable=is_lendable,
        )

    def mark_on_loan(self, holding_id: UUID) -> None:
        holding = self._session.get(HoldingModel, holding_id)
        if holding is None:
            raise ValueError(f"Holding {holding_id} not found")
        holding.holding_status = HoldingStatus.ON_LOAN

    def lock_for_return(self, holding_id: UUID) -> None:
        row = self._session.scalar(
            select(HoldingModel).where(HoldingModel.id == holding_id).with_for_update()
        )
        if row is None:
            raise ValueError(f"Holding {holding_id} not found")

    def mark_available(self, holding_id: UUID) -> None:
        holding = self._session.get(HoldingModel, holding_id)
        if holding is None:
            raise ValueError(f"Holding {holding_id} not found")
        holding.holding_status = HoldingStatus.AVAILABLE
