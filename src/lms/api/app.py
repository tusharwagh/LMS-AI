from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from lms.api.agent.router import router as agent_router
from lms.api.auth_router import router as auth_router
from lms.api.domain_api import domain_api_router
from lms.api.errors import register_exception_handlers
from lms.api.health import router as health_router
from lms.api.middleware import CorrelationIdMiddleware
from lms.api.openapi import configure_openapi
from lms.api.security_middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from lms.config import get_settings
from lms.shared.logging import configure_logging
from lms.staff.router import router as staff_router
from lms.staff.router import staff_static_directory


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.app_debug)

    app = FastAPI(
        title="LMS-AI API",
        version="0.1.0",
        description=(
            "LMS-AI — K-12 Library Management (MVP). "
            "Click **Authorize**, paste a JWT from `POST /api/v1/auth/token`, "
            "then try domain endpoints."
        ),
        swagger_ui_parameters={"persistAuthorization": True},
    )

    configure_openapi(app)

    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Correlation-Id",
        ],
    )

    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(domain_api_router)
    app.include_router(agent_router, prefix="/api/v1", tags=["agent"])
    app.mount(
        "/staff/static",
        StaticFiles(directory=staff_static_directory()),
        name="staff-static",
    )
    app.include_router(staff_router, prefix="/staff")

    return app
