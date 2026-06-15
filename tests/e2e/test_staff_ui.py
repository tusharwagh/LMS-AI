"""Staff desk UI smoke tests (Phase 6)."""

import re

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.e2e


def test_staff_ui_index(bare_client: TestClient) -> None:
    resp = bare_client.get("/staff/")
    assert resp.status_code == 200
    assert "LMS-AI Staff Desk" in resp.text
    assert 'id="root"' in resp.text
    assert 'type="module"' in resp.text
    assert "/staff/static/assets/" in resp.text


def test_staff_ui_static_assets(bare_client: TestClient) -> None:
    index = bare_client.get("/staff/")
    assert index.status_code == 200

    css_href = _extract_asset_href(index.text, ".css")
    css = bare_client.get(css_href)
    assert css.status_code == 200
    assert "--color-primary" in css.text

    js_href = _extract_asset_href(index.text, ".js")
    js = bare_client.get(js_href)
    assert js.status_code == 200
    assert "workflows/issue/commit" in js.text
    assert "/api/v1/loan/checkouts" not in js.text


def _extract_asset_href(html: str, suffix: str) -> str:
    pattern = rf'(/staff/static/assets/[^"\']+{re.escape(suffix)})'
    match = re.search(pattern, html)
    if not match:
        raise AssertionError(f"Could not find built {suffix} asset in staff index.html")
    return match.group(1)
