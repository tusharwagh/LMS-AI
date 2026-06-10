"""OpenAPI / Swagger UI configuration — Bearer JWT authorize dialog."""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

BEARER_SCHEME_NAME = "BearerJWT"

BEARER_SCHEME_DESCRIPTION = (
    "JWT access token. Obtain via **POST /api/v1/auth/token** "
    "(form: username + password), then paste the `access_token` value here "
    "(without the `Bearer ` prefix). "
    "After `make seed`: `librarian` / `changeme` or `admin` / `changeme`."
)


def configure_openapi(app: FastAPI) -> None:
    """Register a named HTTP Bearer scheme so Swagger shows a token input."""

    def custom_openapi() -> dict:
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
            "description": BEARER_SCHEME_DESCRIPTION,
        }
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
