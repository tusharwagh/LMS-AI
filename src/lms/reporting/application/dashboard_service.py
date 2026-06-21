"""Dashboard snapshot aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from lms.reporting.infrastructure.queries import DailyCirculationRow, ReportingQueries
from lms.shared.time import library_today


@dataclass(frozen=True, slots=True)
class CirculationSummary:
    total_active_loans: int
    overdue_loans: int


@dataclass(frozen=True, slots=True)
class TodaySummary:
    issues_today: int
    returns_today: int


@dataclass(frozen=True, slots=True)
class DashboardSnapshot:
    holdings_by_status: dict[str, int]
    circulation: CirculationSummary
    today: TodaySummary
    daily_series: tuple[DailyCirculationRow, ...]
    from_date: date
    to_date: date


class DashboardService:
    def __init__(self, session: Session) -> None:
        self._queries = ReportingQueries(session)

    def snapshot(
        self,
        *,
        days: int = 30,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> DashboardSnapshot:
        today = library_today()
        if from_date is not None and to_date is not None:
            series_from = from_date
            series_to = to_date
        elif from_date is not None or to_date is not None:
            raise ValueError("from_date and to_date must both be provided")
        else:
            series_to = today
            series_from = today - timedelta(days=days - 1)

        if series_from > series_to:
            raise ValueError("from_date must be on or before to_date")

        holdings = self._queries.count_holdings_by_status()
        circulation = CirculationSummary(
            total_active_loans=self._queries.count_active_loans(),
            overdue_loans=self._queries.count_overdue_loans(as_of=today),
        )
        today_summary = TodaySummary(
            issues_today=self._queries.count_issues_on(today),
            returns_today=self._queries.count_returns_on(today),
        )
        daily_series = tuple(self._queries.daily_circulation(series_from, series_to))

        return DashboardSnapshot(
            holdings_by_status=holdings,
            circulation=circulation,
            today=today_summary,
            daily_series=daily_series,
            from_date=series_from,
            to_date=series_to,
        )
