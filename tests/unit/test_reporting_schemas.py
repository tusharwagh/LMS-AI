"""Report spec and API schema validation."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from lms.reporting.api.schemas import ReportGenerateRequest
from lms.reporting.domain.enums import ReportFormat, ReportGroupBy, ReportMetric
from lms.reporting.domain.report_spec import ReportSpec

pytestmark = pytest.mark.unit


def test_report_spec_requires_metrics() -> None:
    with pytest.raises(ValueError, match="At least one metric"):
        ReportSpec(
            metrics=(),
            from_date=date(2026, 6, 1),
            to_date=date(2026, 6, 19),
        )


def test_report_spec_rejects_inverted_dates() -> None:
    with pytest.raises(ValueError, match="from_date must be on or before"):
        ReportSpec(
            metrics=(ReportMetric.DAILY_ISSUES,),
            from_date=date(2026, 6, 20),
            to_date=date(2026, 6, 1),
        )


def test_report_spec_rejects_long_range() -> None:
    with pytest.raises(ValueError, match="366 days"):
        ReportSpec(
            metrics=(ReportMetric.DAILY_ISSUES,),
            from_date=date(2025, 1, 1),
            to_date=date(2026, 6, 1),
        )


def test_report_generate_request_to_spec() -> None:
    body = ReportGenerateRequest(
        metrics=[ReportMetric.DAILY_ISSUES, ReportMetric.HOLDINGS_BY_STATUS],
        from_date=date(2026, 6, 1),
        to_date=date(2026, 6, 19),
        group_by=ReportGroupBy.DAY,
        format=ReportFormat.JSON,
    )
    spec = body.to_spec()
    assert spec.metrics == (ReportMetric.DAILY_ISSUES, ReportMetric.HOLDINGS_BY_STATUS)
    assert spec.format == ReportFormat.JSON


def test_report_generate_request_validation_error() -> None:
    with pytest.raises(ValidationError):
        ReportGenerateRequest(
            metrics=[],
            from_date=date(2026, 6, 1),
            to_date=date(2026, 6, 19),
        )
