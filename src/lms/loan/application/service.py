from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import bindparam, select, text
from sqlalchemy.orm import Session
from sqlalchemy.sql import Executable
from sqlalchemy.sql.elements import BindParameter

from lms.api.errors import AppError, ErrorCode
from lms.loan.api.schemas import LoanRuleSetCreate, LoanRuleSetUpdate
from lms.loan.domain.enums import CalendarPolicy
from lms.loan.infrastructure.models.models import LoanModel, LoanRuleSetModel
from lms.shared.time import library_today

_LOAN_DETAIL_SELECT = """
    SELECT
        l.id AS loan_id,
        p.display_name AS patron_display_name,
        h.barcode AS holding_barcode,
        c.title AS catalog_title
    FROM loans l
    JOIN patrons p ON l.patron_id = p.id
    JOIN holdings h ON l.holding_id = h.id
    JOIN catalogs c ON h.catalog_id = c.id
"""


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
        stmt = text(
            _LOAN_DETAIL_SELECT
            + """
            WHERE l.patron_id = :patron_id
              AND l.returned_at IS NULL
            ORDER BY l.checkout_at DESC
            """
        )
        return self._load_loan_details(stmt, {"patron_id": patron_id})

    def search_open_loan_details(
        self,
        *,
        patron_ids: list[UUID] | None = None,
        title_query: str | None = None,
        limit: int = 10,
    ) -> list[LoanDetailRow]:
        clauses = ["l.returned_at IS NULL"]
        params: dict[str, Any] = {"limit": min(limit, 20)}
        bind_params: list[BindParameter[Any]] = [bindparam("limit")]
        if patron_ids:
            clauses.append("l.patron_id IN :patron_ids")
            params["patron_ids"] = patron_ids
            bind_params.append(bindparam("patron_ids", expanding=True))
        title = (title_query or "").strip()
        if title:
            clauses.append("c.title ILIKE :title_pattern")
            params["title_pattern"] = f"%{title}%"
            bind_params.append(bindparam("title_pattern"))
        where_sql = " AND ".join(clauses)
        stmt = text(
            _LOAN_DETAIL_SELECT
            + f"""
            WHERE {where_sql}
            ORDER BY l.checkout_at DESC
            LIMIT :limit
            """
        ).bindparams(*bind_params)
        return self._load_loan_details(stmt, params)

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
        stmt = text(
            _LOAN_DETAIL_SELECT
            + """
            WHERE l.returned_at IS NULL
              AND l.due_date < :as_of
            ORDER BY l.due_date, l.checkout_at
            """
        )
        return self._load_loan_details(stmt, {"as_of": as_of})

    def _load_loan_details(
        self, stmt: Executable, params: dict[str, Any]
    ) -> list[LoanDetailRow]:
        rows = self._session.execute(stmt, params).all()
        if not rows:
            return []
        loan_ids = [row.loan_id for row in rows]
        loans = {
            loan.id: loan
            for loan in self._session.scalars(select(LoanModel).where(LoanModel.id.in_(loan_ids)))
        }
        return [
            LoanDetailRow(
                loan=loans[row.loan_id],
                patron_display_name=row.patron_display_name,
                holding_barcode=row.holding_barcode,
                catalog_title=row.catalog_title,
            )
            for row in rows
            if row.loan_id in loans
        ]

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
