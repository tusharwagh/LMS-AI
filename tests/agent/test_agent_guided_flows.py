"""Agent desk guided flows — return, catalog browse, patron lookup."""

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


def _seed_return_loan(
    client: TestClient,
    admin_headers: dict[str, str],
    tag: str,
    *,
    subject_tags: list[str] | None = None,
) -> dict:
    rule_id = client.post(
        "/api/v1/loan/loan-rule-sets",
        json={"name": f"Rule {tag}", "max_active_loans": 3, "loan_period_days": 14},
        headers=admin_headers,
    ).json()["id"]
    patron_type_id = client.post(
        "/api/v1/reference/patron-types",
        json={"code": f"GR_{tag}", "name": "Student", "loan_rule_set_id": rule_id},
        headers=admin_headers,
    ).json()["id"]
    patron_id = client.post(
        "/api/v1/reference/patrons",
        json={
            "display_name": f"Return Guided {tag}",
            "patron_type_id": patron_type_id,
            "card_barcode": f"GRCARD-{tag}",
            "external_ref": f"GRADM-{tag}",
        },
    ).json()["id"]
    catalog_body: dict = {"title": f"Return Guided Book {tag}", "language": "en"}
    if subject_tags:
        catalog_body["subject_tags"] = subject_tags
    catalog_id = client.post(
        "/api/v1/catalog/catalogs",
        json=catalog_body,
        headers=admin_headers,
    ).json()["id"]
    client.post(f"/api/v1/catalog/catalogs/{catalog_id}/publish")
    holding_id = client.post(
        f"/api/v1/catalog/catalogs/{catalog_id}/holdings",
        json={"barcode": f"GRBC-{tag}", "accession_number": f"GRACC-{tag}"},
    ).json()["id"]
    issue = client.post(
        "/api/v1/workflows/issue/commit",
        json={
            "patron_id": patron_id,
            "holding_id": holding_id,
            "fulfillment_mode": "DESK",
        },
        headers={**admin_headers, "Idempotency-Key": f"seed-gr-{tag}"},
    )
    assert issue.status_code == 201, issue.text
    return {
        "patron_name": f"Return Guided {tag}",
        "title": f"Return Guided Book {tag}",
        "barcode": f"GRBC-{tag}",
        "card": f"GRCARD-{tag}",
        "patron_id": patron_id,
        "tag": tag,
    }


def _seed_catalog_browse(
    client: TestClient,
    admin_headers: dict[str, str],
    tag: str,
    *,
    subject_tags: list[str] | None = None,
    call_number: str | None = None,
) -> dict:
    catalog_body: dict = {"title": f"Browse Book {tag}", "language": "en"}
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
        json={"barcode": f"GBC-{tag}", "accession_number": f"GACC-{tag}"},
    ).json()["id"]
    return {
        "title": f"Browse Book {tag}",
        "barcode": f"GBC-{tag}",
        "holding_id": holding_id,
        "tag": tag,
    }


def _seed_patron_lookup(
    client: TestClient,
    admin_headers: dict[str, str],
    tag: str,
) -> dict:
    rule_id = client.post(
        "/api/v1/loan/loan-rule-sets",
        json={"name": f"Rule PL {tag}", "max_active_loans": 3, "loan_period_days": 14},
        headers=admin_headers,
    ).json()["id"]
    patron_type_id = client.post(
        "/api/v1/reference/patron-types",
        json={"code": f"PL_{tag}", "name": "Student", "loan_rule_set_id": rule_id},
        headers=admin_headers,
    ).json()["id"]
    patron_id = client.post(
        "/api/v1/reference/patrons",
        json={
            "display_name": f"Lookup Patron {tag}",
            "patron_type_id": patron_type_id,
            "card_barcode": f"PLCARD-{tag}",
            "external_ref": f"PLADM-{tag}",
        },
    ).json()["id"]
    return {
        "patron_name": f"Lookup Patron {tag}",
        "card": f"PLCARD-{tag}",
        "adm": f"PLADM-{tag}",
        "patron_id": patron_id,
        "tag": tag,
    }


