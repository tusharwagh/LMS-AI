# LMS-AI — static & dynamic analysis

Supplement to [python-code-analysis/SKILL.md](../../generic/python-code-analysis/SKILL.md). Commands and paths for **this repository**.

---

## Tool configuration

| Tool | Config | Scope |
|------|--------|-------|
| Ruff | `pyproject.toml` `[tool.ruff]` | `E,F,I,UP,B`; line length 100; py312 |
| mypy | `pyproject.toml` `[tool.mypy]` | `strict = true`; packages `lms` |
| import-linter | `pyproject.toml` `[tool.importlinter]` | 4 contracts (reference, catalog, loan, agent) |
| pytest | `pyproject.toml` `[tool.pytest.ini_options]` | markers: unit, integration, e2e, hardening, performance, agent |

**CI** (`.github/workflows/ci.yml`): `ruff check`, `lint-imports`, `mypy`, `alembic upgrade head`, `pytest`, `npm audit`, diagram script.

---

## Makefile targets

```bash
make lint                 # ruff + lint-imports + mypy (strict)
make test                 # full pytest
make test-unit            # -m unit
make test-integration     # -m integration
make test-e2e             # -m e2e
make test-agent           # AGENT_ISSUE_ENABLED + AGENT_MOCK_LLM
make test-hardening       # -m hardening
make test-performance     # -m performance
make phase7               # hardening + performance
make phase8               # agent tests
make ci-native            # lint + all pytest suites (no Docker)
```

Prerequisites: `make install` (venv + dev deps). DB tests need Postgres and `DATABASE_URL` in `.env`.

---

## Recommended pre-PR command sequence

```bash
make lint
PYTHONPATH=src .venv/bin/mypy
make migrate              # if schema changed or fresh DB
make ci-native            # or narrower: test-unit + affected markers
```

Touching `lms/agent/`: include `make test-agent` or `make phase8`.

**Agent desk copy (`messages.py`):** after changing staff-facing strings, intent routing, or slot guard messages, run:

```bash
make test-agent
pytest tests/agent/test_intent_and_masking.py -v
```

Assert: intent-specific guard text, query echo, CHAT vs patron-search routing, no technical jargon in success messages (`test_issue_committed_is_friendly_not_technical`).

**Agent slot guards:** after changing `IssueTools` prerequisite helpers (`_patron_id`, `_holding_id`, `_patron_and_holding`), run `make test-agent` and confirm union-return messages match each guard (patron-first, then holding).

Touching circulation writes / auth / middleware: include `make test-hardening` and `pytest tests/hardening/test_security.py`.

---

## import-linter contracts

| Contract | Source | Forbidden |
|----------|--------|-----------|
| Reference must not import Catalog or Loan infrastructure | `lms.reference` | `catalog.infrastructure`, `loan.infrastructure` |
| Catalog must not import Reference or Loan infrastructure | `lms.catalog` | `reference.infrastructure`, `loan.infrastructure` |
| Loan must not import Reference or Catalog infrastructure | `lms.loan` | `reference.infrastructure`, `catalog.infrastructure` |
| Agent must not import domain infrastructure | `lms.agent` | all three `*.infrastructure` (narrow ignore list in pyproject) |

Failure = architectural defect — fix ports/adapters/workflows per [clean-code-ddd-lms-ai](../clean-code-ddd-lms-ai/SKILL.md).

---

## Test layout

| Directory | Marker | Examples |
|-----------|--------|----------|
| `tests/unit/` | `unit` | health, auth helpers |
| `tests/integration/` | `integration` | orchestrator, domain services |
| `tests/e2e/` | `e2e` | API journeys, staff UI smoke, workflows |
| `tests/hardening/` | `hardening` | concurrency, idempotency, security |
| `tests/performance/` | `performance` | SLO baselines |
| `tests/agent/` | `agent` | coordinator, tools, intent, graph |

Shared fixtures: `tests/conftest.py` — DB seed skipped for unit/smoke via `bare_client`.

---

## Dynamic analysis by change type

| Change | Minimum dynamic scope |
|--------|------------------------|
| Domain rule / validation | unit + integration |
| New REST route | e2e + RBAC denial case |
| Workflow step | `tests/e2e/test_workflow_issue_return.py` or return counterpart |
| Circulation write path | hardening idempotency + concurrency if touching checkout |
| Security middleware / errors | `tests/hardening/test_security.py` |
| Agent tool or coordinator | `tests/agent/` with `AGENT_MOCK_LLM=true` |
| Agent desk copy (`messages.py`) | `tests/agent/test_intent_and_masking.py` + `make test-agent` |
| Staff UI only | `tests/e2e/test_staff_ui.py` |

---

## SLO targets (performance marker)

| Class | p95 target | Test |
|-------|------------|------|
| Checkout / return | ≤ 1200 ms | `test_checkout_return_p95_within_slo` |
| Staff search / overdue | ≤ 1500 ms | `test_staff_search_p95_within_slo` |

---

## Cross-references

| Topic | Path |
|-------|------|
| Security tests & headers | `.cursor/rules/generic/security-and-hardening.md` + `.cursor/rules/lms-ai/security-and-hardening-lms-ai.md` |
| Go-live test matrix | `docs/go-live-checklist.md` |
| Agent governance tests (G11–G13) | `.cursor/skills/generic/imda-agentic-ai-governance/SKILL.md` |
| DDD boundaries | `.cursor/skills/lms-ai/clean-code-ddd-lms-ai/SKILL.md` |
| SonarQube quality rules | `.cursor/rules/generic/sonarqube-quality.md` + `.cursor/rules/lms-ai/sonarqube-quality-lms-ai.md` |
