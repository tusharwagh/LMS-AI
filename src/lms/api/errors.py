from enum import StrEnum

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    DOMAIN_RULE_VIOLATION = "DOMAIN_RULE_VIOLATION"
    RETRIABLE_ERROR = "RETRIABLE_ERROR"


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status_code: int = 400,
        retriable: bool = False,
        details: dict | None = None,
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
    details: dict | None = None,
) -> dict:
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
