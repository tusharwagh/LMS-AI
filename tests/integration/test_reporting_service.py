"""Reporting dashboard and report generation — database integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from lms.catalog.domain.enums import HoldingStatus
from lms.catalog.infrastructure.models.models import CatalogModel, HoldingModel
from lms.loan.infrastructure.models.models import LoanModel
from lms.reporting.application.dashboard_service import DashboardService
from lms.reporting.application.report_service import ReportService
from lms.reporting.domain.enums import ReportFormat, ReportGroupBy, ReportMetric
from lms.reporting.domain.report_spec import ReportSpec
from lms.shared.time import library_today

pytestmark = pytest.mark.integration


def test_dashboard_service_returns_counts(db_session: Session) -> None:
    service = DashboardService(db_session)
    snapshot = service.snapshot(days=7)
    assert isinstance(snapshot.holdings_by_status, dict)
    assert snapshot.holdings_by_status[HoldingStatus.AVAILABLE.value] >= 0
    assert snapshot.circulation.total_active_loans >= 0
    assert snapshot.circulation.overdue_loans >= 0
    assert len(snapshot.daily_series) == 7


def test_report_service_generates_sections(db_session: Session) -> None:
    service = ReportService(db_session)
    today = library_today()
    spec = ReportSpec(
        metrics=(
            ReportMetric.DAILY_ISSUES,
            ReportMetric.HOLDINGS_BY_STATUS,
            ReportMetric.OVERDUE_LOANS,
        ),
        from_date=today - timedelta(days=6),
        to_date=today,
        group_by=ReportGroupBy.DAY,
        format=ReportFormat.JSON,
    )
    report = service.generate(spec)
    assert len(report.sections) == 3
    assert report.sections[0].metric == ReportMetric.DAILY_ISSUES
    assert len(report.sections[0].rows) == 7


def test_report_service_csv_render(db_session: Session) -> None:
    service = ReportService(db_session)
    today = library_today()
    spec = ReportSpec(
        metrics=(ReportMetric.DAILY_RETURNS,),
        from_date=today - timedelta(days=2),
        to_date=today,
    )
    report = service.generate(spec)
    csv_text = service.render_csv(report)
    assert "daily_returns" in csv_text
    assert today.isoformat() in csv_text


def test_reporting_dashboard_http(client: TestClient) -> None:
    response = client.get("/api/v1/reporting/dashboard", params={"days": 14})
    assert response.status_code == 200
    body = response.json()
    assert "holdings_by_status" in body
    assert "circulation" in body
    assert "today" in body
    assert len(body["daily_series"]) == 14


def test_reporting_presets_http(client: TestClient) -> None:
    response = client.get("/api/v1/reporting/reports/presets")
    assert response.status_code == 200
    presets = response.json()["presets"]
    assert len(presets) >= 1
    assert "metrics" in presets[0]


def test_reporting_generate_json_http(client: TestClient) -> None:
    today = library_today()
    from_date = today - timedelta(days=3)
    response = client.post(
        "/api/v1/reporting/reports/generate",
        json={
            "metrics": ["daily_issues", "holdings_by_status"],
            "from_date": from_date.isoformat(),
            "to_date": today.isoformat(),
            "format": "json",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["from_date"] == from_date.isoformat()
    assert len(body["sections"]) == 2


def test_reporting_generate_csv_http(client: TestClient) -> None:
    today = library_today()
    response = client.post(
        "/api/v1/reporting/reports/generate",
        json={
            "metrics": ["daily_issues"],
            "from_date": (today - timedelta(days=2)).isoformat(),
            "to_date": today.isoformat(),
            "format": "csv",
        },
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    assert "daily_issues" in response.text


def test_reporting_counts_isolated_loan(db_session: Session) -> None:
    """Insert a loan checked out today and verify issue count includes it."""
    catalog_id = db_session.scalar(select(CatalogModel.id).limit(1))
    if catalog_id is None:
        pytest.skip("No catalog rows in test database")

    holding = HoldingModel(
        catalog_id=catalog_id,
        barcode=f"BC-RPT-{datetime.now(UTC).timestamp():.0f}",
        accession_number=f"ACC-RPT-{datetime.now(UTC).timestamp():.0f}",
        holding_status=HoldingStatus.AVAILABLE,
        circulating=True,
    )
    db_session.add(holding)
    db_session.flush()

    from lms.reference.infrastructure.models.models import PatronModel

    patron = db_session.scalar(select(PatronModel).limit(1))
    if patron is None:
        pytest.skip("No patron rows in test database")

    now = datetime.now(UTC)
    loan = LoanModel(
        patron_id=patron.id,
        holding_id=holding.id,
        checkout_at=now,
        due_date=(now + timedelta(days=14)).date(),
        returned_at=None,
    )
    db_session.add(loan)
    db_session.flush()

    service = DashboardService(db_session)
    today = library_today()
    issues = service._queries.count_issues_on(today)  # noqa: SLF001
    assert issues >= 1
