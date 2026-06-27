# AI SDLC Charter — LMS-AI

**Status:** Active  
**Model:** Option 1 — **AI assists humans** at each stage  
**Owner:** Repository maintainers

This charter governs AI-assisted software delivery for the K-12 library management monolith (FastAPI, React staff desk, optional LangGraph agent desk).

---

## 1. Purpose

Establish a repeatable, auditable process where:

- AI **accelerates** planning, design, implementation, verification, and shipping.
- Humans **own** merge, release, secrets, production config, and go-live sign-off.
- Every AI-assisted change batch is **recorded** in [CHANGELOG.md](CHANGELOG.md).

Aligned with runtime agent governance (IMDA MGF v1.5, HITL on writes) documented in [research.md §15](../research.md) and the [IMDA governance skill](../../.cursor/skills/generic/imda-agentic-ai-governance/SKILL.md).

---

## 2. Scope

| In scope | Out of scope (for now) |
|----------|-------------------------|
| `src/lms/**` bounded contexts, staff UI, agent desk | Autonomous merge/deploy without human approval |
| Alembic migrations, `tests/**`, Makefile/CI | AI changing production hosts or cloud IAM |
| `docs/**`, `.cursor/rules/**`, `.cursor/skills/**` | Committing `.env`, API keys, or patron PII |
| GitHub issues/PR drafts | AI as sole owner of go-live sign-off (G1–G13) |

---

## 3. Autonomy levels

| Level | Meaning | LMS-AI example |
|-------|---------|----------------|
| **A — Autonomous** | AI acts; human reviews via change log | Unit tests, changelog entry, ruff fixes |
| **Advise — Recommend** | AI proposes; human confirms before execution | New REST route, import-linter boundary change, agent tool |
| **Blocked — Human only** | AI must not execute | `git push`, `make deploy-*`, `.env` edits, `make ci-ship` commit |

### By SDLC stage

| Stage | AI may (A) | AI must advise (Advise) | Human only (Blocked) |
|-------|------------|-------------------------|----------------------|
| **Plan** | Draft issues, map to `REQ-XX` in [plan-mvp.md](../plan-mvp.md) | MVP scope change, new bounded context | Backlog priority |
| **Design** | Draft ADRs, mermaid diagrams (`make diagram`) | Cross-context port, new aggregate, agent tool | ADR approval |
| **Implement** | Handlers, workflows, UI, migrations, tests | Public API contract, RBAC, `lms/agent/` tools | — |
| **Verify** | `make lint`, `make test-agent`, `make ci-native`; draft review | Security/hardening findings | Merge approval |
| **Ship** | PR body, release notes draft | Alembic on shared DB | Push, deploy, [go-live checklist](../go-live-checklist.md) |

**Non-trivial decisions:** apply [doubt-driven-development](../../.cursor/rules/generic/doubt-driven-development.md) before standing (cross-boundary, security, irreversible ops).

---

## 4. Human gates

| Action | Owner | Reference |
|--------|-------|-----------|
| Merge to `main` | Human | CI: [.github/workflows/ci.yml](../../.github/workflows/ci.yml) |
| `git push` / `make ci-ship` | Human | [scripts/ci_commit_push.sh](../../scripts/ci_commit_push.sh) |
| `make deploy-native` / `make deploy-local` | Human | [runbook.md](../runbook.md) |
| Secrets, LLM keys, Langfuse | Human | `.env.example`; never in prompts or graph state |
| Agent enabled in production | Human | `AGENT_ISSUE_ENABLED`, `validate_production_security()` |
| Go-live G1–G13 | Human | [go-live-checklist.md](../go-live-checklist.md) |
| Template standards pin bump / `standards upgrade` | Repository maintainers (PR) | [standards/GOVERNANCE.md](../../standards/GOVERNANCE.md) §5; AI blocked unless user requests |

**Managed generic standards:** Do not edit `.cursor/rules/generic/` or `.cursor/skills/generic/` copies in place — use `.cursor/rules/lms-ai/` overlay or upstream PR to the template repo, then upgrade. See [standards/GOVERNANCE.md](../../standards/GOVERNANCE.md).

