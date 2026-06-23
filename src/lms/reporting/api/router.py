"""Staff reporting and dashboard API."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from lms.platform.auth.rbac import require_staff
from lms.reporting.api.schemas import (
    CirculationSummaryResponse,
    DailySeriesPoint,
    DashboardResponse,
    ReportGenerateRequest,
    ReportGenerateResponse,
    ReportPresetResponse,
    ReportPresetsResponse,
    ReportSectionResponse,
    TodaySummaryResponse,
)
from lms.reporting.application.dashboard_service import DashboardService
from lms.reporting.application.report_service import ReportService
from lms.reporting.domain.enums import ReportFormat
from lms.shared.auth.deps import DbSession
from lms.shared.http.errors import AppError, ErrorCode

router = APIRouter(prefix="/reporting", dependencies=[require_staff])


def _dashboard_service(session: DbSession) -> DashboardService:
    return DashboardService(session)


def _report_service(session: DbSession) -> ReportService:
    return ReportService(session)


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    service: Annotated[DashboardService, Depends(_dashboard_service)],
    days: Annotated[int, Query(ge=7, le=90)] = 30,
    from_date: Annotated[date | None, Query()] = None,
    to_date: Annotated[date | None, Query()] = None,
) -> DashboardResponse:
    if (from_date is None) != (to_date is None):
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "from_date and to_date must both be provided",
            status_code=422,
        )
    try:
        snapshot = service.snapshot(days=days, from_date=from_date, to_date=to_date)
    except ValueError as exc:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            str(exc),
            status_code=422,
        ) from exc
    return DashboardResponse(
        holdings_by_status=snapshot.holdings_by_status,
        circulation=CirculationSummaryResponse(
            total_active_loans=snapshot.circulation.total_active_loans,
            overdue_loans=snapshot.circulation.overdue_loans,
        ),
        today=TodaySummaryResponse(
            issues_today=snapshot.today.issues_today,
            returns_today=snapshot.today.returns_today,
        ),
        daily_series=[
            DailySeriesPoint(date=row.day, issues=row.issues, returns=row.returns)
            for row in snapshot.daily_series
        ],
        from_date=snapshot.from_date,
        to_date=snapshot.to_date,
    )


@router.post("/reports/generate", response_model=None)
def generate_report(
    body: ReportGenerateRequest,
    service: Annotated[ReportService, Depends(_report_service)],
) -> ReportGenerateResponse | StreamingResponse:
    spec = body.to_spec()
    report = service.generate(spec)

    if spec.format == ReportFormat.CSV:
        csv_text = service.render_csv(report)
        filename = f"report-{spec.from_date.isoformat()}-{spec.to_date.isoformat()}.csv"
        return StreamingResponse(
            iter([csv_text]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return ReportGenerateResponse(
        from_date=report.from_date,
        to_date=report.to_date,
        group_by=report.group_by,
        sections=[
            ReportSectionResponse(
                metric=section.metric,
                group_by=section.group_by,
                rows=list(section.rows),
            )
            for section in report.sections
        ],
    )


@router.get("/reports/presets", response_model=ReportPresetsResponse)
def list_report_presets(
    service: Annotated[ReportService, Depends(_report_service)],
) -> ReportPresetsResponse:
    presets = service.list_presets()
    return ReportPresetsResponse(
        presets=[
            ReportPresetResponse(
                id=preset.id,
                name=preset.name,
                description=preset.description,
                metrics=list(preset.metrics),
                default_days=preset.default_days,
            )
            for preset in presets
        ]
    )
