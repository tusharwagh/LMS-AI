"""Security response headers and request rate limiting."""

from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lms.config import get_settings
from lms.shared.http.errors import ErrorCode, error_body


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    path_prefix: str
    max_requests: int
    window_seconds: int


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


def _security_header_values(*, hsts_enabled: bool) -> dict[str, str]:
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        ),
    }
    if hsts_enabled:
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return headers


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response: Response = await call_next(request)
        settings = get_settings()
        for name, value in _security_header_values(
            hsts_enabled=settings.security_hsts_enabled
        ).items():
            if name not in response.headers:
                response.headers[name] = value
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window rate limiter keyed by client IP and path prefix."""

    _EXEMPT_PREFIXES = ("/health", "/docs", "/openapi.json", "/redoc")

    def __init__(self, app) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _rules(self) -> list[RateLimitRule]:
        settings = get_settings()
        return [
            RateLimitRule(
                "/api/v1/auth/",
                settings.auth_rate_limit_max,
                settings.auth_rate_limit_window_seconds,
            ),
            RateLimitRule(
                "/api/",
                settings.api_rate_limit_max,
                settings.api_rate_limit_window_seconds,
            ),
        ]

    def _match_rule(self, path: str) -> RateLimitRule | None:
        matched: RateLimitRule | None = None
        for rule in self._rules():
            if path.startswith(rule.path_prefix):
                if matched is None or len(rule.path_prefix) > len(matched.path_prefix):
                    matched = rule
        return matched

    def _allow(self, key: str, rule: RateLimitRule) -> bool:
        now = time.monotonic()
        window_start = now - rule.window_seconds
        recent = [ts for ts in self._hits[key] if ts > window_start]
        if len(recent) >= rule.max_requests:
            self._hits[key] = recent
            return False
        recent.append(now)
        self._hits[key] = recent
        return True

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        settings = get_settings()
        path = request.url.path
        if not settings.rate_limit_enabled or any(
            path.startswith(prefix) for prefix in self._EXEMPT_PREFIXES
        ):
            response: Response = await call_next(request)
            return response

        rule = self._match_rule(path)
        if rule is None:
            return await call_next(request)

        key = f"{_client_ip(request)}:{rule.path_prefix}"
        if not self._allow(key, rule):
            return JSONResponse(
                status_code=429,
                content=error_body(
                    ErrorCode.RATE_LIMIT_EXCEEDED,
                    "Too many requests. Try again later.",
                    retriable=True,
                ),
                headers={"Retry-After": str(rule.window_seconds)},
            )
        return await call_next(request)
