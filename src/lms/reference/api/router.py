"""Reference domain API — all routes require Bearer JWT + staff role."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from lms.api.deps import DbSession
from lms.api.rbac import require_admin, require_staff
from lms.reference.api.schemas import (
    AssignClassSectionRequest,
    AssignPatronToSectionRequest,
    ClassSectionCreate,
    ClassSectionResponse,
    PatronBlockCreate,
    PatronBlockResponse,
    PatronCreate,
    PatronDetailResponse,
    PatronResponse,
    PatronTypeCreate,
    PatronTypeResponse,
    PatronTypeUpdate,
    PatronUpdate,
)
from lms.reference.application.service import ReferenceService

router = APIRouter(dependencies=[require_staff])


def _service(session: DbSession) -> ReferenceService:
    return ReferenceService(session)


@router.post(
    "/patron-types",
    response_model=PatronTypeResponse,
    status_code=201,
    dependencies=[require_admin],
)
def create_patron_type(
    body: PatronTypeCreate,
    service: Annotated[ReferenceService, Depends(_service)],
) -> PatronTypeResponse:
    return PatronTypeResponse.model_validate(service.create_patron_type(body))


@router.patch(
    "/patron-types/{type_id}",
    response_model=PatronTypeResponse,
    dependencies=[require_admin],
)
def update_patron_type(
    type_id: UUID,
    body: PatronTypeUpdate,
    service: Annotated[ReferenceService, Depends(_service)],
) -> PatronTypeResponse:
    return PatronTypeResponse.model_validate(service.update_patron_type(type_id, body))


@router.get("/patron-types", response_model=list[PatronTypeResponse])
def list_patron_types(
    service: Annotated[ReferenceService, Depends(_service)],
) -> list[PatronTypeResponse]:
    return [PatronTypeResponse.model_validate(row) for row in service.list_patron_types()]


@router.get("/patron-types/{type_id}", response_model=PatronTypeResponse)
def get_patron_type(
    type_id: UUID,
    service: Annotated[ReferenceService, Depends(_service)],
) -> PatronTypeResponse:
    return PatronTypeResponse.model_validate(service.get_patron_type(type_id))


@router.post("/patrons", response_model=PatronResponse, status_code=201)
def register_patron(
    body: PatronCreate,
    service: Annotated[ReferenceService, Depends(_service)],
) -> PatronResponse:
    return PatronResponse.model_validate(service.register_patron(body))


@router.patch("/patrons/{patron_id}", response_model=PatronResponse)
def update_patron(
    patron_id: UUID,
    body: PatronUpdate,
    service: Annotated[ReferenceService, Depends(_service)],
) -> PatronResponse:
    return PatronResponse.model_validate(service.update_patron(patron_id, body))


@router.get("/patrons/search", response_model=list[PatronDetailResponse])
def search_patrons_by_name(
    service: Annotated[ReferenceService, Depends(_service)],
    q: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[PatronDetailResponse]:
    return [service.patron_detail(row) for row in service.search_patrons_by_name(q, limit=limit)]


@router.get("/patrons/{patron_id}", response_model=PatronDetailResponse)
def get_patron(
    patron_id: UUID,
    service: Annotated[ReferenceService, Depends(_service)],
) -> PatronDetailResponse:
    return service.patron_detail(service.get_patron(patron_id))


@router.get("/patrons/by-external-ref/{external_ref}", response_model=PatronDetailResponse)
def get_patron_by_external_ref(
    external_ref: str,
    service: Annotated[ReferenceService, Depends(_service)],
) -> PatronDetailResponse:
    return service.patron_detail(service.get_patron_by_external_ref(external_ref))


@router.get("/patrons/by-card/{card_barcode}", response_model=PatronDetailResponse)
def get_patron_by_card(
    card_barcode: str,
    service: Annotated[ReferenceService, Depends(_service)],
) -> PatronDetailResponse:
    return service.patron_detail(service.get_patron_by_card(card_barcode))


@router.post("/patrons/{patron_id}/suspend", response_model=PatronResponse)
def suspend_patron(
    patron_id: UUID,
    service: Annotated[ReferenceService, Depends(_service)],
) -> PatronResponse:
    return PatronResponse.model_validate(service.suspend_patron(patron_id))


@router.post("/patrons/{patron_id}/exit", response_model=PatronResponse)
def exit_patron(
    patron_id: UUID,
    service: Annotated[ReferenceService, Depends(_service)],
) -> PatronResponse:
    return PatronResponse.model_validate(service.exit_patron(patron_id))


@router.post("/patrons/{patron_id}/blocks", response_model=PatronBlockResponse, status_code=201)
def set_patron_block(
    patron_id: UUID,
    body: PatronBlockCreate,
    service: Annotated[ReferenceService, Depends(_service)],
) -> PatronBlockResponse:
    return PatronBlockResponse.model_validate(service.set_patron_block(patron_id, body))


@router.post("/patrons/{patron_id}/blocks/{block_id}/clear", response_model=PatronBlockResponse)
def clear_patron_block(
    patron_id: UUID,
    block_id: UUID,
    service: Annotated[ReferenceService, Depends(_service)],
) -> PatronBlockResponse:
    return PatronBlockResponse.model_validate(service.clear_patron_block(patron_id, block_id))


@router.post(
    "/class-sections",
    response_model=ClassSectionResponse,
    status_code=201,
    dependencies=[require_admin],
)
def create_class_section(
    body: ClassSectionCreate,
    service: Annotated[ReferenceService, Depends(_service)],
) -> ClassSectionResponse:
    return ClassSectionResponse.model_validate(service.create_class_section(body))


@router.get("/class-sections", response_model=list[ClassSectionResponse])
def list_class_sections(
    service: Annotated[ReferenceService, Depends(_service)],
    academic_year: Annotated[str | None, Query()] = None,
) -> list[ClassSectionResponse]:
    return [
        ClassSectionResponse.model_validate(row)
        for row in service.list_class_sections(academic_year=academic_year)
    ]


@router.get("/class-sections/{section_id}", response_model=ClassSectionResponse)
def get_class_section(
    section_id: UUID,
    service: Annotated[ReferenceService, Depends(_service)],
) -> ClassSectionResponse:
    return ClassSectionResponse.model_validate(service.get_class_section(section_id))


@router.post("/patrons/{patron_id}/assign-class-section", response_model=PatronResponse)
def assign_patron_to_class_section(
    patron_id: UUID,
    body: AssignClassSectionRequest,
    service: Annotated[ReferenceService, Depends(_service)],
) -> PatronResponse:
    return PatronResponse.model_validate(service.assign_patron_to_class_section(patron_id, body))


@router.post("/class-sections/{section_id}/assign-patron", response_model=PatronResponse)
def assign_patron_to_section(
    section_id: UUID,
    body: AssignPatronToSectionRequest,
    service: Annotated[ReferenceService, Depends(_service)],
) -> PatronResponse:
    return PatronResponse.model_validate(service.assign_patron_to_section_by_id(section_id, body))