def test_agent_patron_wants_return_single_book_fast_path(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    """Return intent + one loan → ready for complete return without extra menu."""
    tag = _uid()
    fx = _seed_return_loan(client, admin_headers, tag)

    session_id = client.post("/api/v1/agent/issue/sessions").json()["session_id"]

    start = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "I want to return a book"},
    )
    assert start.status_code == 200, start.text
    assert "return a book" in start.json()["assistant_message"].lower()

    identify = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": fx["patron_name"]},
    )
    assert identify.status_code == 200, identify.text
    body = identify.json()
    assert body["session_summary"].get("desk_return_intent") is True
    assert body["session_summary"].get("awaiting_desk_next_action") is not True
    assert "complete return" in body["assistant_message"].lower()
    assert fx["barcode"] in body["assistant_message"]

    pending = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "complete return"},
    )
    assert pending.json()["pending_approval"]["kind"] == "commit_return"
    client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/resume",
        json={"approved": True},
    )
    assert len(client.get(f"/api/v1/loan/loans/open?patron_id={fx['patron_id']}").json()) == 0


def test_agent_patron_desk_list_loans_then_return_hitl(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    """Patron at desk → list issued books → return one → HITL → refreshed desk."""
    tag = _uid()
    fx = _seed_return_loan(client, admin_headers, tag)

    session_id = client.post("/api/v1/agent/issue/sessions").json()["session_id"]

    list_loans = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"What books are issued to {fx['patron_name']}"},
    )
    assert list_loans.status_code == 200, list_loans.text
    list_body = list_loans.json()
    assert list_body["session_summary"]["awaiting_desk_next_action"] is True
    assert fx["patron_name"] in list_body["assistant_message"]
    assert fx["barcode"] in list_body["assistant_message"]
    assert "what would you like to do next" in list_body["assistant_message"].lower()

    pick = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"barcode {fx['barcode']}"},
    )
    assert pick.status_code == 200, pick.text
    pick_body = pick.json()
    assert pick_body["pending_approval"]["kind"] == "select_return"

    selected = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/resume",
        json={"approved": True},
    )
    assert selected.status_code == 200, selected.text
    assert "complete return" in selected.json()["assistant_message"].lower()

    pending = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "complete return"},
    )
    assert pending.json()["pending_approval"]["kind"] == "commit_return"

    approved = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/resume",
        json={"approved": True},
    )
    assert approved.status_code == 200, approved.text
    approved_body = approved.json()
    assert "checked in" in approved_body["assistant_message"].lower()
    assert "no books checked out" in approved_body["assistant_message"].lower()

    open_loans = client.get(f"/api/v1/loan/loans/open?patron_id={fx['patron_id']}")
    assert len(open_loans.json()) == 0


def test_agent_patron_desk_ask_patron_then_done(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    tag = _uid()
    fx = _seed_return_loan(client, admin_headers, tag)

    session_id = client.post("/api/v1/agent/issue/sessions").json()["session_id"]

    start = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "Which books are issued to me"},
    )
    assert start.status_code == 200, start.text
    start_body = start.json()
    assert start_body["session_summary"]["awaiting_desk_patron"] is True
    assert "who is the patron" in start_body["assistant_message"].lower()

    identify = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": fx["patron_name"]},
    )
    assert identify.status_code == 200, identify.text
    identify_body = identify.json()
    assert identify_body["session_summary"]["awaiting_desk_next_action"] is True
    assert fx["barcode"] in identify_body["assistant_message"]

    done = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "done"},
    )
    assert done.status_code == 200, done.text
    done_body = done.json()
    assert done_body["session_summary"].get("awaiting_desk_next_action") is not True
    assert "all set" in done_body["assistant_message"].lower()


def test_agent_patron_desk_patron_not_found_then_cancel(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    tag = _uid()
    _seed_return_loan(client, admin_headers, tag)

    session_id = client.post("/api/v1/agent/issue/sessions").json()["session_id"]

    client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "Return a book"},
    )

    miss = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"nomatch-{tag}"},
    )
    assert miss.status_code == 200, miss.text
    miss_body = miss.json()
    assert miss_body["session_summary"]["awaiting_desk_patron"] is True
    assert f"nomatch-{tag}" in miss_body["assistant_message"]

    cancel = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "cancel"},
    )
    assert cancel.status_code == 200, cancel.text
    cancel_body = cancel.json()
    assert cancel_body["session_summary"].get("awaiting_desk_patron") is not True
    assert "ended" in cancel_body["assistant_message"].lower()


def test_agent_guided_catalog_browse_subject(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    tag = _uid()
    subject = f"gbrowse-{tag}"
    fx = _seed_catalog_browse(client, admin_headers, tag, subject_tags=[subject])

    session_id = client.post("/api/v1/agent/issue/sessions").json()["session_id"]

    start = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "Search catalog"},
    )
    assert start.status_code == 200, start.text
    start_body = start.json()
    assert start_body["session_summary"]["awaiting_catalog_criteria"] is True
    assert start_body["session_summary"].get("patron_display_name") is None
    assert "subject" in start_body["assistant_message"].lower()

    search = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": subject},
    )
    assert search.status_code == 200, search.text
    search_body = search.json()
    assert search_body["session_summary"].get("awaiting_catalog_criteria") is not True
    assert fx["barcode"] in search_body["assistant_message"]
    assert "issue" not in search_body["assistant_message"].lower()


