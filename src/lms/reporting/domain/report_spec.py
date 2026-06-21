from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from lms.reporting.domain.enums import ReportFormat, ReportGroupBy, ReportMetric
from lms.shared.time import library_today


@dataclass(frozen=True, slots=True)
class ReportSpec:
    metrics: tuple[ReportMetric, ...]
    from_date: date
    to_date: date
    group_by: ReportGroupBy = ReportGroupBy.DAY
    format: ReportFormat = ReportFormat.JSON

    def __post_init__(self) -> None:
        if not self.metrics:
            raise ValueError("At least one metric is required")
        if self.from_date > self.to_date:
            raise ValueError("from_date must be on or before to_date")
        span = (self.to_date - self.from_date).days
        if span > 366:
            raise ValueError("Date range must not exceed 366 days")

    @classmethod
    def for_last_days(
        cls,
        metrics: tuple[ReportMetric, ...],
        days: int,
        *,
        group_by: ReportGroupBy = ReportGroupBy.DAY,
        format: ReportFormat = ReportFormat.JSON,
    ) -> ReportSpec:
        if days < 1 or days > 366:
            raise ValueError("days must be between 1 and 366")
        to_date = library_today()
        from_date = to_date - timedelta(days=days - 1)
        return cls(
            metrics=metrics,
            from_date=from_date,
            to_date=to_date,
            group_by=group_by,
            format=format,
        )
