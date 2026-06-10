from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from lms.api.errors import AppError, ErrorCode
from lms.catalog.infrastructure.models.models import CatalogModel, HoldingModel
from lms.loan.api.schemas import LoanRuleSetCreate, LoanRuleSetUpdate
from lms.loan.domain.enums import CalendarPolicy
from lms.loan.infrastructure.models.models import LoanModel, LoanRuleSetModel
from lms.reference.infrastructure.models.models import PatronModel
from lms.shared.time import library_today


@dataclass(frozen=True, slots=True)
class LoanDetailRow:
    loan: LoanModel
    patron_display_name: str
    holding_barcode: str
    catalog_title: str


class LoanService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def configure_loan_rule_set(self, body: LoanRuleSetCreate) -> LoanRuleSetModel:
        row = LoanRuleSetModel(
            name=body.name,
            max_active_loans=body.max_active_loans,
            loan_period_days=body.loan_period_days,
            calendar_policy=body.calendar_policy or CalendarPolicy.CALENDAR_DAYS,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return row

    def update_loan_rule_set(self, rule_set_id: UUID, body: LoanRuleSetUpdate) -> LoanRuleSetModel:
        row = self._get_rule_set(rule_set_id)
        if body.name is not None:
            row.name = body.name
        if body.max_active_loans is not None:
            row.max_active_loans = body.max_active_loans
        if body.loan_period_days is not None:
            row.loan_period_days = body.loan_period_days
        if body.calendar_policy is not None:
            row.calendar_policy = body.calendar_policy
        self._session.commit()
        self._session.refresh(row)
        return row

    def list_loan_rule_sets(self) -> list[LoanRuleSetModel]:
        return list(self._session.scalars(select(LoanRuleSetModel).order_by(LoanRuleSetModel.name)))

    def get_loan_rule_set(self, rule_set_id: UUID) -> LoanRuleSetModel:
        return self._get_rule_set(rule_set_id)

    def list_open_loans_by_patron(self, patron_id: UUID) -> list[LoanModel]:
        stmt = (
            select(LoanModel)
            .where(LoanModel.patron_id == patron_id, LoanModel.returned_at.is_(None))
            .order_by(LoanModel.checkout_at.desc())
        )
        return list(self._session.scalars(stmt))

    def list_open_loan_details_by_patron(self, patron_id: UUID) -> list[LoanDetailRow]:
        stmt = (
            select(
                LoanModel,
                PatronModel.display_name,
                HoldingModel.barcode,
                CatalogModel.title,
            )
            .join(PatronModel, LoanModel.patron_id == PatronModel.id)
            .join(HoldingModel, LoanModel.holding_id == HoldingModel.id)
            .join(CatalogModel, HoldingModel.catalog_id == CatalogModel.id)
            .where(LoanModel.patron_id == patron_id, LoanModel.returned_at.is_(None))
            .order_by(LoanModel.checkout_at.desc())
        )
        return [self._loan_detail_row(row) for row in self._session.execute(stmt).all()]

    def list_overdue_loans(self, *, as_of: date | None = None) -> list[LoanModel]:
        as_of = as_of or library_today()
        stmt = (
            select(LoanModel)
            .where(LoanModel.returned_at.is_(None), LoanModel.due_date < as_of)
            .order_by(LoanModel.due_date, LoanModel.checkout_at)
        )
        return list(self._session.scalars(stmt))

    def list_overdue_loan_details(self, *, as_of: date | None = None) -> list[LoanDetailRow]:
        as_of = as_of or library_today()
        stmt = (
            select(
                LoanModel,
                PatronModel.display_name,
                HoldingModel.barcode,
                CatalogModel.title,
            )
            .join(PatronModel, LoanModel.patron_id == PatronModel.id)
            .join(HoldingModel, LoanModel.holding_id == HoldingModel.id)
            .join(CatalogModel, HoldingModel.catalog_id == CatalogModel.id)
            .where(LoanModel.returned_at.is_(None), LoanModel.due_date < as_of)
            .order_by(LoanModel.due_date, LoanModel.checkout_at)
        )
        return [self._loan_detail_row(row) for row in self._session.execute(stmt).all()]

    @staticmethod
    def _loan_detail_row(row: tuple) -> LoanDetailRow:
        loan, patron_display_name, holding_barcode, catalog_title = row
        return LoanDetailRow(
            loan=loan,
            patron_display_name=patron_display_name,
            holding_barcode=holding_barcode,
            catalog_title=catalog_title,
        )

    def get_open_loan_by_holding(self, holding_id: UUID) -> LoanModel:
        row = self._session.scalar(
            select(LoanModel).where(
                LoanModel.holding_id == holding_id,
                LoanModel.returned_at.is_(None),
            )
        )
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, "Open loan not found", status_code=404)
        return row

    def _get_rule_set(self, rule_set_id: UUID) -> LoanRuleSetModel:
        row = self._session.get(LoanRuleSetModel, rule_set_id)
        if row is None:
            raise AppError(ErrorCode.NOT_FOUND, "Loan rule set not found", status_code=404)
        return row
