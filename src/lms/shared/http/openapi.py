"""OpenAPI / Swagger UI configuration — Bearer JWT authorize dialog."""

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

BEARER_SCHEME_NAME = "BearerJWT"

DEFAULT_BEARER_SCHEME_DESCRIPTION = (
    "JWT access token. Obtain via the auth token endpoint, "
    "then paste the `access_token` value here (without the `Bearer ` prefix)."
)


def configure_openapi(
    app: FastAPI,
    *,
    bearer_description: str = DEFAULT_BEARER_SCHEME_DESCRIPTION,
) -> None:
    """Register a named HTTP Bearer scheme so Swagger shows a token input."""

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        components = schema.setdefault("components", {})
        schemes = components.setdefault("securitySchemes", {})
        schemes[BEARER_SCHEME_NAME] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": bearer_description,
        }
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
