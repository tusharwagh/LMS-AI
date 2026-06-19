"""Agent desk guided issue flow — patron-first, subject/area book search."""

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


def _seed_guided_issue(
    client: TestClient,
    admin_headers: dict[str, str],
    tag: str,
    *,
    subject_tags: list[str] | None = None,
    call_number: str | None = None,
) -> dict:
    rule_id = client.post(
        "/api/v1/loan/loan-rule-sets",
        json={"name": f"Rule {tag}", "max_active_loans": 3, "loan_period_days": 14},
        headers=admin_headers,
    ).json()["id"]
    patron_type_id = client.post(
        "/api/v1/reference/patron-types",
        json={"code": f"GI_{tag}", "name": "Student", "loan_rule_set_id": rule_id},
        headers=admin_headers,
    ).json()["id"]
    patron_id = client.post(
        "/api/v1/reference/patrons",
        json={
            "display_name": f"Guided Patron {tag}",
            "patron_type_id": patron_type_id,
            "card_barcode": f"GICARD-{tag}",
            "external_ref": f"GIADM-{tag}",
        },
    ).json()["id"]
    catalog_body: dict = {"title": f"Guided Book {tag}", "language": "en"}
    if subject_tags:
        catalog_body["subject_tags"] = subject_tags
    if call_number:
        catalog_body["call_number"] = call_number
    catalog_id = client.post(
        "/api/v1/catalog/catalogs",
        json=catalog_body,
        headers=admin_headers,
    ).json()["id"]
    client.post(f"/api/v1/catalog/catalogs/{catalog_id}/publish")
    holding_id = client.post(
        f"/api/v1/catalog/catalogs/{catalog_id}/holdings",
        json={"barcode": f"GIBC-{tag}", "accession_number": f"GIACC-{tag}"},
    ).json()["id"]
    return {
        "patron_name": f"Guided Patron {tag}",
        "title": f"Guided Book {tag}",
        "barcode": f"GIBC-{tag}",
        "patron_id": patron_id,
        "holding_id": holding_id,
        "tag": tag,
    }


def test_agent_guided_issue_subject_search_then_hitl(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    """Patron-first issue → subject criteria → copy list → HITL commit."""
    tag = _uid()
    subject = f"scifi-{tag}"
    fx = _seed_guided_issue(client, admin_headers, tag, subject_tags=[subject])

    sess = client.post("/api/v1/agent/issue/sessions").json()
    session_id = sess["session_id"]

    start = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"I want to issue a book to {fx['patron_name']}"},
    )
    assert start.status_code == 200, start.text
    start_body = start.json()
    assert start_body["session_summary"]["awaiting_book_criteria"] is True
    assert "subject" in start_body["assistant_message"].lower()
    assert fx["patron_name"] in start_body["assistant_message"]

    search = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": subject},
    )
    assert search.status_code == 200, search.text
    search_body = search.json()
    assert search_body["session_summary"].get("awaiting_book_criteria") is not True
    assert fx["barcode"] in search_body["assistant_message"]
    assert "issue" in search_body["assistant_message"].lower()

    pending = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "issue"},
    )
    assert pending.status_code == 200, pending.text
    pending_body = pending.json()
    assert pending_body["pending_approval"]["kind"] == "commit_issue"
    assert fx["patron_name"] in pending_body["pending_approval"]["summary"]

    approved = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/resume",
        json={"approved": True},
    )
    assert approved.status_code == 200, approved.text
    assert "issued" in approved.json()["assistant_message"].lower()

    open_loans = client.get(f"/api/v1/loan/loans/open?patron_id={fx['patron_id']}")
    assert len(open_loans.json()) == 1


def test_agent_guided_issue_no_match_retry_then_cancel(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    tag = _uid()
    subject = f"history-{tag}"
    fx = _seed_guided_issue(client, admin_headers, tag, subject_tags=[subject])

    sess = client.post("/api/v1/agent/issue/sessions").json()
    session_id = sess["session_id"]

    client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"I want to issue a book to {fx['patron_name']}"},
    )

    miss = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"nomatch-{tag}"},
    )
    assert miss.status_code == 200, miss.text
    miss_body = miss.json()
    assert miss_body["session_summary"]["awaiting_book_criteria"] is True
    assert f"nomatch-{tag}" in miss_body["assistant_message"]
    assert "cancel" in miss_body["assistant_message"].lower()

    retry = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": subject},
    )
    assert retry.status_code == 200, retry.text
    assert fx["barcode"] in retry.json()["assistant_message"]

    cancel = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "cancel"},
    )
    assert cancel.status_code == 200, cancel.text
    cancel_body = cancel.json()
    assert cancel_body["session_summary"].get("awaiting_book_criteria") is not True
    assert "stopped" in cancel_body["assistant_message"].lower()


