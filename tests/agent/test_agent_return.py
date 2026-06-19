"""Agent desk return workflow tests (WF-02)."""

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


def _seed_and_issue(
    client: TestClient,
    admin_headers: dict[str, str],
    tag: str,
) -> dict:
    rule_id = client.post(
        "/api/v1/loan/loan-rule-sets",
        json={"name": f"Rule {tag}", "max_active_loans": 2, "loan_period_days": 14},
        headers=admin_headers,
    ).json()["id"]
    patron_type_id = client.post(
        "/api/v1/reference/patron-types",
        json={"code": f"RT_{tag}", "name": "Student", "loan_rule_set_id": rule_id},
        headers=admin_headers,
    ).json()["id"]
    patron_id = client.post(
        "/api/v1/reference/patrons",
        json={
            "display_name": f"Return Patron {tag}",
            "patron_type_id": patron_type_id,
            "card_barcode": f"RCARD-{tag}",
            "external_ref": f"RADM-{tag}",
        },
    ).json()["id"]
    catalog_id = client.post(
        "/api/v1/catalog/catalogs",
        json={"title": f"Return Book {tag}", "language": "en"},
    ).json()["id"]
    client.post(f"/api/v1/catalog/catalogs/{catalog_id}/publish")
    holding_id = client.post(
        f"/api/v1/catalog/catalogs/{catalog_id}/holdings",
        json={"barcode": f"RBC-{tag}", "accession_number": f"RACC-{tag}"},
    ).json()["id"]

    issue = client.post(
        "/api/v1/workflows/issue/commit",
        json={
            "patron_id": patron_id,
            "holding_id": holding_id,
            "fulfillment_mode": "DESK",
        },
        headers={**admin_headers, "Idempotency-Key": f"seed-issue-{tag}"},
    )
    assert issue.status_code == 201, issue.text

    return {
        "patron_name": f"Return Patron {tag}",
        "title": f"Return Book {tag}",
        "barcode": f"RBC-{tag}",
        "patron_id": patron_id,
        "holding_id": holding_id,
        "tag": tag,
    }


def test_agent_desk_return_with_hitl(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    """WF-02 — NL return with HITL desk check-in."""
    tag = _uid()
    fx = _seed_and_issue(client, admin_headers, tag)

    open_before = client.get(f"/api/v1/loan/loans/open?patron_id={fx['patron_id']}")
    assert len(open_before.json()) == 1

    sess = client.post("/api/v1/agent/issue/sessions")
    assert sess.status_code == 201, sess.text
    session_id = sess.json()["session_id"]

    lookup = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"Return barcode {fx['barcode']}"},
    )
    assert lookup.status_code == 200, lookup.text
    lookup_body = lookup.json()
    assert fx["patron_name"] in lookup_body["assistant_message"]
    assert fx["title"] in lookup_body["assistant_message"]
    assert lookup_body["session_summary"]["active_flow"] == "return"
    assert "complete return" in lookup_body["assistant_message"].lower()

    pending = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "Complete return at desk"},
    )
    assert pending.status_code == 200, pending.text
    pending_body = pending.json()
    assert pending_body["pending_approval"] is not None
    assert pending_body["pending_approval"]["kind"] == "commit_return"
    assert fx["title"] in pending_body["pending_approval"]["summary"]
    assert "review" in pending_body["assistant_message"].lower()

    deny = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/resume",
        json={"approved": False},
    )
    assert deny.status_code == 200
    assert "denied" in deny.json()["assistant_message"].lower()

    pending2 = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "Desk return"},
    )
    assert pending2.status_code == 200
    assert pending2.json()["pending_approval"]["kind"] == "commit_return"

    approved = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/resume",
        json={"approved": True},
    )
    assert approved.status_code == 200, approved.text
    assert "checked in" in approved.json()["assistant_message"].lower()

    open_after = client.get(f"/api/v1/loan/loans/open?patron_id={fx['patron_id']}")
    assert open_after.status_code == 200
    assert len(open_after.json()) == 0


def test_agent_return_lookup_intent_parser() -> None:
    from lms.agent.intent_parser import IntentParser
    from lms.agent.schemas import IntentAction

    parser = IntentParser()
    intent = parser.parse("Return barcode RBC-123", has_pending_approval=False)
    assert intent.action == IntentAction.LOOKUP_RETURN
    assert intent.holding_barcode == "RBC-123"

    commit = parser.parse("Complete return", has_pending_approval=False)
    assert commit.action == IntentAction.REQUEST_COMMIT_RETURN


