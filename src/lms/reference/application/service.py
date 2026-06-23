from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from lms.reference.api.schemas import (
    AssignClassSectionRequest,
    AssignPatronToSectionRequest,
    ClassSectionCreate,
    PatronBlockCreate,
    PatronCreate,
    PatronDetailResponse,
    PatronResponse,
    PatronTypeCreate,
    PatronTypeUpdate,
    PatronUpdate,
)
from lms.reference.domain.enums import PatronStatus
from lms.reference.infrastructure.models.models import (
    ClassSectionModel,
    PatronBlockModel,
    PatronModel,
    PatronTypeModel,
)
from lms.shared.http.errors import AppError, ErrorCode


class ReferenceService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_patron_type(self, body: PatronTypeCreate) -> PatronTypeModel:
        existing = self._session.scalar(
            select(PatronTypeModel).where(PatronTypeModel.code == body.code)
        )
        if existing is not None:
            raise AppError(
                ErrorCode.CONFLICT,
                f"Patron type code '{body.code}' already exists",
                status_code=409,
            )
        if body.loan_rule_set_id is not None:
            self._require_loan_rule_set(body.loan_rule_set_id)
        row = PatronTypeModel(
            code=body.code.upper(),
            name=body.name,
            loan_rule_set_id=body.loan_rule_set_id,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return row

    def update_patron_type(self, type_id: UUID, body: PatronTypeUpdate) -> PatronTypeModel:
        row = self._get_patron_type(type_id)
        if body.name is not None:
            row.name = body.name
        if body.loan_rule_set_id is not None:
            self._require_loan_rule_set(body.loan_rule_set_id)
            row.loan_rule_set_id = body.loan_rule_set_id
        self._session.commit()
        self._session.refresh(row)
        return row

    def list_patron_types(self) -> list[PatronTypeModel]:
        return list(self._session.scalars(select(PatronTypeModel).order_by(PatronTypeModel.code)))

    def get_patron_type(self, type_id: UUID) -> PatronTypeModel:
        return self._get_patron_type(type_id)

    def register_patron(self, body: PatronCreate) -> PatronModel:
        self._get_patron_type(body.patron_type_id)
        if body.class_section_id is not None:
            self._get_class_section(body.class_section_id)
        if body.external_ref is not None:
            dup = self._session.scalar(
                select(PatronModel).where(PatronModel.external_ref == body.external_ref)
            )
            if dup is not None:
                raise AppError(
                    ErrorCode.CONFLICT,
                    "External ref already registered",
                    status_code=409,
                )
        if body.card_barcode is not None:
            dup = self._session.scalar(
                select(PatronModel).where(PatronModel.card_barcode == body.card_barcode)
            )
            if dup is not None:
                raise AppError(
                    ErrorCode.CONFLICT,
                    "Card barcode already assigned",
                    status_code=409,
                )
        row = PatronModel(
            display_name=body.display_name,
            patron_type_id=body.patron_type_id,
            external_ref=body.external_ref,
            class_section_id=body.class_section_id,
            card_barcode=body.card_barcode,
            status=PatronStatus.ACTIVE,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return row

    def update_patron(self, patron_id: UUID, body: PatronUpdate) -> PatronModel:
        row = self._get_patron(patron_id)
        if body.patron_type_id is not None:
            self._get_patron_type(body.patron_type_id)
            row.patron_type_id = body.patron_type_id
        if body.class_section_id is not None:
            self._get_class_section(body.class_section_id)
            row.class_section_id = body.class_section_id
        if body.display_name is not None:
            row.display_name = body.display_name
        if body.external_ref is not None:
            dup = self._session.scalar(
                select(PatronModel).where(
                    PatronModel.external_ref == body.external_ref,
                    PatronModel.id != patron_id,
                )
            )
            if dup is not None:
                raise AppError(ErrorCode.CONFLICT, "External ref already in use", status_code=409)
            row.external_ref = body.external_ref
        if body.card_barcode is not None:
            dup = self._session.scalar(
                select(PatronModel).where(
                    PatronModel.card_barcode == body.card_barcode,
                    PatronModel.id != patron_id,
                )
            )
            if dup is not None:
                raise AppError(ErrorCode.CONFLICT, "Card barcode already in use", status_code=409)
            row.card_barcode = body.card_barcode
        self._session.commit()
        self._session.refresh(row)
        return row

    def get_patron(self, patron_id: UUID) -> PatronModel:
        return self._get_patron(patron_id)

    def patron_detail(self, patron: PatronModel) -> PatronDetailResponse:
        patron_type = self._get_patron_type(patron.patron_type_id)
        section_label = None
        if patron.class_section_id is not None:
            section = self._get_class_section(patron.class_section_id)
            section_label = f"Grade {section.grade} {section.section} ({section.academic_year})"
        base = PatronResponse.model_validate(patron)
        return PatronDetailResponse(
            **base.model_dump(),
            patron_type_name=patron_type.name,
            class_section_label=section_label,
        )

    def get_patron_by_external_ref(self, external_ref: str) -> PatronModel:
        row = self._session.scalar(
            select(PatronModel).where(PatronModel.external_ref == external_ref)
        )
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, "Patron not found", status_code=404)
        return row

    def get_patron_by_card(self, card_barcode: str) -> PatronModel:
        row = self._session.scalar(
            select(PatronModel).where(PatronModel.card_barcode == card_barcode)
        )
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, "Patron not found", status_code=404)
        return row

    def search_patrons_by_name(self, query: str, *, limit: int = 20) -> list[PatronModel]:
        term = query.strip()
        if not term:
            return []
        pattern = f"%{term}%"
        stmt = (
            select(PatronModel)
            .where(PatronModel.display_name.ilike(pattern))
            .order_by(PatronModel.display_name)
            .limit(min(limit, 50))
        )
        return list(self._session.scalars(stmt))

    def suspend_patron(self, patron_id: UUID) -> PatronModel:
        row = self._get_patron(patron_id)
        row.status = PatronStatus.SUSPENDED
        self._session.commit()
        self._session.refresh(row)
        return row

    def exit_patron(self, patron_id: UUID) -> PatronModel:
        row = self._get_patron(patron_id)
        row.status = PatronStatus.EXITED
        self._session.commit()
        self._session.refresh(row)
        return row

    def set_patron_block(self, patron_id: UUID, body: PatronBlockCreate) -> PatronBlockModel:
        self._get_patron(patron_id)
        block = PatronBlockModel(
            patron_id=patron_id,
            reason_code=body.reason_code,
            active=True,
            start_at=body.start_at,
            end_at=body.end_at,
            notes=body.notes,
        )
        self._session.add(block)
        patron = self._get_patron(patron_id)
        patron.blocked = True
        self._session.commit()
        self._session.refresh(block)
        return block

    def clear_patron_block(self, patron_id: UUID, block_id: UUID) -> PatronBlockModel:
        block = self._session.get(PatronBlockModel, block_id)
        if block is None or block.patron_id != patron_id:
            raise AppError(ErrorCode.NOT_FOUND, "Block not found", status_code=404)
        block.active = False
        active_blocks = self._session.scalars(
            select(PatronBlockModel).where(
                PatronBlockModel.patron_id == patron_id,
                PatronBlockModel.active.is_(True),
                PatronBlockModel.id != block_id,
            )
        ).all()
        if not active_blocks:
            patron = self._get_patron(patron_id)
            patron.blocked = False
        self._session.commit()
        self._session.refresh(block)
        return block

    def create_class_section(self, body: ClassSectionCreate) -> ClassSectionModel:
        dup = self._session.scalar(
            select(ClassSectionModel).where(
                ClassSectionModel.grade == body.grade,
                ClassSectionModel.section == body.section,
                ClassSectionModel.academic_year == body.academic_year,
            )
        )
        if dup is not None:
            raise AppError(ErrorCode.CONFLICT, "Class section already exists", status_code=409)
        row = ClassSectionModel(
            grade=body.grade,
            section=body.section,
            academic_year=body.academic_year,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return row

    def list_class_sections(self, *, academic_year: str | None = None) -> list[ClassSectionModel]:
        stmt = select(ClassSectionModel).order_by(
            ClassSectionModel.academic_year,
            ClassSectionModel.grade,
            ClassSectionModel.section,
        )
        if academic_year is not None:
            stmt = stmt.where(ClassSectionModel.academic_year == academic_year)
        return list(self._session.scalars(stmt))

    def get_class_section(self, section_id: UUID) -> ClassSectionModel:
        return self._get_class_section(section_id)

    def assign_patron_to_class_section(
        self, patron_id: UUID, body: AssignClassSectionRequest
    ) -> PatronModel:
        self._get_class_section(body.class_section_id)
        row = self._get_patron(patron_id)
        row.class_section_id = body.class_section_id
        self._session.commit()
        self._session.refresh(row)
        return row

    def assign_patron_to_section_by_id(
        self, section_id: UUID, body: AssignPatronToSectionRequest
    ) -> PatronModel:
        return self.assign_patron_to_class_section(
            body.patron_id, AssignClassSectionRequest(class_section_id=section_id)
        )

    def _get_patron(self, patron_id: UUID) -> PatronModel:
        row = self._session.get(PatronModel, patron_id)
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, "Patron not found", status_code=404)
        return row

    def _get_patron_type(self, type_id: UUID) -> PatronTypeModel:
        row = self._session.get(PatronTypeModel, type_id)
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, "Patron type not found", status_code=404)
        return row

    def _get_class_section(self, section_id: UUID) -> ClassSectionModel:
        row = self._session.get(ClassSectionModel, section_id)
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, "Class section not found", status_code=404)
        return row

    def _require_loan_rule_set(self, rule_set_id: UUID) -> None:
        from sqlalchemy import text

        found = self._session.scalar(
            text("SELECT 1 FROM loan_rule_sets WHERE id = :id"),
            {"id": rule_set_id},
        )
        if found is None:
            raise AppError(ErrorCode.NOT_FOUND, "Loan rule set not found", status_code=404)

    @staticmethod
    def is_patron_blocked_now(block: PatronBlockModel, now: datetime | None = None) -> bool:
        if not block.active:
            return False
        now = now or datetime.now(UTC)
        if block.start_at > now:
            return False
        if block.end_at is not None and block.end_at < now:
            return False
        return True
