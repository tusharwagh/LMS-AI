"""SLO baseline checks at seed-data scale (MVP.md §13.1, G5)."""

from __future__ import annotations

import statistics
import time
import uuid

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.performance, pytest.mark.e2e]

# MVP.md §13.1
SLO_CIRCULATION_WRITE_MS = 1200
SLO_STAFF_READ_MS = 1500
WARMUP_ITERATIONS = 3
MEASURED_ITERATIONS = 20


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _p95_ms(samples_ms: list[float]) -> float:
    if not samples_ms:
        return 0.0
    ordered = sorted(samples_ms)
    index = max(0, int(len(ordered) * 0.95) - 1)
    return ordered[index]


def _timed_ms(fn) -> float:
    start = time.perf_counter()
    fn()
    return (time.perf_counter() - start) * 1000


@pytest.fixture
def slo_fixture(client: TestClient, admin_headers: dict[str, str]) -> dict:
    tag = _uid()
    rule_id = client.post(
        "/api/v1/loan/loan-rule-sets",
        json={"name": f"SLO {tag}", "max_active_loans": 5, "loan_period_days": 14},
        headers=admin_headers,
    ).json()["id"]
    ptype_id = client.post(
        "/api/v1/reference/patron-types",
        json={"code": f"SLO_{tag}", "name": "Student", "loan_rule_set_id": rule_id},
        headers=admin_headers,
    ).json()["id"]
    patron_id = client.post(
        "/api/v1/reference/patrons",
        json={"display_name": f"SLO Patron {tag}", "patron_type_id": ptype_id},
    ).json()["id"]
    cat_id = client.post(
        "/api/v1/catalog/catalogs",
        json={"title": f"SLO Title {tag}", "language": "en", "isbn": f"978{tag[:7]}"},
    ).json()["id"]
    client.post(f"/api/v1/catalog/catalogs/{cat_id}/publish")
    holding_ids: list[str] = []
    for i in range(MEASURED_ITERATIONS + WARMUP_ITERATIONS + 2):
        holding_ids.append(
            client.post(
                f"/api/v1/catalog/catalogs/{cat_id}/holdings",
                json={
                    "barcode": f"SLO-{tag}-{i}",
                    "accession_number": f"SLOACC-{tag}-{i}",
                },
            ).json()["id"]
        )
    return {
        "tag": tag,
        "patron_id": patron_id,
        "holding_ids": holding_ids,
        "search_q": f"SLO Title {tag}",
    }


def test_checkout_return_p95_within_slo(client: TestClient, slo_fixture: dict) -> None:
    """Checkout and return p95 <= 1200 ms at §13.6 seed scale."""
    patron_id = slo_fixture["patron_id"]
    samples: list[float] = []
    idx = 0

    for _ in range(WARMUP_ITERATIONS):
        holding_id = slo_fixture["holding_ids"][idx]
        idx += 1
        key = f"slo-warm-{slo_fixture['tag']}-{idx}"
        client.post(
            "/api/v1/loan/checkouts",
            json={"patron_id": patron_id, "holding_id": holding_id},
            headers={"Idempotency-Key": key},
        )
        client.post(
            "/api/v1/loan/returns",
            json={"holding_id": holding_id},
            headers={"Idempotency-Key": f"ret-{key}"},
        )

    for _ in range(MEASURED_ITERATIONS):
        holding_id = slo_fixture["holding_ids"][idx]
        idx += 1
        key = f"slo-{slo_fixture['tag']}-{idx}"
        samples.append(
            _timed_ms(
                lambda hid=holding_id, k=key: client.post(
                    "/api/v1/loan/checkouts",
                    json={"patron_id": patron_id, "holding_id": hid},
                    headers={"Idempotency-Key": k},
                )
            )
        )
        samples.append(
            _timed_ms(
                lambda hid=holding_id, k=key: client.post(
                    "/api/v1/loan/returns",
                    json={"holding_id": hid},
                    headers={"Idempotency-Key": f"ret-{k}"},
                )
            )
        )

    p95 = _p95_ms(samples)
    assert p95 <= SLO_CIRCULATION_WRITE_MS, (
        f"circulation write p95 {p95:.1f}ms exceeds SLO {SLO_CIRCULATION_WRITE_MS}ms "
        f"(median={statistics.median(samples):.1f}ms, n={len(samples)})"
    )


def test_staff_search_p95_within_slo(client: TestClient, slo_fixture: dict) -> None:
    """Staff lendable search and overdue list p95 <= 1500 ms."""
    samples: list[float] = []

    for _ in range(WARMUP_ITERATIONS):
        client.get(
            "/api/v1/catalog/catalogs/search/lendable",
            params={"q": slo_fixture["search_q"]},
        )
        client.get("/api/v1/loan/loans/overdue")

    for _ in range(MEASURED_ITERATIONS):
        samples.append(
            _timed_ms(
                lambda: client.get(
                    "/api/v1/catalog/catalogs/search/lendable",
                    params={"q": slo_fixture["search_q"]},
                )
            )
        )
        samples.append(_timed_ms(lambda: client.get("/api/v1/loan/loans/overdue")))

    p95 = _p95_ms(samples)
    assert p95 <= SLO_STAFF_READ_MS, (
        f"staff read p95 {p95:.1f}ms exceeds SLO {SLO_STAFF_READ_MS}ms "
        f"(median={statistics.median(samples):.1f}ms, n={len(samples)})"
    )
