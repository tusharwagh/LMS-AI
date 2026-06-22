"""Customizable report generation."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from lms.platform.time import library_today
from lms.reporting.domain.enums import ReportGroupBy, ReportMetric
from lms.reporting.domain.report_spec import ReportSpec
from lms.reporting.infrastructure.queries import ReportingQueries


@dataclass(frozen=True, slots=True)
class ReportPreset:
    id: str
    name: str
    description: str
    metrics: tuple[ReportMetric, ...]
    default_days: int


@dataclass(frozen=True, slots=True)
class ReportSection:
    metric: ReportMetric
    group_by: ReportGroupBy | None
    rows: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class GeneratedReport:
    from_date: date
    to_date: date
    group_by: ReportGroupBy
    sections: tuple[ReportSection, ...]


BUILTIN_PRESETS: tuple[ReportPreset, ...] = (
    ReportPreset(
        id="daily_circulation",
        name="Daily circulation",
        description="Issues and returns per day for the selected period.",
        metrics=(ReportMetric.DAILY_ISSUES, ReportMetric.DAILY_RETURNS),
        default_days=30,
    ),
    ReportPreset(
        id="holdings_snapshot",
        name="Holdings by status",
        description="Current count of holdings grouped by status.",
        metrics=(ReportMetric.HOLDINGS_BY_STATUS,),
        default_days=1,
    ),
    ReportPreset(
        id="loan_health",
        name="Loan health",
        description="Active and overdue loan counts as of today.",
        metrics=(ReportMetric.TOTAL_ACTIVE_LOANS, ReportMetric.OVERDUE_LOANS),
        default_days=1,
    ),
    ReportPreset(
        id="full_dashboard",
        name="Full dashboard export",
        description="All dashboard metrics for a date range.",
        metrics=(
            ReportMetric.DAILY_ISSUES,
            ReportMetric.DAILY_RETURNS,
            ReportMetric.HOLDINGS_BY_STATUS,
            ReportMetric.TOTAL_ACTIVE_LOANS,
            ReportMetric.OVERDUE_LOANS,
        ),
        default_days=30,
    ),
)


class ReportService:
    def __init__(self, session: Session) -> None:
        self._queries = ReportingQueries(session)

    def list_presets(self) -> tuple[ReportPreset, ...]:
        return BUILTIN_PRESETS

    def generate(self, spec: ReportSpec) -> GeneratedReport:
        sections: list[ReportSection] = []
        for metric in spec.metrics:
            sections.append(self._section_for_metric(metric, spec))
        return GeneratedReport(
            from_date=spec.from_date,
            to_date=spec.to_date,
            group_by=spec.group_by,
            sections=tuple(sections),
        )

    def render_csv(self, report: GeneratedReport) -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["from_date", report.from_date.isoformat()])
        writer.writerow(["to_date", report.to_date.isoformat()])
        writer.writerow(["group_by", report.group_by.value])
        writer.writerow([])

        for section in report.sections:
            writer.writerow(["metric", section.metric.value])
            if not section.rows:
                writer.writerow(["(no data)"])
                writer.writerow([])
                continue
            headers = list(section.rows[0].keys())
            writer.writerow(headers)
            for row in section.rows:
                writer.writerow([row.get(h, "") for h in headers])
            writer.writerow([])

        return buffer.getvalue()

    def _section_for_metric(self, metric: ReportMetric, spec: ReportSpec) -> ReportSection:
        if metric == ReportMetric.DAILY_ISSUES:
            daily = self._queries.daily_circulation(spec.from_date, spec.to_date)
            rows = tuple({"date": row.day.isoformat(), "issues": row.issues} for row in daily)
            return ReportSection(metric=metric, group_by=spec.group_by, rows=rows)

        if metric == ReportMetric.DAILY_RETURNS:
            daily = self._queries.daily_circulation(spec.from_date, spec.to_date)
            rows = tuple({"date": row.day.isoformat(), "returns": row.returns} for row in daily)
            return ReportSection(metric=metric, group_by=spec.group_by, rows=rows)

        if metric == ReportMetric.HOLDINGS_BY_STATUS:
            counts = self._queries.count_holdings_by_status()
            rows = tuple(
                {"status": status, "count": count}
                for status, count in sorted(counts.items())
            )
            return ReportSection(metric=metric, group_by=None, rows=rows)

        if metric == ReportMetric.TOTAL_ACTIVE_LOANS:
            count = self._queries.count_active_loans()
            return ReportSection(
                metric=metric,
                group_by=None,
                rows=({"as_of": library_today().isoformat(), "total_active_loans": count},),
            )

        if metric == ReportMetric.OVERDUE_LOANS:
            today = library_today()
            count = self._queries.count_overdue_loans(as_of=today)
            return ReportSection(
                metric=metric,
                group_by=None,
                rows=({"as_of": today.isoformat(), "overdue_loans": count},),
            )

        raise ValueError(f"Unsupported metric: {metric}")
