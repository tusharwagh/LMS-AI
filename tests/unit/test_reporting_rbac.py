"""Reporting API — RBAC (no database)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from lms.api.app import create_app
from lms.platform.auth.roles import Role
from lms.shared.auth.jwt import create_access_token

pytestmark = pytest.mark.unit


def test_reporting_dashboard_requires_auth() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/reporting/dashboard")
    assert response.status_code == 401


def test_reporting_dashboard_patron_forbidden() -> None:
    client = TestClient(create_app())
    patron_token = create_access_token(str(uuid.uuid4()), Role.PATRON)
    response = client.get(
        "/api/v1/reporting/dashboard",
        headers={"Authorization": f"Bearer {patron_token}"},
    )
    assert response.status_code == 403


def test_reporting_generate_patron_forbidden() -> None:
    client = TestClient(create_app())
    patron_token = create_access_token(str(uuid.uuid4()), Role.PATRON)
    response = client.post(
        "/api/v1/reporting/reports/generate",
        headers={"Authorization": f"Bearer {patron_token}"},
        json={
            "metrics": ["daily_issues"],
            "from_date": "2026-06-01",
            "to_date": "2026-06-19",
        },
    )
    assert response.status_code == 403


def test_reporting_presets_patron_forbidden() -> None:
    client = TestClient(create_app())
    patron_token = create_access_token(str(uuid.uuid4()), Role.PATRON)
    response = client.get(
        "/api/v1/reporting/reports/presets",
        headers={"Authorization": f"Bearer {patron_token}"},
    )
    assert response.status_code == 403
