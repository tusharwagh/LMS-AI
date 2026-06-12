"""Idempotency regression — checkout/return HTTP replay (MVP.md §13.3, G3)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.hardening, pytest.mark.e2e]


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _seed_holding(client: TestClient, admin_headers: dict[str, str], tag: str) -> tuple[str, str]:
    rule_id = client.post(
        "/api/v1/loan/loan-rule-sets",
        json={"name": f"Idem {tag}", "max_active_loans": 2, "loan_period_days": 14},
        headers=admin_headers,
    ).json()["id"]
    ptype_id = client.post(
        "/api/v1/reference/patron-types",
        json={"code": f"ID_{tag}", "name": "Student", "loan_rule_set_id": rule_id},
        headers=admin_headers,
    ).json()["id"]
    patron_id = client.post(
        "/api/v1/reference/patrons",
        json={"display_name": f"Idem Patron {tag}", "patron_type_id": ptype_id},
    ).json()["id"]
    cat_id = client.post(
        "/api/v1/catalog/catalogs",
        json={"title": f"Idem Book {tag}", "language": "en"},
    ).json()["id"]
    client.post(f"/api/v1/catalog/catalogs/{cat_id}/publish")
    holding_id = client.post(
        f"/api/v1/catalog/catalogs/{cat_id}/holdings",
        json={"barcode": f"ID-{tag}", "accession_number": f"IA-{tag}"},
    ).json()["id"]
    return patron_id, holding_id


def test_checkout_idempotency_http_replay(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    tag = _uid()
    patron_id, holding_id = _seed_holding(client, admin_headers, tag)
    headers = {"Idempotency-Key": f"idem-chk-{tag}"}
    body = {"patron_id": patron_id, "holding_id": holding_id}

    first = client.post("/api/v1/loan/checkouts", json=body, headers=headers)
    second = client.post("/api/v1/loan/checkouts", json=body, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    open_loans = client.get("/api/v1/loan/loans/open", params={"patron_id": patron_id}).json()
    assert len(open_loans) == 1


def test_return_idempotency_http_replay(client: TestClient, admin_headers: dict[str, str]) -> None:
    tag = _uid()
    patron_id, holding_id = _seed_holding(client, admin_headers, tag)
    checkout_key = f"idem-ret-chk-{tag}"
    client.post(
        "/api/v1/loan/checkouts",
        json={"patron_id": patron_id, "holding_id": holding_id},
        headers={"Idempotency-Key": checkout_key},
    )

    return_headers = {"Idempotency-Key": f"idem-ret-{tag}"}
    body = {"holding_id": holding_id}
    first = client.post("/api/v1/loan/returns", json=body, headers=return_headers)
    second = client.post("/api/v1/loan/returns", json=body, headers=return_headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["returned_at"] is not None

    open_loans = client.get("/api/v1/loan/loans/open", params={"patron_id": patron_id}).json()
    assert open_loans == []


def test_checkout_idempotency_payload_mismatch_returns_409(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    tag = _uid()
    patron_id, holding_id = _seed_holding(client, admin_headers, tag)
    rule_id = client.get("/api/v1/loan/loan-rule-sets").json()[0]["id"]
    ptype_id = client.post(
        "/api/v1/reference/patron-types",
        json={"code": f"ID2_{tag}", "name": "Student", "loan_rule_set_id": rule_id},
        headers=admin_headers,
    ).json()["id"]
    other_patron_id = client.post(
        "/api/v1/reference/patrons",
        json={"display_name": f"Idem Patron 2 {tag}", "patron_type_id": ptype_id},
    ).json()["id"]

    headers = {"Idempotency-Key": f"idem-mismatch-{tag}"}
    first = client.post(
        "/api/v1/loan/checkouts",
        json={"patron_id": patron_id, "holding_id": holding_id},
        headers=headers,
    )
    assert first.status_code == 201
    client.post(
        "/api/v1/loan/returns",
        json={"holding_id": holding_id},
        headers={"Idempotency-Key": f"idem-ret-mismatch-{tag}"},
    )

    conflict = client.post(
        "/api/v1/loan/checkouts",
        json={"patron_id": other_patron_id, "holding_id": holding_id},
        headers=headers,
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "CONFLICT"


def test_workflow_commit_idempotency(client: TestClient, admin_headers: dict[str, str]) -> None:
    tag = _uid()
    patron_id, holding_id = _seed_holding(client, admin_headers, tag)
    headers = {"Idempotency-Key": f"wf-idem-{tag}"}
    body = {
        "patron_id": patron_id,
        "holding_id": holding_id,
        "fulfillment_mode": "DESK",
    }
    first = client.post("/api/v1/workflows/issue/commit", json=body, headers=headers)
    second = client.post("/api/v1/workflows/issue/commit", json=body, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["loan_id"] == second.json()["loan_id"]
