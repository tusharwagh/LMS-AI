from enum import StrEnum


class ReportMetric(StrEnum):
    DAILY_ISSUES = "daily_issues"
    DAILY_RETURNS = "daily_returns"
    HOLDINGS_BY_STATUS = "holdings_by_status"
    TOTAL_ACTIVE_LOANS = "total_active_loans"
    OVERDUE_LOANS = "overdue_loans"


class ReportGroupBy(StrEnum):
    DAY = "day"


class ReportFormat(StrEnum):
    JSON = "json"
    CSV = "csv"
