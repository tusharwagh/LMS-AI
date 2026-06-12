"""Security hardening regression tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from lms.api.app import create_app
from lms.config import Settings, get_settings

pytestmark = pytest.mark.hardening


def test_security_headers_on_health(bare_client: TestClient) -> None:
    response = bare_client.get("/health")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in response.headers
    assert "Strict-Transport-Security" not in response.headers


def test_hsts_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SECURITY_HSTS_ENABLED", "true")
    get_settings.cache_clear()
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.headers.get("Strict-Transport-Security", "").startswith("max-age=")


def test_unhandled_error_hides_internals(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DEBUG", "false")
    get_settings.cache_clear()
    app = create_app()

    @app.get("/probe-unhandled-error")
    def _probe() -> None:
        raise RuntimeError("db password leaked")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/probe-unhandled-error")
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "RETRIABLE_ERROR"
    assert body["message"] == "An unexpected error occurred"
    assert "db password" not in response.text


def test_validation_error_shape(bare_client: TestClient) -> None:
    response = bare_client.post("/api/v1/auth/token", data={"username": "only-user"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Invalid input"
    assert body["details"] == {}


def test_production_rejects_default_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "https://library.example.com")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="APP_SECRET_KEY"):
        Settings()


def test_production_rejects_wildcard_cors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_SECRET_KEY", "production-secret-key")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        Settings()


def test_production_rejects_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("APP_SECRET_KEY", "production-secret-key")
    monkeypatch.setenv("CORS_ORIGINS", "https://library.example.com")
    monkeypatch.setenv("APP_DEBUG", "true")
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="APP_DEBUG"):
        Settings()


def test_auth_rate_limit(monkeypatch: pytest.MonkeyPatch, dev_password: str) -> None:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("AUTH_RATE_LIMIT_MAX", "3")
    monkeypatch.setenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    client = TestClient(create_app())
    payload = {"username": "librarian", "password": dev_password}
    for _ in range(3):
        response = client.post("/api/v1/auth/token", data=payload)
        assert response.status_code == 200, response.text
    blocked = client.post("/api/v1/auth/token", data=payload)
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RATE_LIMIT_EXCEEDED"
