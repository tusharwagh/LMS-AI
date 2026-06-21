"""Read-only circulation and holdings queries for reporting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from lms.catalog.domain.enums import HoldingStatus
from lms.config import get_settings
from lms.shared.time import library_today


@dataclass(frozen=True, slots=True)
class DailyCirculationRow:
    day: date
    issues: int
    returns: int


class ReportingQueries:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._tz = get_settings().library_timezone

    def count_holdings_by_status(self) -> dict[str, int]:
        stmt = text(
            """
            SELECT holding_status, COUNT(*) AS cnt
            FROM holdings
            GROUP BY holding_status
            """
        )
        rows = self._session.execute(stmt).all()
        counts = {status.value: 0 for status in HoldingStatus}
        for row in rows:
            counts[str(row.holding_status)] = int(row.cnt)
        return counts

    def count_active_loans(self) -> int:
        stmt = text("SELECT COUNT(*) AS cnt FROM loans WHERE returned_at IS NULL")
        return int(self._session.execute(stmt).scalar_one())

    def count_overdue_loans(self, *, as_of: date | None = None) -> int:
        as_of = as_of or library_today()
        stmt = text(
            """
            SELECT COUNT(*) AS cnt
            FROM loans
            WHERE returned_at IS NULL
              AND due_date < :as_of
            """
        )
        return int(self._session.execute(stmt, {"as_of": as_of}).scalar_one())

    def count_issues_on(self, day: date) -> int:
        stmt = text(
            """
            SELECT COUNT(*) AS cnt
            FROM loans
            WHERE (checkout_at AT TIME ZONE :tz)::date = :day
            """
        )
        return int(self._session.execute(stmt, {"tz": self._tz, "day": day}).scalar_one())

    def count_returns_on(self, day: date) -> int:
        stmt = text(
            """
            SELECT COUNT(*) AS cnt
            FROM loans
            WHERE returned_at IS NOT NULL
              AND (returned_at AT TIME ZONE :tz)::date = :day
            """
        )
        return int(self._session.execute(stmt, {"tz": self._tz, "day": day}).scalar_one())

    def daily_circulation(self, from_date: date, to_date: date) -> list[DailyCirculationRow]:
        stmt = text(
            """
            WITH days AS (
                SELECT generate_series(:from_date, :to_date, INTERVAL '1 day')::date AS day
            ),
            issues AS (
                SELECT (checkout_at AT TIME ZONE :tz)::date AS day, COUNT(*) AS cnt
                FROM loans
                WHERE (checkout_at AT TIME ZONE :tz)::date BETWEEN :from_date AND :to_date
                GROUP BY 1
            ),
            returns AS (
                SELECT (returned_at AT TIME ZONE :tz)::date AS day, COUNT(*) AS cnt
                FROM loans
                WHERE returned_at IS NOT NULL
                  AND (returned_at AT TIME ZONE :tz)::date BETWEEN :from_date AND :to_date
                GROUP BY 1
            )
            SELECT
                d.day,
                COALESCE(i.cnt, 0) AS issues,
                COALESCE(r.cnt, 0) AS returns
            FROM days d
            LEFT JOIN issues i ON d.day = i.day
            LEFT JOIN returns r ON d.day = r.day
            ORDER BY d.day
            """
        )
        rows = self._session.execute(
            stmt,
            {"from_date": from_date, "to_date": to_date, "tz": self._tz},
        ).all()
        return [
            DailyCirculationRow(day=row.day, issues=int(row.issues), returns=int(row.returns))
            for row in rows
        ]
