from enum import StrEnum
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from lms.config import get_settings

logger = structlog.get_logger(__name__)


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    DOMAIN_RULE_VIOLATION = "DOMAIN_RULE_VIOLATION"
    RETRIABLE_ERROR = "RETRIABLE_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status_code: int = 400,
        retriable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retriable = retriable
        self.details = details or {}


def error_body(
    code: ErrorCode,
    message: str,
    *,
    retriable: bool = False,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code.value,
        "message": message,
        "retriable": retriable,
        "details": details or {},
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(
                exc.code,
                exc.message,
                retriable=exc.retriable,
                details=exc.details,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        settings = get_settings()
        details: dict[str, Any] = {}
        if settings.app_debug:
            details = {"errors": exc.errors()}
        return JSONResponse(
            status_code=422,
            content=error_body(
                ErrorCode.VALIDATION_ERROR,
                "Invalid input",
                details=details,
            ),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            detail = exc.detail
            return JSONResponse(
                status_code=exc.status_code,
                content=error_body(
                    ErrorCode(detail["code"]),
                    str(detail.get("message", "Request failed")),
                    details=detail.get("details") or {},
                ),
                headers=getattr(exc, "headers", None),
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(ErrorCode.VALIDATION_ERROR, str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", exc_info=exc)
        settings = get_settings()
        message = str(exc) if settings.app_debug else "An unexpected error occurred"
        return JSONResponse(
            status_code=500,
            content=error_body(ErrorCode.RETRIABLE_ERROR, message, retriable=True),
        )
