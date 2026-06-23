from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from lms.catalog.api.schemas import CatalogCreate, CatalogUpdate, HoldingCreate
from lms.catalog.domain.enums import CatalogingStatus, HoldingStatus
from lms.catalog.infrastructure.models.models import CatalogModel, HoldingModel
from lms.shared.http.errors import AppError, ErrorCode


@dataclass(frozen=True, slots=True)
class LendableCatalogHit:
    catalog: CatalogModel
    lendable_holdings: list[HoldingModel]


class CatalogService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_catalog_draft(self, body: CatalogCreate) -> CatalogModel:
        row = CatalogModel(
            title=body.title,
            subtitle=body.subtitle,
            isbn=body.isbn,
            language=body.language,
            subject_tags=body.subject_tags,
            call_number=body.call_number,
            ddc=body.ddc,
            notes=body.notes,
            cataloging_status=CatalogingStatus.DRAFT,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return row

    def update_catalog_metadata(self, catalog_id: UUID, body: CatalogUpdate) -> CatalogModel:
        row = self._get_catalog(catalog_id)
        if body.title is not None:
            row.title = body.title
        if body.subtitle is not None:
            row.subtitle = body.subtitle
        if body.isbn is not None:
            row.isbn = body.isbn
        if body.language is not None:
            row.language = body.language
        if body.subject_tags is not None:
            row.subject_tags = body.subject_tags
        if body.call_number is not None:
            row.call_number = body.call_number
        if body.ddc is not None:
            row.ddc = body.ddc
        if body.notes is not None:
            row.notes = body.notes
        self._session.commit()
        self._session.refresh(row)
        return row

    def publish_catalog(self, catalog_id: UUID) -> CatalogModel:
        row = self._get_catalog(catalog_id)
        if not row.title.strip():
            raise AppError(
                ErrorCode.DOMAIN_RULE_VIOLATION,
                "Title is required to publish",
                status_code=422,
            )
        row.cataloging_status = CatalogingStatus.PUBLISHED
        self._session.commit()
        self._session.refresh(row)
        return row

    def suppress_catalog(self, catalog_id: UUID) -> CatalogModel:
        row = self._get_catalog(catalog_id)
        row.cataloging_status = CatalogingStatus.SUPPRESSED
        self._session.commit()
        self._session.refresh(row)
        return row

    def get_catalog(self, catalog_id: UUID) -> CatalogModel:
        return self._get_catalog(catalog_id)

    def search_catalog_staff(self, *, q: str, limit: int = 50) -> list[CatalogModel]:
        pattern = f"%{q.strip()}%"
        stmt = (
            select(CatalogModel)
            .where(
                or_(
                    CatalogModel.title.ilike(pattern),
                    CatalogModel.isbn.ilike(pattern),
                    CatalogModel.call_number.ilike(pattern),
                )
            )
            .order_by(CatalogModel.title)
            .limit(limit)
        )
        return list(self._session.scalars(stmt))

    def search_lendable(self, *, q: str, limit: int = 50) -> list[LendableCatalogHit]:
        """Published catalogs matching query with at least one AVAILABLE circulating copy."""
        needle = q.strip()
        pattern = f"%{needle}%"
        subject_pattern = func.lower(cast(CatalogModel.subject_tags, String)).like(
            f"%{needle.lower()}%"
        )
        catalogs = list(
            self._session.scalars(
                select(CatalogModel)
                .where(
                    CatalogModel.cataloging_status == CatalogingStatus.PUBLISHED,
                    or_(
                        CatalogModel.title.ilike(pattern),
                        CatalogModel.isbn.ilike(pattern),
                        CatalogModel.call_number.ilike(pattern),
                        CatalogModel.ddc.ilike(pattern),
                        subject_pattern,
                    ),
                )
                .order_by(CatalogModel.title)
                .limit(limit)
            )
        )
        if not catalogs:
            return []

        catalog_ids = [c.id for c in catalogs]
        holdings = list(
            self._session.scalars(
                select(HoldingModel).where(
                    HoldingModel.catalog_id.in_(catalog_ids),
                    HoldingModel.holding_status == HoldingStatus.AVAILABLE,
                    HoldingModel.circulating.is_(True),
                )
            )
        )
        by_catalog: dict[UUID, list[HoldingModel]] = {cid: [] for cid in catalog_ids}
        for holding in holdings:
            by_catalog[holding.catalog_id].append(holding)

        return [
            LendableCatalogHit(catalog=c, lendable_holdings=by_catalog[c.id])
            for c in catalogs
            if by_catalog[c.id]
        ]

    def list_lendable_holdings(self, catalog_id: UUID) -> list[HoldingModel]:
        catalog = self._get_catalog(catalog_id)
        if catalog.cataloging_status != CatalogingStatus.PUBLISHED:
            return []
        stmt = (
            select(HoldingModel)
            .where(
                HoldingModel.catalog_id == catalog_id,
                HoldingModel.holding_status == HoldingStatus.AVAILABLE,
                HoldingModel.circulating.is_(True),
            )
            .order_by(HoldingModel.accession_number)
        )
        return list(self._session.scalars(stmt))

    def add_holding(self, catalog_id: UUID, body: HoldingCreate) -> HoldingModel:
        self._get_catalog(catalog_id)
        pairs = (("barcode", body.barcode), ("accession_number", body.accession_number))
        for field, value in pairs:
            dup = self._session.scalar(
                select(HoldingModel).where(getattr(HoldingModel, field) == value)
            )
            if dup is not None:
                raise AppError(ErrorCode.CONFLICT, f"{field} already exists", status_code=409)
        row = HoldingModel(
            catalog_id=catalog_id,
            barcode=body.barcode,
            accession_number=body.accession_number,
            shelf_location=body.shelf_location,
            circulating=body.circulating,
            holding_status=HoldingStatus.AVAILABLE,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return row

    def withdraw_holding(self, holding_id: UUID) -> HoldingModel:
        row = self._get_holding(holding_id)
        if row.holding_status == HoldingStatus.ON_LOAN:
            raise AppError(
                ErrorCode.DOMAIN_RULE_VIOLATION,
                "Cannot withdraw a holding that is on loan",
                status_code=422,
            )
        row.holding_status = HoldingStatus.WITHDRAWN
        self._session.commit()
        self._session.refresh(row)
        return row

    def list_holdings(self, catalog_id: UUID) -> list[HoldingModel]:
        self._get_catalog(catalog_id)
        stmt = (
            select(HoldingModel)
            .where(HoldingModel.catalog_id == catalog_id)
            .order_by(HoldingModel.accession_number)
        )
        return list(self._session.scalars(stmt))

    def get_holding_by_barcode(self, barcode: str) -> HoldingModel:
        row = self._session.scalar(select(HoldingModel).where(HoldingModel.barcode == barcode))
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, "Holding not found", status_code=404)
        return row

    def _get_catalog(self, catalog_id: UUID) -> CatalogModel:
        row = self._session.get(CatalogModel, catalog_id)
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, "Catalog not found", status_code=404)
        return row

    def _get_holding(self, holding_id: UUID) -> HoldingModel:
        row = self._session.get(HoldingModel, holding_id)
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, "Holding not found", status_code=404)
        return row
