"""Reporting API schemas."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, model_validator

from lms.reporting.domain.enums import ReportFormat, ReportGroupBy, ReportMetric
from lms.reporting.domain.report_spec import ReportSpec


class DailySeriesPoint(BaseModel):
    date: date
    issues: int
    returns: int


class CirculationSummaryResponse(BaseModel):
    total_active_loans: int
    overdue_loans: int


class TodaySummaryResponse(BaseModel):
    issues_today: int
    returns_today: int


class DashboardResponse(BaseModel):
    holdings_by_status: dict[str, int]
    circulation: CirculationSummaryResponse
    today: TodaySummaryResponse
    daily_series: list[DailySeriesPoint]
    from_date: date
    to_date: date


class ReportGenerateRequest(BaseModel):
    metrics: list[ReportMetric] = Field(min_length=1)
    from_date: date
    to_date: date
    group_by: ReportGroupBy = ReportGroupBy.DAY
    format: ReportFormat = ReportFormat.JSON

    @model_validator(mode="after")
    def validate_dates(self) -> ReportGenerateRequest:
        if self.from_date > self.to_date:
            raise ValueError("from_date must be on or before to_date")
        span = (self.to_date - self.from_date).days
        if span > 366:
            raise ValueError("Date range must not exceed 366 days")
        return self

    def to_spec(self) -> ReportSpec:
        return ReportSpec(
            metrics=tuple(self.metrics),
            from_date=self.from_date,
            to_date=self.to_date,
            group_by=self.group_by,
            format=self.format,
        )


class ReportSectionResponse(BaseModel):
    metric: ReportMetric
    group_by: ReportGroupBy | None
    rows: list[dict[str, Any]]


class ReportGenerateResponse(BaseModel):
    from_date: date
    to_date: date
    group_by: ReportGroupBy
    sections: list[ReportSectionResponse]


class ReportPresetResponse(BaseModel):
    id: str
    name: str
    description: str
    metrics: list[ReportMetric]
    default_days: int


class ReportPresetsResponse(BaseModel):
    presets: list[ReportPresetResponse]