def test_agent_guided_catalog_browse_multi_copy_select(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    tag = _uid()
    fx = _seed_catalog_browse(client, admin_headers, tag, call_number=f"FIC-GB-{tag}")
    catalog2_id = client.post(
        "/api/v1/catalog/catalogs",
        json={
            "title": f"Browse Book Two {tag}",
            "language": "en",
            "call_number": f"FIC-GB-{tag}",
        },
        headers=admin_headers,
    ).json()["id"]
    client.post(f"/api/v1/catalog/catalogs/{catalog2_id}/publish")
    client.post(
        f"/api/v1/catalog/catalogs/{catalog2_id}/holdings",
        json={"barcode": f"GBC2-{tag}", "accession_number": f"GACC2-{tag}"},
    )

    session_id = client.post("/api/v1/agent/issue/sessions").json()["session_id"]

    client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "Find a book"},
    )
    search = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"FIC-GB-{tag}"},
    )
    assert search.json()["session_summary"]["catalog_candidate_count"] == 2

    pick = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": f"barcode {fx['barcode']}"},
    )
    assert pick.status_code == 200, pick.text
    pick_body = pick.json()
    assert fx["barcode"] in pick_body["assistant_message"]
    assert "issue" not in pick_body["assistant_message"].lower()


def test_agent_guided_patron_lookup_by_name(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    tag = _uid()
    fx = _seed_patron_lookup(client, admin_headers, tag)

    session_id = client.post("/api/v1/agent/issue/sessions").json()["session_id"]

    start = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "Look up patron"},
    )
    assert start.status_code == 200, start.text
    start_body = start.json()
    assert start_body["session_summary"]["awaiting_patron_lookup"] is True
    assert "name" in start_body["assistant_message"].lower()

    found = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": fx["patron_name"]},
    )
    assert found.status_code == 200, found.text
    found_body = found.json()
    assert found_body["session_summary"].get("awaiting_patron_lookup") is not True
    assert fx["patron_name"] in found_body["assistant_message"]
    assert "issue" not in found_body["assistant_message"].lower()


def test_agent_guided_patron_lookup_no_match_then_cancel(
    client: TestClient,
    admin_headers: dict[str, str],
    agent_env: None,
) -> None:
    tag = _uid()
    _seed_patron_lookup(client, admin_headers, tag)

    session_id = client.post("/api/v1/agent/issue/sessions").json()["session_id"]

    client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "Find patron"},
    )

    miss = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "Nobody Here"},
    )
    assert miss.status_code == 200, miss.text
    miss_body = miss.json()
    assert miss_body["session_summary"]["awaiting_patron_lookup"] is True
    assert "Nobody Here" in miss_body["assistant_message"]
    assert "cancel" in miss_body["assistant_message"].lower()

    cancel = client.post(
        f"/api/v1/agent/issue/sessions/{session_id}/message",
        json={"message": "cancel"},
    )
    assert cancel.status_code == 200, cancel.text
    cancel_body = cancel.json()
    assert cancel_body["session_summary"].get("awaiting_patron_lookup") is not True
    assert "stopped" in cancel_body["assistant_message"].lower()


