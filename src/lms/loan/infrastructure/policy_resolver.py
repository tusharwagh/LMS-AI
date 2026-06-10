"""Resolves PatronType -> LoanRuleSet and due date (ADR-005)."""

from datetime import timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from lms.loan.domain.ports import ResolvedPolicy
from lms.shared.time import library_today


class PolicyResolver:
    def __init__(self, session: Session) -> None:
        self._session = session

    def resolve(self, patron_type_id: UUID) -> ResolvedPolicy:
        row = self._session.execute(
            text(
                """
                SELECT lrs.id, lrs.max_active_loans, lrs.loan_period_days
                FROM patron_types pt
                JOIN loan_rule_sets lrs ON lrs.id = pt.loan_rule_set_id
                WHERE pt.id = :patron_type_id
                """
            ),
            {"patron_type_id": patron_type_id},
        ).one_or_none()
        if row is None:
            raise ValueError(f"No loan rule set mapped for patron type {patron_type_id}")
        due_date = library_today() + timedelta(days=row.loan_period_days)
        return ResolvedPolicy(
            loan_rule_set_id=row.id,
            max_active_loans=row.max_active_loans,
            loan_period_days=row.loan_period_days,
            due_date=due_date,
        )
