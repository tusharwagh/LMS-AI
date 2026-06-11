"""E2E tests for staff desk workflows (G7, G8, G9, G10)."""

import uuid

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.e2e


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _seed_circulation_fixture(client: TestClient, admin_headers: dict[str, str], tag: str) -> dict:
    rule_id = client.post(
        "/api/v1/loan/loan-rule-sets",
        json={"name": f"Rule {tag}", "max_active_loans": 2, "loan_period_days": 14},
        headers=admin_headers,
    ).json()["id"]
    patron_type_id = client.post(
        "/api/v1/reference/patron-types",
        json={"code": f"STU_{tag}", "name": "Student", "loan_rule_set_id": rule_id},
        headers=admin_headers,
    ).json()["id"]
    patron_id = client.post(
        "/api/v1/reference/patrons",
        json={
            "display_name": f"Patron {tag}",
            "patron_type_id": patron_type_id,
            "card_barcode": f"CARD-{tag}",
            "external_ref": f"ADM-{tag}",
        },
    ).json()["id"]
    catalog_id = client.post(
        "/api/v1/catalog/catalogs",
        json={"title": f"Workflow Book {tag}", "language": "en"},
    ).json()["id"]
    client.post(f"/api/v1/catalog/catalogs/{catalog_id}/publish")
    holding_id = client.post(
        f"/api/v1/catalog/catalogs/{catalog_id}/holdings",
        json={"barcode": f"BC-{tag}", "accession_number": f"ACC-{tag}"},
    ).json()["id"]
    return {
        "patron_id": patron_id,
        "catalog_id": catalog_id,
        "holding_id": holding_id,
        "barcode": f"BC-{tag}",
        "card": f"CARD-{tag}",
        "tag": tag,
    }


def test_workflow_desk_issue_and_return(client: TestClient, admin_headers: dict[str, str]) -> None:
    """G7 + G8 — full desk issue/return via workflow APIs."""
    tag = _uid()
    fx = _seed_circulation_fixture(client, admin_headers, tag)

    start = client.post(
        "/api/v1/workflows/issue/start",
        json={"card_barcode": fx["card"], "search_query": f"Workflow Book {tag}"},
    )
    assert start.status_code == 200, start.text
    body = start.json()
    assert body["patron_id"] == fx["patron_id"]
    assert body["patron_validation"]["is_valid"] is True
    assert len(body["search_results"]) >= 1
    assert any(
        c["holding_id"] == fx["holding_id"]
        for hit in body["search_results"]
        for c in hit["lendable_copies"]
    )

    commit = client.post(
        "/api/v1/workflows/issue/commit",
        json={
            "patron_id": fx["patron_id"],
            "holding_id": fx["holding_id"],
            "fulfillment_mode": "DESK",
        },
        headers={"Idempotency-Key": f"wf-issue-{tag}"},
    )
    assert commit.status_code == 201, commit.text
    loan_id = commit.json()["loan_id"]
    assert commit.json()["fulfillment"] is None

    open_loans = client.get("/api/v1/loan/loans/open", params={"patron_id": fx["patron_id"]}).json()
    assert len(open_loans) == 1
    assert open_loans[0]["id"] == loan_id

    ret_start = client.post(
        "/api/v1/workflows/return/start",
        json={"barcode": fx["barcode"]},
    )
    assert ret_start.status_code == 200
    assert ret_start.json()["loan_id"] == loan_id

    ret_commit = client.post(
        "/api/v1/workflows/return/commit",
        json={"barcode": fx["barcode"]},
        headers={"Idempotency-Key": f"wf-return-{tag}"},
    )
    assert ret_commit.status_code == 200
    assert ret_commit.json()["returned_at"] is not None
    assert (
        client.get(f"/api/v1/catalog/holdings/by-barcode/{fx['barcode']}").json()["holding_status"]
        == "AVAILABLE"
    )