def test_agent_guided_issue_multi_copy_select(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    tag = _uid()
    fx = _seed_guided_issue(client, admin_headers, tag, call_number=f"FIC-GI-{tag}")
    catalog2_id = client.post(
        "/api/v1/catalog/catalogs",
        json={
            "title": f"Guided Book Two {tag}",
            "language": "en",
            "call_number": f"FIC-GI-{tag}",
        },
        headers=admin_headers,
    ).json()["id"]
    client.post(f"/api/v1/catalog/catalogs/{catalog2_id}/publish")
    client.post(
        f"/api/v1/catalog/catalogs/{catalog2_id}/holdings",
        json={"barcode": f"GIBC2-{tag}", "accession_number": f"GIACC2-{tag}"},
    )

    sess = client.post("/api/v1/agent/issue/sessions").json()
    session_id = sess["session_id"]

    client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"I want to issue a book to {fx['patron_name']}"},
    )
    search = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"FIC-GI-{tag}"},
    )
    assert search.json()["session_summary"]["catalog_candidate_count"] == 2

    pick = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"barcode {fx['barcode']}"},
    )
    assert pick.status_code == 200, pick.text
    assert "issue" in pick.json()["assistant_message"].lower()

    pending = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "issue"},
    )
    assert pending.json()["pending_approval"]["kind"] == "commit_issue"
    client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/resume",
        json={"approved": True},
    )
    open_loans = client.get(f"/api/v1/loan/loans/open?patron_id={fx['patron_id']}")
    assert open_loans.json()[0]["holding_barcode"] == fx["barcode"]


def test_agent_guided_issue_no_patron_then_subject_then_hitl(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    """No patron in opener → ask patron → criteria → HITL commit."""
    tag = _uid()
    subject = f"scifi-{tag}"
    fx = _seed_guided_issue(client, admin_headers, tag, subject_tags=[subject])

    sess = client.post("/api/v1/agent/issue/sessions").json()
    session_id = sess["session_id"]

    start = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "I want to issue a book"},
    )
    assert start.status_code == 200, start.text
    start_body = start.json()
    assert start_body["session_summary"]["awaiting_patron"] is True
    assert start_body["session_summary"].get("awaiting_book_criteria") is not True
    assert "borrower" in start_body["assistant_message"].lower()

    patron = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": fx["patron_name"]},
    )
    assert patron.status_code == 200, patron.text
    patron_body = patron.json()
    assert patron_body["session_summary"].get("awaiting_patron") is not True
    assert patron_body["session_summary"]["awaiting_book_criteria"] is True
    assert fx["patron_name"] in patron_body["assistant_message"]
    assert "subject" in patron_body["assistant_message"].lower()

    search = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": subject},
    )
    assert search.status_code == 200, search.text
    assert fx["barcode"] in search.json()["assistant_message"]

    pending = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "issue"},
    )
    assert pending.json()["pending_approval"]["kind"] == "commit_issue"
    client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/resume",
        json={"approved": True},
    )
    open_loans = client.get(f"/api/v1/loan/loans/open?patron_id={fx['patron_id']}")
    assert len(open_loans.json()) == 1


def test_agent_guided_issue_no_patron_cancel(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    tag = _uid()
    _seed_guided_issue(client, admin_headers, tag, subject_tags=["history"])

    sess = client.post("/api/v1/agent/issue/sessions").json()
    session_id = sess["session_id"]

    client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "I want to issue a book"},
    )
    cancel = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "cancel"},
    )
    assert cancel.status_code == 200, cancel.text
    cancel_body = cancel.json()
    assert cancel_body["session_summary"].get("awaiting_patron") is not True
    assert "stopped" in cancel_body["assistant_message"].lower()


def test_guided_issue_intent_parser() -> None:
    from lms.agent.intent_parser import IntentParser
    from lms.agent.schemas import IntentAction

    parser = IntentParser()
    start = parser.parse(
        "I want to issue a book to Riya Sharma",
        has_pending_approval=False,
    )
    assert start.action == IntentAction.START_ISSUE_TO_PATRON
    assert start.patron_query == "Riya Sharma"

    generic = parser.parse("I want to issue a book", has_pending_approval=False)
    assert generic.action == IntentAction.START_ISSUE_TO_PATRON
    assert generic.patron_query is None

    criteria = parser.parse(
        "science fiction",
        has_pending_approval=False,
        has_pending_book_criteria_prompt=True,
    )
    assert criteria.action == IntentAction.PROVIDE_BOOK_CRITERIA
    assert criteria.catalog_query == "science fiction"

    decline = parser.parse(
        "cancel",
        has_pending_approval=False,
        has_pending_book_criteria_prompt=True,
    )
    assert decline.action == IntentAction.DECLINE_CONTINUE

    patron_step = parser.parse(
        "Riya Sharma",
        has_pending_approval=False,
        has_pending_patron_prompt=True,
    )
    assert patron_step.action == IntentAction.PROVIDE_PATRON_FOR_ISSUE
    assert patron_step.patron_query == "Riya Sharma"

    patron_cancel = parser.parse(
        "cancel",
        has_pending_approval=False,
        has_pending_patron_prompt=True,
    )
    assert patron_cancel.action == IntentAction.DECLINE_CONTINUE