---

## 5. Quality gates

| Change type | Minimum verification | Full pre-merge |
|-------------|----------------------|----------------|
| Python / API | `make lint` | `make ci-native` |
| Staff UI | `make staff-ui-typecheck` | `make ci-native` |
| Agent desk (`lms/agent/`) | `make test-agent` | `make ci-native` |
| Schema | `make migrate` (local) + integration tests | `make ci-native` |
| Security-sensitive | `pytest tests/hardening/test_security.py` | `make ci-native` |

**CI parity:** 211 tests — ruff, import-linter (6 contracts), mypy strict, pytest, Docker build.

Record commands in [CHANGELOG.md](CHANGELOG.md). Recommended before merge: `make lint && make ci-native`.

---

## 6. Artifacts

| Artifact | Path |
|----------|------|
| Charter (this file) | `docs/ai-sdlc/CHARTER.md` |
| Change log | `docs/ai-sdlc/CHANGELOG.md` |
| Generic change-log rule | `.cursor/rules/generic/ai-sdlc-change-log.md` |
| LMS-AI addendum | `.cursor/rules/lms-ai/ai-sdlc-change-log-lms-ai.md` |
| Reusable template pack | `.cursor/templates/ai-sdlc/` |
| Template standards governance | [standards/GOVERNANCE.md](../../standards/GOVERNANCE.md) |
| Requirements traceability | `docs/plan-mvp.md` (REQ-01–34) |
| MVP / architecture | `docs/MVP.md` |

---

## 7. Agent obligations

When modifying LMS-AI, AI agents **must**:

1. Follow this charter and [ai-sdlc-change-log](../../.cursor/rules/generic/ai-sdlc-change-log.md) + [LMS-AI addendum](../../.cursor/rules/lms-ai/ai-sdlc-change-log-lms-ai.md).
2. Append one [CHANGELOG.md](CHANGELOG.md) entry per change batch (newest first).
3. Run §5 verification for the touched areas.
4. Respect bounded contexts — import-linter contracts in `pyproject.toml`.
5. Use project skills for Python (DDD), analysis, and agent governance when relevant.

**Blocked without explicit user request:** commit, push, deploy, edit `.env`.

---

## 8. Traceability

| Link | Where |
|------|-------|
| GitHub issue | `#NNN` in change log and PR |
| Requirement | `REQ-XX` in [plan-mvp.md](../plan-mvp.md) |
| Go-live item | `G1`–`G13` in [go-live-checklist.md](../go-live-checklist.md) |
| ADR | `docs/adr/` (phase 3 — not yet bootstrapped) |

---

## 9. Rollout phases

| Phase | Focus | Status |
|-------|--------|--------|
| **0 — Charter** | Scope, autonomy, gates (this doc) | ☑ |
| **0b — Change log** | Append-only record + Cursor rules | ☑ |
| **1 — Traceability** | Issue/PR templates; REQ/issue CI check | ☑ |
| **2 — Review automation** | Bugbot/security on PRs | ☐ |
| **3 — Design discipline** | `docs/adr/`; doubt-driven triggers | ☐ |
| **4 — Orchestration** | CI triage, release notes | ☐ |
| **5 — Metrics** | Cycle time, quality trends | ☐ |

---

## 10. Related docs

| Doc | Purpose |
|-----|---------|
| [README.md](../../README.md) | Build, test, deploy |
| [MVP.md](../MVP.md) | Requirements and architecture |
| [plan-mvp.md](../plan-mvp.md) | Phased plan and REQ map |
| [runbook.md](../runbook.md) | Operations and agent env |
| [go-live-checklist.md](../go-live-checklist.md) | Pre-production verification |
| [standards/GOVERNANCE.md](../../standards/GOVERNANCE.md) | Template ownership, upgrade, contributions |
| [template-standards-plan.md](../template-standards-plan.md) | Phased rollout (verify-first) |
