"""LLM spend reporting API — RBAC (no database)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from lms.api.app import create_app
from lms.shared.auth.jwt import create_access_token
from lms.shared.auth.roles import Role

pytestmark = pytest.mark.unit


def test_llm_spend_logs_require_auth() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/llm-spend/logs")
    assert response.status_code == 401


def test_llm_spend_patron_role_forbidden() -> None:
    client = TestClient(create_app())
    patron_token = create_access_token(str(uuid.uuid4()), Role.PATRON)
    response = client.get(
        "/api/v1/llm-spend/logs",
        headers={"Authorization": f"Bearer {patron_token}"},
    )
    assert response.status_code == 403


def test_llm_spend_summary_patron_role_forbidden() -> None:
    client = TestClient(create_app())
    patron_token = create_access_token(str(uuid.uuid4()), Role.PATRON)
    response = client.get(
        "/api/v1/llm-spend/summary",
        headers={"Authorization": f"Bearer {patron_token}"},
    )
    assert response.status_code == 403
