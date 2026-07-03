"""FastAPI error envelope (org-python-platform)."""

from fastapi import FastAPI
from fastapi_platform.errors import (
    AppError,
    ErrorCode,
    error_body,
)
from fastapi_platform.errors import (
    register_exception_handlers as _register_exception_handlers,
)

from lms.config import get_settings

__all__ = [
    "AppError",
    "ErrorCode",
    "error_body",
    "register_exception_handlers",
]


def register_exception_handlers(app: FastAPI) -> None:
    _register_exception_handlers(app, debug=get_settings().app_debug)
