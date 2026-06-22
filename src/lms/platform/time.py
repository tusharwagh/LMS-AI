from datetime import date
from zoneinfo import ZoneInfo

from lms.config import get_settings
from lms.shared.time import utc_now


def library_timezone() -> ZoneInfo:
    return ZoneInfo(get_settings().library_timezone)


def library_today() -> date:
    return utc_now().astimezone(library_timezone()).date()
