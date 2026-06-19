"""Agent desk catalog-first issue flow tests."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.agent, pytest.mark.e2e]


@pytest.fixture
def agent_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_ISSUE_ENABLED", "true")
    monkeypatch.setenv("AGENT_MOCK_LLM", "true")
    from lms.config import get_settings

    get_settings.cache_clear()


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _seed_lendable(client: TestClient, admin_headers: dict[str, str], tag: str) -> dict:
    rule_id = client.post(
        "/api/v1/loan/loan-rule-sets",
        json={"name": f"Rule {tag}", "max_active_loans": 3, "loan_period_days": 14},
        headers=admin_headers,
    ).json()["id"]
    patron_type_id = client.post(
        "/api/v1/reference/patron-types",
        json={"code": f"CAT_{tag}", "name": "Student", "loan_rule_set_id": rule_id},
        headers=admin_headers,
    ).json()["id"]
    patron_id = client.post(
        "/api/v1/reference/patrons",
        json={
            "display_name": f"Catalog Patron {tag}",
            "patron_type_id": patron_type_id,
            "card_barcode": f"CCARD-{tag}",
            "external_ref": f"CADM-{tag}",
        },
    ).json()["id"]
    catalog_id = client.post(
        "/api/v1/catalog/catalogs",
        json={"title": f"Catalog Book {tag}", "language": "en"},
    ).json()["id"]
    client.post(f"/api/v1/catalog/catalogs/{catalog_id}/publish")
    holding_id = client.post(
        f"/api/v1/catalog/catalogs/{catalog_id}/holdings",
        json={"barcode": f"CBC-{tag}", "accession_number": f"CACC-{tag}"},
    ).json()["id"]
    return {
        "patron_name": f"Catalog Patron {tag}",
        "title": f"Catalog Book {tag}",
        "barcode": f"CBC-{tag}",
        "patron_id": patron_id,
        "holding_id": holding_id,
        "tag": tag,
    }


def test_agent_catalog_search_then_issue_with_hitl(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    """Catalog search → issue to patron → HITL → committed loan."""
    tag = _uid()
    fx = _seed_lendable(client, admin_headers, tag)

    sess = client.post("/api/v1/agent/issue/sessions").json()
    session_id = sess["session_id"]

    search = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"Search {fx['title']}"},
    )
    assert search.status_code == 200, search.text
    search_body = search.json()
    assert fx["title"] in search_body["assistant_message"]
    assert fx["barcode"] in search_body["assistant_message"]
    assert "issue to" in search_body["assistant_message"].lower()

    issue_pending = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"Issue to {fx['patron_name']}, desk pickup"},
    )
    assert issue_pending.status_code == 200, issue_pending.text
    pending_body = issue_pending.json()
    assert pending_body["pending_approval"]["kind"] == "commit_issue"
    assert fx["patron_name"] in pending_body["pending_approval"]["summary"]
    assert fx["title"] in pending_body["pending_approval"]["summary"]

    approved = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/resume",
        json={"approved": True},
    )
    assert approved.status_code == 200, approved.text
    assert "issued" in approved.json()["assistant_message"].lower()

    open_loans = client.get(f"/api/v1/loan/loans/open?patron_id={fx['patron_id']}")
    assert len(open_loans.json()) == 1


def test_agent_catalog_search_multi_copy_select_then_issue(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    tag = _uid()
    fx = _seed_lendable(client, admin_headers, tag)
    catalog2_id = client.post(
        "/api/v1/catalog/catalogs",
        json={"title": fx["title"], "language": "en"},
    ).json()["id"]
    client.post(f"/api/v1/catalog/catalogs/{catalog2_id}/publish")
    client.post(
        f"/api/v1/catalog/catalogs/{catalog2_id}/holdings",
        json={"barcode": f"CBC2-{tag}", "accession_number": f"CACC2-{tag}"},
    )

    sess = client.post("/api/v1/agent/issue/sessions").json()
    session_id = sess["session_id"]

    search = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"Find book {fx['title']}"},
    )
    assert search.status_code == 200, search.text
    assert search.json()["session_summary"]["catalog_candidate_count"] == 2

    pick = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"barcode {fx['barcode']}"},
    )
    assert pick.status_code == 200, pick.text
    assert "issue to" in pick.json()["assistant_message"].lower()

    pending = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"Issue to {fx['patron_name']}, desk pickup"},
    )
    assert pending.json()["pending_approval"]["kind"] == "commit_issue"
    client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/resume",
        json={"approved": True},
    )

    open_loans = client.get(f"/api/v1/loan/loans/open?patron_id={fx['patron_id']}")
    assert open_loans.json()[0]["holding_barcode"] == fx["barcode"]


def test_agent_catalog_search_intent_parser() -> None:
    from lms.agent.intent_parser import IntentParser
    from lms.agent.schemas import IntentAction

    parser = IntentParser()
    intent = parser.parse("Search Harry Potter", has_pending_approval=False)
    assert intent.action == IntentAction.SEARCH_CATALOG
    assert intent.catalog_query == "Harry Potter"

    issue_to = parser.parse(
        "Issue to Riya Sharma, desk pickup",
        has_pending_approval=False,
        has_selected_copy_no_patron=True,
    )
    assert issue_to.action == IntentAction.ISSUE_TO_PATRON
    assert issue_to.patron_query == "Riya Sharma"


def test_agent_catalog_tools_allowlisted() -> None:
    from lms.agent.tools import AUTHORIZED_TOOL_NAMES, READ_TOOL_NAMES

    assert "search_catalog" in READ_TOOL_NAMES
    assert "select_catalog_copy" in READ_TOOL_NAMES
    assert "search_catalog" in AUTHORIZED_TOOL_NAMES