def test_agent_governance_return_tools_allowlisted() -> None:
    from lms.agent.tools import AUTHORIZED_TOOL_NAMES, READ_TOOL_NAMES, WRITE_TOOL_NAMES

    assert "lookup_return" in READ_TOOL_NAMES
    assert "search_return_loans" in READ_TOOL_NAMES
    assert "select_return_loan" in READ_TOOL_NAMES
    assert "commit_desk_return" in WRITE_TOOL_NAMES
    assert "apply_return_selection" in WRITE_TOOL_NAMES
    assert "initiate_return_pickup" in AUTHORIZED_TOOL_NAMES


def test_agent_return_by_patron_name_with_multi_select_hitl(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    """Return by patron name when multiple loans — list, select, approve, commit."""
    tag = _uid()
    fx = _seed_and_issue(client, admin_headers, tag)

    catalog2_id = client.post(
        "/api/v1/catalog/catalogs",
        json={"title": f"Second Return Book {tag}", "language": "en"},
    ).json()["id"]
    client.post(f"/api/v1/catalog/catalogs/{catalog2_id}/publish")
    holding2_id = client.post(
        f"/api/v1/catalog/catalogs/{catalog2_id}/holdings",
        json={"barcode": f"RBC2-{tag}", "accession_number": f"RACC2-{tag}"},
    ).json()["id"]
    issue2 = client.post(
        "/api/v1/workflows/issue/commit",
        json={
            "patron_id": fx["patron_id"],
            "holding_id": holding2_id,
            "fulfillment_mode": "DESK",
        },
        headers={**admin_headers, "Idempotency-Key": f"seed-issue2-{tag}"},
    )
    assert issue2.status_code == 201, issue2.text

    sess = client.post("/api/v1/agent/issue/sessions").json()
    session_id = sess["session_id"]

    search = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"Return from {fx['patron_name']}"},
    )
    assert search.status_code == 200, search.text
    search_body = search.json()
    assert search_body["session_summary"]["return_candidate_count"] == 2
    assert fx["barcode"] in search_body["assistant_message"]
    assert f"RBC2-{tag}" in search_body["assistant_message"]

    pick = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"barcode {fx['barcode']}"},
    )
    assert pick.status_code == 200, pick.text
    pick_body = pick.json()
    assert pick_body["pending_approval"]["kind"] == "select_return"
    assert fx["title"] in pick_body["pending_approval"]["summary"]

    selected = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/resume",
        json={"approved": True},
    )
    assert selected.status_code == 200, selected.text
    assert "selected" in selected.json()["assistant_message"].lower()

    commit_pending = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "Complete return"},
    )
    assert commit_pending.status_code == 200, commit_pending.text
    assert commit_pending.json()["pending_approval"]["kind"] == "commit_return"

    committed = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/resume",
        json={"approved": True},
    )
    assert committed.status_code == 200, committed.text
    assert "checked in" in committed.json()["assistant_message"].lower()

    open_loans = client.get(f"/api/v1/loan/loans/open?patron_id={fx['patron_id']}")
    assert len(open_loans.json()) == 1
    assert open_loans.json()[0]["holding_barcode"] == f"RBC2-{tag}"


def test_agent_return_by_title_and_patron_single_match(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    tag = _uid()
    fx = _seed_and_issue(client, admin_headers, tag)

    sess = client.post("/api/v1/agent/issue/sessions").json()
    session_id = sess["session_id"]

    search = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"Return {fx['title']} from {fx['patron_name']}"},
    )
    assert search.status_code == 200, search.text
    body = search.json()
    assert fx["title"] in body["assistant_message"]
    assert "complete return" in body["assistant_message"].lower()
    assert body["session_summary"].get("return_candidate_count", 0) == 0

    pending = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "Desk return"},
    )
    assert pending.json()["pending_approval"]["kind"] == "commit_return"
    client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/resume",
        json={"approved": True},
    )

    open_loans = client.get(f"/api/v1/loan/loans/open?patron_id={fx['patron_id']}")
    assert len(open_loans.json()) == 0


def test_agent_return_search_intent_parser() -> None:
    from lms.agent.intent_parser import IntentParser
    from lms.agent.schemas import IntentAction

    parser = IntentParser()
    intent = parser.parse(
        "Return Harry Potter from Riya Sharma",
        has_pending_approval=False,
    )
    assert intent.action == IntentAction.SEARCH_RETURN
    assert intent.catalog_query == "Harry Potter"
    assert intent.patron_query == "Riya Sharma"

    patron_only = parser.parse("Return from Riya Sharma", has_pending_approval=False)
    assert patron_only.action == IntentAction.SEARCH_RETURN
    assert patron_only.patron_query == "Riya Sharma"
