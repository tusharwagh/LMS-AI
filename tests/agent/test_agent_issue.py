"""Agent desk tests (Phase 8)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from lms.agent.session import SessionStore

pytestmark = [pytest.mark.agent, pytest.mark.e2e]


@pytest.fixture
def agent_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_ISSUE_ENABLED", "true")
    monkeypatch.setenv("AGENT_MOCK_LLM", "true")
    from lms.config import get_settings

    get_settings.cache_clear()


@pytest.fixture
def agent_store() -> SessionStore:
    return SessionStore()


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _seed(client: TestClient, admin_headers: dict[str, str], tag: str) -> dict:
    rule_id = client.post(
        "/api/v1/loan/loan-rule-sets",
        json={"name": f"Rule {tag}", "max_active_loans": 2, "loan_period_days": 14},
        headers=admin_headers,
    ).json()["id"]
    patron_type_id = client.post(
        "/api/v1/reference/patron-types",
        json={"code": f"AG_{tag}", "name": "Student", "loan_rule_set_id": rule_id},
        headers=admin_headers,
    ).json()["id"]
    patron_id = client.post(
        "/api/v1/reference/patrons",
        json={
            "display_name": f"Agent Patron {tag}",
            "patron_type_id": patron_type_id,
            "card_barcode": f"ACARD-{tag}",
            "external_ref": f"AADM-{tag}",
        },
    ).json()["id"]
    catalog_id = client.post(
        "/api/v1/catalog/catalogs",
        json={"title": f"Agent Book {tag}", "language": "en"},
    ).json()["id"]
    client.post(f"/api/v1/catalog/catalogs/{catalog_id}/publish")
    holding_id = client.post(
        f"/api/v1/catalog/catalogs/{catalog_id}/holdings",
        json={"barcode": f"ABC-{tag}", "accession_number": f"AACC-{tag}"},
    ).json()["id"]
    return {
        "patron_name": f"Agent Patron {tag}",
        "title": f"Agent Book {tag}",
        "barcode": f"ABC-{tag}",
        "patron_id": patron_id,
        "holding_id": holding_id,
        "tag": tag,
    }


def test_agent_disabled_without_flag(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_ISSUE_ENABLED", "false")
    monkeypatch.setenv("AGENT_MOCK_LLM", "true")
    from lms.config import get_settings

    get_settings.cache_clear()
    res = client.post("/api/v1/agent/issue/sessions")
    assert res.status_code == 403


def test_agent_conversational_desk_issue(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    """G11 — NL issue with HITL commit."""
    tag = _uid()
    fx = _seed(client, admin_headers, tag)

    sess = client.post("/api/v1/agent/issue/sessions")
    assert sess.status_code == 201, sess.text
    session_id = sess.json()["session_id"]

    msg = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"Issue {fx['title']} to {fx['patron_name']}, desk pickup"},
    )
    assert msg.status_code == 200, msg.text
    body = msg.json()
    assert body["pending_approval"] is not None
    assert body["pending_approval"]["kind"] == "commit_issue"
    assert fx["patron_name"] in body["pending_approval"]["summary"]
    assert fx["title"] in body["assistant_message"]
    assert "desk pickup" in body["assistant_message"].lower()
    assert "review" in body["assistant_message"].lower()

    deny = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/resume",
        json={"approved": False},
    )
    assert deny.status_code == 200
    assert "denied" in deny.json()["assistant_message"].lower()

    msg2 = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"Issue {fx['title']} to {fx['patron_name']}, desk pickup"},
    )
    assert msg2.status_code == 200
    assert msg2.json()["pending_approval"] is not None

    approve = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/resume",
        json={"approved": True},
    )
    assert approve.status_code == 200, approve.text
    assert "issued" in approve.json()["assistant_message"].lower()

    open_loans = client.get(f"/api/v1/loan/loans/open?patron_id={fx['patron_id']}")
    assert open_loans.status_code == 200
    assert len(open_loans.json()) >= 1


def test_agent_delivery_fulfillment_transition(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    """G12 — delivery issue + agentic fulfillment transition with HITL."""
    tag = _uid()
    fx = _seed(client, admin_headers, tag)

    sess = client.post("/api/v1/agent/issue/sessions").json()
    session_id = sess["session_id"]

    pending = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={
            "message": f"Issue {fx['title']} to {fx['patron_name']}, deliver to Class 5A",
        },
    )
    assert pending.status_code == 200, pending.text
    assert pending.json()["pending_approval"]["kind"] == "commit_issue"

    committed = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/resume",
        json={"approved": True},
    )
    assert committed.status_code == 200, committed.text

    ready_pending = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "Mark ready for dispatch"},
    )
    assert ready_pending.status_code == 200, ready_pending.text
    assert ready_pending.json()["pending_approval"]["kind"] == "transition_fulfillment"
    client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/resume",
        json={"approved": True},
    )

    transit_pending = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "Mark in transit"},
    )
    assert transit_pending.status_code == 200, transit_pending.text
    assert transit_pending.json()["pending_approval"] is not None
    assert transit_pending.json()["pending_approval"]["kind"] == "transition_fulfillment"

    done = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/resume",
        json={"approved": True},
    )
    assert done.status_code == 200, done.text
    assert "in transit" in done.json()["assistant_message"].lower() or "IN_TRANSIT" in done.text


def test_agent_governance_tool_allowlist_unit() -> None:
    from lms.agent.tools import AUTHORIZED_TOOL_NAMES, READ_TOOL_NAMES, RESTRICTED_TOOL_NAMES

    assert "direct_db" in RESTRICTED_TOOL_NAMES
    assert "commit_issue" in AUTHORIZED_TOOL_NAMES
    assert "select_barcode" in READ_TOOL_NAMES
    assert "cancel_issue" in AUTHORIZED_TOOL_NAMES
    assert "direct_db" not in AUTHORIZED_TOOL_NAMES


def test_agent_select_barcode_after_catalog_search(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    tag = _uid()
    fx = _seed(client, admin_headers, tag)
    catalog_id = client.post(
        "/api/v1/catalog/catalogs",
        json={"title": fx["title"], "language": "en"},
    ).json()["id"]
    client.post(f"/api/v1/catalog/catalogs/{catalog_id}/publish")
    client.post(
        f"/api/v1/catalog/catalogs/{catalog_id}/holdings",
        json={"barcode": f"ALT-{tag}", "accession_number": f"ALTACC-{tag}"},
    )

    sess = client.post("/api/v1/agent/issue/sessions")
    session_id = sess.json()["session_id"]

    patron = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": fx["patron_name"]},
    )
    assert patron.status_code == 200, patron.text
    patron_msg = patron.json()["assistant_message"]
    assert fx["patron_name"] in patron_msg
    assert "matching" in patron_msg.lower() or "ready to borrow" in patron_msg.lower()

    search = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"search {fx['title']}"},
    )
    assert search.status_code == 200, search.text
    search_msg = search.json()["assistant_message"]
    assert fx["title"] in search_msg
    assert "matching" in search_msg.lower() or "found" in search_msg.lower()

    select = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"barcode {fx['barcode']}"},
    )
    assert select.status_code == 200, select.text
    select_msg = select.json()["assistant_message"]
    assert fx["barcode"] in select_msg
    assert "selected" in select_msg.lower() or "barcode" in select_msg.lower()
    assert select.json()["session_summary"]["holding_barcode"] == fx["barcode"]


def test_agent_help_message_is_friendly_not_patron_search(
    client: TestClient,
    agent_env: None,
) -> None:
    sess = client.post("/api/v1/agent/issue/sessions")
    session_id = sess.json()["session_id"]

    res = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "help"},
    )
    assert res.status_code == 200, res.text
    msg = res.json()["assistant_message"].lower()
    assert "issue" in msg
    assert "no patrons matched" not in msg
    assert "pseudonym" not in msg


def test_agent_cancel_issue_with_hitl(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    tag = _uid()
    fx = _seed(client, admin_headers, tag)

    sess = client.post("/api/v1/agent/issue/sessions").json()
    session_id = sess["session_id"]

    pending = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"Issue {fx['title']} to {fx['patron_name']}, desk pickup"},
    )
    assert pending.status_code == 200, pending.text
    client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/resume",
        json={"approved": True},
    )

    open_before = client.get(f"/api/v1/loan/loans/open?patron_id={fx['patron_id']}")
    assert len(open_before.json()) >= 1

    cancel_pending = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "Cancel the issue"},
    )
    assert cancel_pending.status_code == 200, cancel_pending.text
    assert cancel_pending.json()["pending_approval"]["kind"] == "cancel_issue"

    cancelled = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/resume",
        json={"approved": True},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert "cancelled" in cancelled.json()["assistant_message"].lower()

    open_after = client.get(f"/api/v1/loan/loans/open?patron_id={fx['patron_id']}")
    assert open_after.status_code == 200
    assert len(open_after.json()) == 0
