from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lms.api.errors import register_exception_handlers
from lms.api.health import router as health_router
from lms.api.middleware import CorrelationIdMiddleware
from lms.shared.logging import configure_logging
from lms.catalog.api.router import router as catalog_router
from lms.config import get_settings
from lms.loan.api.router import router as loan_router
from lms.reference.api.router import router as reference_router


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.app_debug)

    app = FastAPI(
        title="LMS API",
        version="0.1.0",
        description="K-12 Library Management — MVP",
    )

    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(reference_router, prefix="/api/v1/reference", tags=["reference"])
    app.include_router(catalog_router, prefix="/api/v1/catalog", tags=["catalog"])
    app.include_router(loan_router, prefix="/api/v1/loan", tags=["loan"])

    return app