def test_workflow_validation_report_multiple_violations(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """G10 — blocked patron + unavailable holding surfaces multiple rule_ids."""
    tag = _uid()
    fx = _seed_circulation_fixture(client, admin_headers, tag)

    client.post(
        f"/api/v1/reference/patrons/{fx['patron_id']}/blocks",
        json={"reason_code": "TEST", "start_at": "2026-01-01T00:00:00Z"},
    )

    catalog2 = client.post(
        "/api/v1/catalog/catalogs",
        json={"title": f"Second {tag}"},
    ).json()["id"]
    holding2 = client.post(
        f"/api/v1/catalog/catalogs/{catalog2}/holdings",
        json={"barcode": f"BC2-{tag}", "accession_number": f"ACC2-{tag}"},
    ).json()["id"]

    report = client.post(
        "/api/v1/workflows/issue/validate",
        json={"patron_id": fx["patron_id"], "holding_id": holding2},
    )
    assert report.status_code == 200
    violations = report.json()["violations"]
    rule_ids = {v["rule_id"] for v in violations}
    assert "REF-B2" in rule_ids
    assert "XCAT-1" in rule_ids or "CAT-5" in rule_ids
    assert report.json()["is_valid"] is False


def test_workflow_delivery_issue_and_pickup_return(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """G9 — delivery issue fulfillment + two-phase pick-up return."""
    tag = _uid()
    fx = _seed_circulation_fixture(client, admin_headers, tag)

    issue = client.post(
        "/api/v1/workflows/issue/commit",
        json={
            "patron_id": fx["patron_id"],
            "holding_id": fx["holding_id"],
            "fulfillment_mode": "DELIVERY",
            "destination": {"notes": "Class 7A room", "contact": "9876543210"},
        },
        headers={"Idempotency-Key": f"del-issue-{tag}"},
    )
    assert issue.status_code == 201, issue.text
    loan_id = issue.json()["loan_id"]
    fulfillment_id = issue.json()["fulfillment"]["id"]
    assert issue.json()["fulfillment"]["status"] == "REQUESTED"

    complete = client.post(
        f"/api/v1/workflows/fulfillment/{fulfillment_id}/transition",
        json={"status": "COMPLETED"},
    )
    assert complete.status_code == 422

    ready = client.post(
        f"/api/v1/workflows/fulfillment/{fulfillment_id}/transition",
        json={"status": "READY"},
    )
    assert ready.status_code == 200
    done = client.post(
        f"/api/v1/workflows/fulfillment/{fulfillment_id}/transition",
        json={"status": "COMPLETED"},
    )
    assert done.status_code == 200
    assert done.json()["status"] == "COMPLETED"

    open_loans = client.get("/api/v1/loan/loans/open", params={"patron_id": fx["patron_id"]}).json()
    assert len(open_loans) == 1
    assert open_loans[0]["id"] == loan_id

    pickup = client.post(
        "/api/v1/workflows/return/pickup/initiate",
        json={"loan_id": loan_id, "destination": {"notes": "Collect from home"}},
    )
    assert pickup.status_code == 201
    pickup_id = pickup.json()["id"]
    assert pickup.json()["status"] == "REQUESTED"

    still_open = client.get("/api/v1/loan/loans/open", params={"patron_id": fx["patron_id"]}).json()
    assert len(still_open) == 1

    confirm = client.post(
        "/api/v1/workflows/return/pickup/confirm",
        json={"fulfillment_id": pickup_id},
        headers={"Idempotency-Key": f"pickup-{tag}"},
    )
    assert confirm.status_code == 200
    assert confirm.json()["returned_at"] is not None
    assert (
        client.get(f"/api/v1/catalog/holdings/by-barcode/{fx['barcode']}").json()["holding_status"]
        == "AVAILABLE"
    )


def test_lendable_search_excludes_draft_and_on_loan(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    tag = _uid()
    fx = _seed_circulation_fixture(client, admin_headers, tag)

    draft_id = client.post(
        "/api/v1/catalog/catalogs",
        json={"title": f"DraftOnly{tag}"},
    ).json()["id"]
    client.post(
        f"/api/v1/catalog/catalogs/{draft_id}/holdings",
        json={"barcode": f"DRAFT-{tag}", "accession_number": f"DRAFTACC-{tag}"},
    )

    client.post(
        "/api/v1/workflows/issue/commit",
        json={
            "patron_id": fx["patron_id"],
            "holding_id": fx["holding_id"],
            "fulfillment_mode": "DESK",
        },
        headers={"Idempotency-Key": f"lendable-{tag}"},
    )

    hits = client.get(
        "/api/v1/catalog/catalogs/search/lendable",
        params={"q": f"Workflow Book {tag}"},
    )
    assert hits.status_code == 200
    assert hits.json() == []


def test_workflow_issue_search_patron_by_name(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    tag = _uid()
    fx = _seed_circulation_fixture(client, admin_headers, tag)

    search = client.post(
        "/api/v1/workflows/issue/search-patrons",
        json={"display_name": f"Patron {tag}"},
    )
    assert search.status_code == 200
    assert len(search.json()["patrons"]) == 1
    assert search.json()["patrons"][0]["id"] == fx["patron_id"]

    start = client.post(
        "/api/v1/workflows/issue/start",
        json={"display_name": f"Patron {tag}"},
    )
    assert start.status_code == 200
    assert start.json()["patron_id"] == fx["patron_id"]


def test_workflow_issue_back_and_cancel(client: TestClient, admin_headers: dict[str, str]) -> None:
    tag = _uid()
    fx = _seed_circulation_fixture(client, admin_headers, tag)

    back = client.post("/api/v1/workflows/issue/back", json={"target_step": 2})
    assert back.status_code == 200
    assert back.json()["allowed"] is True

    commit = client.post(
        "/api/v1/workflows/issue/commit",
        json={
            "patron_id": fx["patron_id"],
            "holding_id": fx["holding_id"],
            "fulfillment_mode": "DESK",
        },
        headers={"Idempotency-Key": f"cancel-test-{tag}"},
    )
    assert commit.status_code == 201
    loan_id = commit.json()["loan_id"]

    blocked_back = client.post(
        "/api/v1/workflows/issue/back",
        json={"target_step": 2, "loan_id": loan_id},
    )
    assert blocked_back.status_code == 422

    cancel = client.post(
        "/api/v1/workflows/issue/cancel",
        json={"loan_id": loan_id},
        headers={"Idempotency-Key": f"cancel-{tag}"},
    )
    assert cancel.status_code == 200
    assert cancel.json()["returned_at"] is not None
    assert (
        client.get(f"/api/v1/catalog/holdings/by-barcode/{fx['barcode']}").json()["holding_status"]
        == "AVAILABLE"
    )


def test_workflow_issue_cancel_with_delivery_fulfillment(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    tag = _uid()
    fx = _seed_circulation_fixture(client, admin_headers, tag)

    commit = client.post(
        "/api/v1/workflows/issue/commit",
        json={
            "patron_id": fx["patron_id"],
            "holding_id": fx["holding_id"],
            "fulfillment_mode": "DELIVERY",
            "destination": {"notes": "Room 12"},
        },
        headers={"Idempotency-Key": f"del-cancel-{tag}"},
    )
    assert commit.status_code == 201
    loan_id = commit.json()["loan_id"]

    cancel = client.post(
        "/api/v1/workflows/issue/cancel",
        json={"loan_id": loan_id},
        headers={"Idempotency-Key": f"del-cancel-ret-{tag}"},
    )
    assert cancel.status_code == 200
    assert cancel.json()["fulfillment_cancelled"] is True

    draft_hits = client.get(
        "/api/v1/catalog/catalogs/search/lendable",
        params={"q": f"DraftOnly{tag}"},
    )
    assert draft_hits.json() == []