def test_guided_flows_intent_parser() -> None:
    from lms.agent.intent_parser import IntentParser
    from lms.agent.schemas import IntentAction

    parser = IntentParser()

    start_return = parser.parse("I want to return a book", has_pending_approval=False)
    assert start_return.action == IntentAction.START_RETURN

    patron_loans = parser.parse(
        "What books are issued to Riya Sharma",
        has_pending_approval=False,
    )
    assert patron_loans.action == IntentAction.START_PATRON_DESK
    assert patron_loans.patron_query == "Riya Sharma"

    open_loans = parser.parse(
        "List open loans for Riya Sharma",
        has_pending_approval=False,
    )
    assert open_loans.action == IntentAction.START_PATRON_DESK
    assert open_loans.patron_query == "Riya Sharma"

    has_out = parser.parse(
        "What loans does Amit Sharma have",
        has_pending_approval=False,
    )
    assert has_out.action == IntentAction.START_PATRON_DESK
    assert has_out.patron_query == "Amit Sharma"

    show_issued = parser.parse(
        "Show issued to Riya Sharma",
        has_pending_approval=False,
    )
    assert show_issued.action == IntentAction.START_PATRON_DESK
    assert show_issued.patron_query == "Riya Sharma"

    desk_patron = parser.parse(
        "barcode RBC-123",
        has_pending_approval=False,
        has_pending_desk_patron=True,
    )
    assert desk_patron.action == IntentAction.PROVIDE_PATRON_FOR_DESK
    assert desk_patron.holding_barcode == "RBC-123"

    desk_issue = parser.parse(
        "issue a book",
        has_pending_approval=False,
        has_pending_desk_next_action=True,
    )
    assert desk_issue.action == IntentAction.DESK_START_ISSUE

    desk_return = parser.parse(
        "return",
        has_pending_approval=False,
        has_pending_desk_next_action=True,
        has_return_candidates=True,
    )
    assert desk_return.action == IntentAction.DESK_START_RETURN

    desk_done = parser.parse(
        "done",
        has_pending_approval=False,
        has_pending_desk_next_action=True,
    )
    assert desk_done.action == IntentAction.DESK_SESSION_DONE

    start_catalog = parser.parse("Browse catalog", has_pending_approval=False)
    assert start_catalog.action == IntentAction.START_CATALOG_SEARCH

    catalog_criteria = parser.parse(
        "science fiction",
        has_pending_approval=False,
        has_pending_catalog_criteria=True,
    )
    assert catalog_criteria.action == IntentAction.PROVIDE_CATALOG_CRITERIA
    assert catalog_criteria.catalog_query == "science fiction"

    start_lookup = parser.parse("Who is the patron", has_pending_approval=False)
    assert start_lookup.action == IntentAction.START_PATRON_LOOKUP

    lookup_query = parser.parse(
        "Riya Sharma",
        has_pending_approval=False,
        has_pending_patron_lookup=True,
    )
    assert lookup_query.action == IntentAction.PROVIDE_PATRON_LOOKUP
    assert lookup_query.patron_query == "Riya Sharma"

    select_patron = parser.parse(
        "PATRON_1",
        has_pending_approval=False,
        has_patron_candidates=True,
    )
    assert select_patron.action == IntentAction.SELECT_PATRON
    assert select_patron.patron_pseudonym == "PATRON_1"

    select_copy = parser.parse(
        "COPY_2",
        has_pending_approval=False,
        has_catalog_candidates=True,
    )
    assert select_copy.action == IntentAction.SELECT_CATALOG_COPY
    assert select_copy.copy_pseudonym == "COPY_2"

    select_loan = parser.parse(
        "LOAN_1",
        has_pending_approval=False,
        has_return_candidates=True,
    )
    assert select_loan.action == IntentAction.SELECT_RETURN_LOAN
    assert select_loan.loan_pseudonym == "LOAN_1"

    priya_issued = parser.parse(
        "Which books are issued to Priya?",
        has_pending_approval=False,
    )
    assert priya_issued.action == IntentAction.START_PATRON_DESK
    assert priya_issued.patron_query == "Priya"

    priya_borrowed = parser.parse(
        "What has Priya borrowed?",
        has_pending_approval=False,
    )
    assert priya_borrowed.action == IntentAction.START_PATRON_DESK
    assert priya_borrowed.patron_query == "Priya"

    checked_out = parser.parse(
        "What's checked out to Priya",
        has_pending_approval=False,
    )
    assert checked_out.action == IntentAction.START_PATRON_DESK
    assert checked_out.patron_query == "Priya"

    card_loans = parser.parse(
        "loans for CARD-12345",
        has_pending_approval=False,
    )
    assert card_loans.action == IntentAction.START_PATRON_DESK
    assert card_loans.card_barcode == "CARD-12345"

    pseudo_issued = parser.parse(
        "books issued to PATRON_1",
        has_pending_approval=False,
    )
    assert pseudo_issued.action == IntentAction.START_PATRON_DESK
    assert pseudo_issued.patron_pseudonym == "PATRON_1"

    show_loans = parser.parse(
        "show Priya Sharma loans",
        has_pending_approval=False,
    )
    assert show_loans.action == IntentAction.START_PATRON_DESK
    assert show_loans.patron_query == "Priya Sharma"

    return_decline = parser.parse(
        "cancel",
        has_pending_approval=False,
        has_guided_return_context=True,
    )
    assert return_decline.action == IntentAction.DECLINE_CONTINUE
