"""Staff desk UI smoke tests (Phase 6)."""

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.e2e


def test_staff_ui_index(bare_client: TestClient) -> None:
    resp = bare_client.get("/staff/")
    assert resp.status_code == 200
    assert "Library Staff Desk" in resp.text
    assert "/staff/static/app.js" in resp.text


def test_staff_ui_static_assets(bare_client: TestClient) -> None:
    css = bare_client.get("/staff/static/styles.css")
    assert css.status_code == 200
    assert "var(--primary)" in css.text

    js = bare_client.get("/staff/static/app.js")
    assert js.status_code == 200
    assert "workflows/issue/commit" in js.text
    assert "/api/v1/loan/checkouts" not in js.text
