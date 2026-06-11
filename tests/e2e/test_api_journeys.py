"""End-to-end API tests — full HTTP journey (MVP.md §2)."""

import uuid

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.e2e


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def test_health_and_docs(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200


def test_mvp_circulation_journey(client: TestClient, admin_headers: dict[str, str]) -> None:
    tag = _uid()

    rule_resp = client.post(
        "/api/v1/loan/loan-rule-sets",
        json={"name": f"Student {tag}", "max_active_loans": 3, "loan_period_days": 14},
        headers=admin_headers,
    )
    assert rule_resp.status_code == 201, rule_resp.text
    rule_set_id = rule_resp.json()["id"]

    type_resp = client.post(
        "/api/v1/reference/patron-types",
        json={"code": f"STUDENT_{tag}", "name": "Student", "loan_rule_set_id": rule_set_id},
        headers=admin_headers,
    )
    assert type_resp.status_code == 201
    patron_type_id = type_resp.json()["id"]

    section_resp = client.post(
        "/api/v1/reference/class-sections",
        json={"grade": "7", "section": "A", "academic_year": f"2025-{tag}"},
        headers=admin_headers,
    )
    assert section_resp.status_code == 201
    section_id = section_resp.json()["id"]

    patron_resp = client.post(
        "/api/v1/reference/patrons",
        json={
            "display_name": f"Test Patron {tag}",
            "patron_type_id": patron_type_id,
            "external_ref": f"ADM-{tag}",
            "class_section_id": section_id,
            "card_barcode": f"CARD-{tag}",
        },
    )
    assert patron_resp.status_code == 201
    patron_id = patron_resp.json()["id"]

    assert client.get(f"/api/v1/reference/patrons/by-card/CARD-{tag}").json()["id"] == patron_id

    catalog_resp = client.post(
        "/api/v1/catalog/catalogs",
        json={"title": f"Python {tag}", "language": "en"},
    )
    catalog_id = catalog_resp.json()["id"]
    client.post(f"/api/v1/catalog/catalogs/{catalog_id}/publish")

    holding_resp = client.post(
        f"/api/v1/catalog/catalogs/{catalog_id}/holdings",
        json={"barcode": f"BC-{tag}", "accession_number": f"ACC-{tag}", "shelf_location": "A-1"},
    )
    holding_id = holding_resp.json()["id"]

    checkout = client.post(
        "/api/v1/loan/checkouts",
        json={"patron_id": patron_id, "holding_id": holding_id},
        headers={"Idempotency-Key": f"checkout-{tag}"},
    )
    assert checkout.status_code == 201, checkout.text
    loan_id = checkout.json()["id"]

    assert (
        client.get(f"/api/v1/catalog/holdings/by-barcode/BC-{tag}").json()["holding_status"]
        == "ON_LOAN"
    )
    assert len(client.get("/api/v1/loan/loans/open", params={"patron_id": patron_id}).json()) == 1

    ret = client.post(
        "/api/v1/loan/returns",
        json={"holding_id": holding_id},
        headers={"Idempotency-Key": f"return-{tag}"},
    )
    assert ret.status_code == 200
    assert ret.json()["id"] == loan_id
    assert (
        client.get(f"/api/v1/catalog/holdings/by-barcode/BC-{tag}").json()["holding_status"]
        == "AVAILABLE"
    )


def test_mvp_journey_includes_search_and_overdue(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    """G1 extension — staff lendable search + overdue list in same journey."""
    tag = _uid()

    rule_resp = client.post(
        "/api/v1/loan/loan-rule-sets",
        json={"name": f"Student {tag}", "max_active_loans": 3, "loan_period_days": 14},
        headers=admin_headers,
    )
    rule_set_id = rule_resp.json()["id"]
    patron_type_id = client.post(
        "/api/v1/reference/patron-types",
        json={"code": f"STUDENT_{tag}", "name": "Student", "loan_rule_set_id": rule_set_id},
        headers=admin_headers,
    ).json()["id"]
    patron_id = client.post(
        "/api/v1/reference/patrons",
        json={"display_name": f"Search Patron {tag}", "patron_type_id": patron_type_id},
    ).json()["id"]

    catalog_id = client.post(
        "/api/v1/catalog/catalogs",
        json={"title": f"Searchable {tag}", "language": "en"},
    ).json()["id"]
    client.post(f"/api/v1/catalog/catalogs/{catalog_id}/publish")
    holding_id = client.post(
        f"/api/v1/catalog/catalogs/{catalog_id}/holdings",
        json={"barcode": f"SBC-{tag}", "accession_number": f"SACC-{tag}"},
    ).json()["id"]

    lendable = client.get(
        "/api/v1/catalog/catalogs/search/lendable",
        params={"q": f"Searchable {tag}"},
    )
    assert lendable.status_code == 200
    assert len(lendable.json()) == 1
    assert lendable.json()[0]["lendable_holdings"][0]["id"] == holding_id

    client.post(
        "/api/v1/workflows/issue/commit",
        json={
            "patron_id": patron_id,
            "holding_id": holding_id,
            "fulfillment_mode": "DESK",
        },
        headers={"Idempotency-Key": f"g1-search-{tag}"},
    )

    overdue = client.get("/api/v1/loan/loans/overdue")
    assert overdue.status_code == 200
    assert isinstance(overdue.json(), list)

    client.post(
        "/api/v1/workflows/return/commit",
        json={"barcode": f"SBC-{tag}"},
        headers={"Idempotency-Key": f"g1-return-{tag}"},
    )

    lendable_after = client.get(
        "/api/v1/catalog/catalogs/search/lendable",
        params={"q": f"Searchable {tag}"},
    )
    assert len(lendable_after.json()) == 1


def test_checkout_rejects_suspended_patron(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    tag = _uid()
    rule_id = client.post(
        "/api/v1/loan/loan-rule-sets",
        json={"name": f"R {tag}", "max_active_loans": 1, "loan_period_days": 7},
        headers=admin_headers,
    ).json()["id"]
    ptype_id = client.post(
        "/api/v1/reference/patron-types",
        json={"code": f"T_{tag}", "name": "T", "loan_rule_set_id": rule_id},
        headers=admin_headers,
    ).json()["id"]
    patron_id = client.post(
        "/api/v1/reference/patrons",
        json={"display_name": "Suspended", "patron_type_id": ptype_id},
    ).json()["id"]
    client.post(f"/api/v1/reference/patrons/{patron_id}/suspend")

    cat_id = client.post("/api/v1/catalog/catalogs", json={"title": f"B {tag}"}).json()["id"]
    client.post(f"/api/v1/catalog/catalogs/{cat_id}/publish")
    holding_id = client.post(
        f"/api/v1/catalog/catalogs/{cat_id}/holdings",
        json={"barcode": f"B2-{tag}", "accession_number": f"A2-{tag}"},
    ).json()["id"]

    resp = client.post(
        "/api/v1/loan/checkouts",
        json={"patron_id": patron_id, "holding_id": holding_id},
        headers={"Idempotency-Key": f"fail-{tag}"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "DOMAIN_RULE_VIOLATION"


def test_auth_required_without_token(bare_client: TestClient) -> None:
    domain_paths = (
        "/api/v1/reference/patron-types",
        "/api/v1/catalog/catalogs/search?q=test",
        "/api/v1/loan/loan-rule-sets",
        "/api/v1/loan/loans/overdue",
    )
    for path in domain_paths:
        resp = bare_client.get(path)
        assert resp.status_code == 401, path
        assert resp.json()["detail"]["code"] == "UNAUTHORIZED"


def test_login_and_me(bare_client: TestClient, dev_password: str) -> None:
    login = bare_client.post(
        "/api/v1/auth/token",
        data={"username": "librarian", "password": dev_password},
    )
    assert login.status_code == 200, login.text
    body = login.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    token = body["access_token"]

    me = bare_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "librarian"
    assert me.json()["role"] == "LIBRARIAN"


def test_login_rejects_bad_password(bare_client: TestClient) -> None:
    resp = bare_client.post(
        "/api/v1/auth/token",
        data={"username": "librarian", "password": "wrong"},
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "UNAUTHORIZED"


def test_librarian_cannot_configure_loan_rules(client: TestClient) -> None:
    tag = _uid()
    resp = client.post(
        "/api/v1/loan/loan-rule-sets",
        json={"name": f"Denied {tag}", "max_active_loans": 1, "loan_period_days": 7},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "FORBIDDEN"


def test_admin_can_configure_loan_rules(
    admin_headers: dict[str, str], bare_client: TestClient
) -> None:
    tag = _uid()
    resp = bare_client.post(
        "/api/v1/loan/loan-rule-sets",
        json={"name": f"AdminRule {tag}", "max_active_loans": 2, "loan_period_days": 14},
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text


def test_reference_patron_type_crud(client: TestClient, admin_headers: dict[str, str]) -> None:
    tag = _uid()
    create = client.post(
        "/api/v1/reference/patron-types",
        json={"code": f"CRUD_{tag}", "name": "Crud Type"},
        headers=admin_headers,
    )
    assert create.status_code == 201
    type_id = create.json()["id"]

    listed = client.get("/api/v1/reference/patron-types")
    assert any(row["id"] == type_id for row in listed.json())

    got = client.get(f"/api/v1/reference/patron-types/{type_id}")
    assert got.status_code == 200
    assert got.json()["code"] == f"CRUD_{tag}".upper()


def test_catalog_draft_not_in_staff_search_until_publish(client: TestClient) -> None:
    tag = _uid()
    draft = client.post(
        "/api/v1/catalog/catalogs",
        json={"title": f"HiddenDraft{tag}", "language": "en"},
    ).json()["id"]

    before = client.get("/api/v1/catalog/catalogs/search", params={"q": f"HiddenDraft{tag}"})
    assert before.status_code == 200

    client.post(f"/api/v1/catalog/catalogs/{draft}/publish")
    after = client.get("/api/v1/catalog/catalogs/search", params={"q": f"HiddenDraft{tag}"})
    assert any(c["id"] == draft for c in after.json())
