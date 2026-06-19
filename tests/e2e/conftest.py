"""Playwright E2E fixtures for staff desk browser tests."""

from __future__ import annotations

import socket
import threading
import time
import uuid
from collections.abc import Generator

import pytest
import uvicorn
from fastapi.testclient import TestClient
from playwright.sync_api import Page
from tests.conftest import AuthenticatedTestClient

from lms.api.app import create_app
from lms.config import get_settings

pytestmark = pytest.mark.e2e


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_server(base_url: str, timeout_s: float = 10.0) -> None:
    import httpx

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            resp = httpx.get(f"{base_url}/health", timeout=1.0)
            if resp.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.05)
    raise RuntimeError(f"Staff server did not become ready at {base_url}")


def _run_staff_server() -> Generator[str, None, None]:
    port = _free_port()
    config = uvicorn.Config(
        create_app(),
        host="127.0.0.1",
        port=port,
        log_level="error",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{port}"
    _wait_for_server(base_url)
    try:
        yield base_url
    finally:
        server.should_exit = True
        thread.join(timeout=5)


@pytest.fixture
def staff_server() -> Generator[str, None, None]:
    """Live uvicorn server for browser E2E (serves built staff UI from static/)."""
    yield from _run_staff_server()


@pytest.fixture
def agent_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_ISSUE_ENABLED", "true")
    monkeypatch.setenv("AGENT_MOCK_LLM", "true")
    get_settings.cache_clear()


@pytest.fixture
def agent_staff_server(agent_env: None) -> Generator[str, None, None]:
    """Staff server with agent desk enabled (mock LLM)."""
    yield from _run_staff_server()


@pytest.fixture
def api_client(admin_headers: dict[str, str]) -> AuthenticatedTestClient:
    return AuthenticatedTestClient(create_app(), default_headers=admin_headers)


def seed_issue_fixture(
    client: TestClient,
    admin_headers: dict[str, str],
    tag: str,
) -> dict[str, str]:
    """Seed patron + lendable copy for desk issue wizard flows."""
    rule_id = client.post(
        "/api/v1/loan/loan-rule-sets",
        json={"name": f"Rule {tag}", "max_active_loans": 2, "loan_period_days": 14},
        headers=admin_headers,
    ).json()["id"]
    patron_type_id = client.post(
        "/api/v1/reference/patron-types",
        json={"code": f"PW_{tag}", "name": "Student", "loan_rule_set_id": rule_id},
        headers=admin_headers,
    ).json()["id"]
    patron_id = client.post(
        "/api/v1/reference/patrons",
        json={
            "display_name": f"Playwright Patron {tag}",
            "patron_type_id": patron_type_id,
            "card_barcode": f"PW-CARD-{tag}",
            "external_ref": f"PW-ADM-{tag}",
        },
    ).json()["id"]
    catalog_id = client.post(
        "/api/v1/catalog/catalogs",
        json={"title": f"Playwright Book {tag}", "language": "en"},
    ).json()["id"]
    client.post(f"/api/v1/catalog/catalogs/{catalog_id}/publish")
    holding_id = client.post(
        f"/api/v1/catalog/catalogs/{catalog_id}/holdings",
        json={"barcode": f"PW-BC-{tag}", "accession_number": f"PW-ACC-{tag}"},
    ).json()["id"]
    return {
        "tag": tag,
        "patron_id": patron_id,
        "holding_id": holding_id,
        "patron_name": f"Playwright Patron {tag}",
        "title": f"Playwright Book {tag}",
        "card": f"PW-CARD-{tag}",
        "barcode": f"PW-BC-{tag}",
    }


@pytest.fixture
def issue_fixture(
    api_client: AuthenticatedTestClient,
    admin_headers: dict[str, str],
) -> dict[str, str]:
    tag = uuid.uuid4().hex[:8]
    return seed_issue_fixture(api_client, admin_headers, tag)


@pytest.fixture
def issued_loan_fixture(
    api_client: AuthenticatedTestClient,
    admin_headers: dict[str, str],
    issue_fixture: dict[str, str],
) -> dict[str, str]:
    """Patron + lendable copy with an active desk loan (for return wizard E2E)."""
    commit = api_client.post(
        "/api/v1/workflows/issue/commit",
        json={
            "patron_id": issue_fixture["patron_id"],
            "holding_id": issue_fixture["holding_id"],
            "fulfillment_mode": "DESK",
        },
        headers={**admin_headers, "Idempotency-Key": f"pw-issue-{issue_fixture['tag']}"},
    )
    assert commit.status_code in (200, 201), commit.text
    issue_fixture["loan_id"] = commit.json()["loan_id"]
    return issue_fixture


def staff_login(
    page: Page,
    base_url: str,
    username: str = "librarian",
    password: str = "changeme",
) -> None:
    page.goto(f"{base_url}/staff/")
    page.get_by_label("Username").fill(username)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()
    page.get_by_role("navigation", name="Staff desk navigation").wait_for()
