from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from lms.config import get_settings


def library_timezone() -> ZoneInfo:
    return ZoneInfo(get_settings().library_timezone)


def utc_now() -> datetime:
    return datetime.now(UTC)


def library_today() -> date:
    return utc_now().astimezone(library_timezone()).date()
