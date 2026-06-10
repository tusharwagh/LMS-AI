# Go-live checklist — LMS-AI MVP

Sign-off against [plan-mvp.md §1.2](plan-mvp.md) success criteria (G1–G10) and [MVP.md §13](MVP.md) guardrails.

**Run verification:** `make phase7 && make ci-native`

---

## Product criteria (G1–G10)

| # | Criterion | Verify command / test | Status |
|---|-----------|----------------------|--------|
| **G1** | Journey steps 1–8 end-to-end | `pytest tests/e2e/test_api_journeys.py::test_mvp_circulation_journey` + `::test_mvp_journey_includes_search_and_overdue` | ☐ |
| **G2** | Concurrent checkout — one winner | `pytest tests/hardening/test_concurrency.py` | ☐ |
| **G3** | Idempotent checkout/return | `pytest tests/hardening/test_idempotency_regression.py` | ☐ |
| **G4** | RBAC + JWT enforced | `pytest tests/e2e/test_api_journeys.py -k auth` | ☐ |
| **G5** | SLO baselines (seed scale) | `pytest tests/performance/test_slo_baselines.py` | ☐ |
| **G6** | REQ-01–30 mapped to shipped code | [plan-mvp.md §5](plan-mvp.md) + code review | ☐ |
| **G7** | WF-01 desk issue | `pytest tests/e2e/test_workflow_issue_return.py::test_workflow_desk_issue_and_return` | ☐ |
| **G8** | WF-02 desk return | `pytest tests/e2e/test_workflow_issue_return.py -k return` | ☐ |
| **G9** | Delivery + pick-up paths | `pytest tests/e2e/test_workflow_issue_return.py -k delivery` | ☐ |
| **G10** | ValidationReport multi-violation | `pytest tests/e2e/test_workflow_issue_return.py::test_workflow_validation_report_multiple_violations` | ☐ |

---

## Operational readiness (MVP.md §13)

| Item | Reference | Status |
|------|-----------|--------|
| Migrations applied (`alembic upgrade head`) | [runbook.md §3](runbook.md) | ☐ |
| Backup procedure documented and tested | [runbook.md §4](runbook.md) | ☐ |
| Default passwords changed | [runbook.md §9](runbook.md) | ☐ |
| `JWT_SECRET` rotated for production | `.env` | ☐ |
| Health check monitored | `GET /health` | ☐ |
| Correlation id present on API responses | `X-Correlation-Id` | ☐ |
| Staff desk reachable | `/staff/` | ☐ |
| Sample seed loaded (pilot) | `make seed` | ☐ |

---

## SLO targets (§13.1, validated at seed scale)

| Endpoint class | p95 target | Test |
|----------------|------------|------|
| Checkout / return | ≤ 1200 ms | `test_checkout_return_p95_within_slo` |
| Staff search / overdue | ≤ 1500 ms | `test_staff_search_p95_within_slo` |

If production load exceeds [MVP.md §13.6](MVP.md) baselines (100k catalogs, 250k holdings, 25 concurrent desk users), re-run performance tests and revise SLOs before rollout.

---

## REQ traceability quick reference

| Phase | REQs | Verified by |
|-------|------|-------------|
| 0 | REQ-01, 21, 30 | import-linter, auth e2e |
| 1–3 | REQ-03–11 | integration + e2e |
| 4 | REQ-13, 14, 17, 18, 22–24 | orchestrator + hardening |
| 5 | REQ-10, 15, 19, 20, 25 | e2e search/overdue |
| 5A | REQ-26, 27, 29 | workflow e2e |
| 5B | REQ-28 | delivery e2e |
| 6 | — | `test_staff_ui.py` |
| 7 | G2, G3, G5 | hardening + performance |

---

## Sign-off

| Role | Name | Date |
|------|------|------|
| Engineering | | |
| Library operations | | |
| School IT | | |

**Notes:**
