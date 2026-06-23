"""Catalog domain API — all routes require Bearer JWT + staff role."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from lms.catalog.api.schemas import (
    CatalogCreate,
    CatalogResponse,
    CatalogUpdate,
    HoldingCreate,
    HoldingResponse,
)
from lms.catalog.application.service import CatalogService, LendableCatalogHit
from lms.platform.auth.rbac import require_staff
from lms.shared.auth.deps import DbSession

router = APIRouter(dependencies=[require_staff])


def _service(session: DbSession) -> CatalogService:
    return CatalogService(session)


@router.post("/catalogs", response_model=CatalogResponse, status_code=201)
def create_catalog_draft(
    body: CatalogCreate,
    service: Annotated[CatalogService, Depends(_service)],
) -> CatalogResponse:
    return CatalogResponse.model_validate(service.create_catalog_draft(body))


@router.patch("/catalogs/{catalog_id}", response_model=CatalogResponse)
def update_catalog_metadata(
    catalog_id: UUID,
    body: CatalogUpdate,
    service: Annotated[CatalogService, Depends(_service)],
) -> CatalogResponse:
    return CatalogResponse.model_validate(service.update_catalog_metadata(catalog_id, body))


@router.post("/catalogs/{catalog_id}/publish", response_model=CatalogResponse)
def publish_catalog(
    catalog_id: UUID,
    service: Annotated[CatalogService, Depends(_service)],
) -> CatalogResponse:
    return CatalogResponse.model_validate(service.publish_catalog(catalog_id))


@router.post("/catalogs/{catalog_id}/suppress", response_model=CatalogResponse)
def suppress_catalog(
    catalog_id: UUID,
    service: Annotated[CatalogService, Depends(_service)],
) -> CatalogResponse:
    return CatalogResponse.model_validate(service.suppress_catalog(catalog_id))


@router.get("/catalogs/search", response_model=list[CatalogResponse])
def search_catalog_staff(
    service: Annotated[CatalogService, Depends(_service)],
    q: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[CatalogResponse]:
    return [
        CatalogResponse.model_validate(row)
        for row in service.search_catalog_staff(q=q, limit=limit)
    ]


@router.get("/catalogs/search/lendable")
def search_lendable_catalog(
    service: Annotated[CatalogService, Depends(_service)],
    q: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, Any]]:
    hits = service.search_lendable(q=q, limit=limit)
    return [_lendable_hit_to_dict(hit) for hit in hits]


@router.get("/catalogs/{catalog_id}/holdings/lendable", response_model=list[HoldingResponse])
def list_lendable_holdings(
    catalog_id: UUID,
    service: Annotated[CatalogService, Depends(_service)],
) -> list[HoldingResponse]:
    return [
        HoldingResponse.model_validate(row) for row in service.list_lendable_holdings(catalog_id)
    ]


def _lendable_hit_to_dict(hit: LendableCatalogHit) -> dict[str, Any]:
    catalog = hit.catalog
    return {
        "catalog": CatalogResponse.model_validate(catalog).model_dump(mode="json"),
        "lendable_holdings": [
            HoldingResponse.model_validate(h).model_dump(mode="json") for h in hit.lendable_holdings
        ],
    }


@router.get("/catalogs/{catalog_id}", response_model=CatalogResponse)
def get_catalog(
    catalog_id: UUID,
    service: Annotated[CatalogService, Depends(_service)],
) -> CatalogResponse:
    return CatalogResponse.model_validate(service.get_catalog(catalog_id))


@router.post("/catalogs/{catalog_id}/holdings", response_model=HoldingResponse, status_code=201)
def add_holding(
    catalog_id: UUID,
    body: HoldingCreate,
    service: Annotated[CatalogService, Depends(_service)],
) -> HoldingResponse:
    return HoldingResponse.model_validate(service.add_holding(catalog_id, body))


@router.get("/catalogs/{catalog_id}/holdings", response_model=list[HoldingResponse])
def list_holdings(
    catalog_id: UUID,
    service: Annotated[CatalogService, Depends(_service)],
) -> list[HoldingResponse]:
    return [HoldingResponse.model_validate(row) for row in service.list_holdings(catalog_id)]


@router.post("/holdings/{holding_id}/withdraw", response_model=HoldingResponse)
def withdraw_holding(
    holding_id: UUID,
    service: Annotated[CatalogService, Depends(_service)],
) -> HoldingResponse:
    return HoldingResponse.model_validate(service.withdraw_holding(holding_id))


@router.get("/holdings/by-barcode/{barcode}", response_model=HoldingResponse)
def get_holding_by_barcode(
    barcode: str,
    service: Annotated[CatalogService, Depends(_service)],
) -> HoldingResponse:
    return HoldingResponse.model_validate(service.get_holding_by_barcode(barcode))
