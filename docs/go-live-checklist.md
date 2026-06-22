# Go-live checklist — LMS-AI MVP

Sign-off against [plan-mvp.md §1.2](plan-mvp.md) success criteria (**G1–G13**) and [MVP.md §13](MVP.md) guardrails.

**Phases 0–7 verification:** `make phase7 && make ci-native`  
**Phase 8 (agent desk):** `make test-agent` then enable `AGENT_ISSUE_ENABLED` for pilot — see §Agent criteria below

---

## Product criteria (G1–G10)

| # | Criterion | Verify command / test | Status |
|---|-----------|----------------------|--------|
| **G1** | Journey steps 1–8 end-to-end | `pytest tests/e2e/test_api_journeys.py::test_mvp_circulation_journey` + `::test_mvp_journey_includes_search_and_overdue` | ☐ |
| **G2** | Concurrent checkout — one winner | `pytest tests/hardening/test_concurrency.py` | ☐ |
| **G3** | Idempotent checkout/return | `pytest tests/hardening/test_idempotency_regression.py` | ☐ |
| **G4** | RBAC + JWT enforced | `pytest tests/e2e/test_api_journeys.py -k auth` | ☐ |
| **G5** | SLO baselines (seed scale) | `pytest tests/performance/test_slo_baselines.py` | ☐ |
| **G6** | REQ-01–34 mapped to shipped code | [plan-mvp.md §5](plan-mvp.md) + code review | ☐ |
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
| `APP_SECRET_KEY` rotated for production | `.env` | ☐ |
| `APP_ENV=production` with explicit `CORS_ORIGINS` (not `*`) | `.env` | ☐ |
| `APP_DEBUG=false` in production | `.env` | ☐ |
| Health check monitored | `GET /health` | ☐ |
| Correlation id present on API responses | `X-Correlation-Id` | ☐ |
| Security headers on API responses | `X-Content-Type-Options`, `X-Frame-Options`, CSP | ☐ |
| Auth rate limiting active | `POST /api/v1/auth/token` → 429 after threshold | ☐ |
| Staff desk reachable | `/staff/` | ☐ |
| Sample seed loaded (pilot) | `make seed` | ☐ |

---

## Security hardening (MVP.md §13.7)

| Control | Verify command / check | Status |
|---------|------------------------|--------|
| bcrypt passwords (cost ≥ 12) | Code review `shared/auth/password.py` | ☐ |
| RBAC roles (ADMIN/LIBRARIAN/PATRON) | Code review `platform/auth/roles.py` | ☐ |
| JWT on all domain APIs | `pytest tests/e2e/test_api_journeys.py -k auth` | ☐ |
| Generic errors when not in debug | `pytest tests/hardening/test_security.py::test_unhandled_error_hides_internals` | ☐ |
| Production rejects default secret / wildcard CORS | `pytest tests/hardening/test_security.py -k production` | ☐ |
| Auth + API rate limits | `pytest tests/hardening/test_security.py::test_auth_rate_limit` | ☐ |
| Security response headers | `pytest tests/hardening/test_security.py::test_security_headers_on_health` | ☐ |
| npm supply-chain audit in CI | `.github/workflows/ci.yml` (`npm audit --audit-level=high`) | ☐ |
| HTTPS + HSTS at reverse proxy | `SECURITY_HSTS_ENABLED=true` only behind TLS | ☐ |

---

## Agent desk criteria (Phase 8 — G11–G13)

Requires [MVP.md §2.2](MVP.md), §13.8, and [research.md §15](research.md) (IMDA MGF v1.5 + Twelve-Factor). Enable with `AGENT_ISSUE_ENABLED=true`.

| # | Criterion | Verify command / check | Status |
|---|-----------|----------------------|--------|
| **G11** | Conversational circulation desk with HITL | `make test-agent` — guided issue, patron desk (issued books), return, catalog browse, patron lookup; friendly desk copy | ☐ |
| **G12** | Agentic fulfillment transitions with HITL | `make test-agent` — delivery issue → transition with HITL | ☐ |
| **G13** | IMDA agent charter + observability + Twelve-Factor ops | Charter signed; Langfuse traces with redacted args; config in env only; adversarial tests | ☐ |

### Agent operational readiness (MVP.md §13.8)

| Item | Reference | Status |
|------|-----------|--------|
| Provider API key(s) set (not in git) | [runbook.md §10](runbook.md) — `GROQ_API_KEY` and/or `LLM_PROVIDERS` chain | ☐ |
| `AGENT_MOCK_LLM=false` tested in staging (if using live LLM) | `.env` | ☐ |
| `AGENT_ISSUE_ENABLED` intentional for pilot | `.env` | ☐ |
| Enterprise agent charter signed | [research.md §15.2](research.md) | ☐ |
| Langfuse keys configured (`LANGFUSE_*`) | [runbook.md §10](runbook.md) | ☐ |
| Staff UI shows AI transparency + approval cards | MVP.md §2.2; UI renders backend `assistant_message` verbatim | ☐ |
| Wizard mode still passes G7–G10 with agent enabled | Regression E2E | ☐ |
| HF / Together fallback provider pinned (if enabled) | ADR-028; prefer `LLM_PROVIDERS` chain | ☐ |
| Residual risk (PII to hosted LLM provider(s)) accepted in writing | Charter | ☐ |
| `make ci-native` green on release candidate | Build/test gate before deploy (Twelve-Factor V) | ☐ |
| Migrations applied before agent run (not via agent tools) | `make migrate` (Twelve-Factor XII) | ☐ |
| Logs aggregated from stdout (not container log files only) | Ops / school IT log pipeline | ☐ |
| Same agent code path in staging and prod (mock LLM off in staging only via config) | Twelve-Factor X | ☐ |
| Single API worker per desk (in-process session store) or durable store deployed | [research.md §15.10](research.md) | ☐ |
| Production rejects default DB URL and mock LLM when agent enabled | `Settings.validate_production_security()` | ☐ |

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
| 7 | G2, G3, G5 | hardening + performance + `test_security.py` |
| 8 | REQ-31–34, G11–G13 | `make test-agent` (mocked LLM) + charter + Langfuse (G13) |

---

## Sign-off

| Role | Name | Date |
|------|------|------|
| Engineering | | |
| Library operations | | |
| School IT | | |

**Notes:**
