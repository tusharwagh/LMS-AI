---
name: sonarqube-quality
description: SonarQube-aligned quality rules for Python FastAPI services — bugs, vulnerabilities, code smells, security hotspots, complexity, and duplication. Use when reviewing code, fixing Sonar issues, or aligning local lint/test gates with Sonar quality profiles.
---

# SonarQube Quality Rules (Python / FastAPI)

Quality gates aligned with common **SonarQube** rule families for Python (`python`, `security`, `maintainability`). This repo enforces many equivalents locally via **ruff**, **mypy**, **import-linter**, and **pytest** — see [python-code-analysis](../skills/python-code-analysis/SKILL.md).

Craft principles: [clean-code-ddd-python](../skills/clean-code-ddd-python/SKILL.md) (Clean Code, SOLID, DDD).

---

## When to use

- Sonar scan reported issues on a PR
- Designing modules to pass quality gate on new code
- Choosing between quick fix vs structural fix (SRP, DIP)
- Aligning CI with Sonar **new code** thresholds

---

## Local toolchain mapping

| Sonar category | Local equivalent | Command |
|----------------|------------------|---------|
| Bugs / style / complexity | Ruff (`E,F,I,UP,B`) | `ruff check src tests` |
| Type safety | mypy strict | `mypy` |
| Architecture boundaries | import-linter | `lint-imports` |
| Security (subset) | Ruff `B`, security tests | `pytest tests/hardening/test_security.py` |
| Tests / coverage | pytest markers | `make ci-native` |
| Duplication | Manual + Sonar CPd | refactor shared helpers |

**Pre-merge:** `make lint` (ruff + import-linter + mypy).

---

## Quality gate (recommended)

| Metric | Target (new code) | Notes |
|--------|-------------------|--------|
| Bugs | 0 | Blocker / critical |
| Vulnerabilities | 0 | Blocker / critical |
| Security hotspots | Reviewed | No unreviewed high severity |
| Code smells (blocker/critical) | 0 | Fix or justify in ADR |
| Coverage on new code | ≥ 80% | pytest markers; focus behavior |
| Duplicated lines | &lt; 3% on new code | Extract helpers, not copy-paste |
| Cognitive complexity | ≤ 15 per function | Split or guard clauses |

Adjust thresholds in Sonar project settings; this file is the engineering default for LMS-AI.

---

## Bugs (reliability)

Rules that prevent incorrect runtime behavior.

| Rule theme | Sonar-style ID | Requirement |
|------------|----------------|-------------|
| No bare `except:` | python:S5754 | Catch specific exceptions; log at boundary |
| No swallowed exceptions | python:S1166 | Re-raise, translate to `AppError`, or log with context |
| Return consistent types | — | mypy strict; no `Any` leakage in public APIs |
| Close resources | python:S2095 | Use context managers (`with session`) |
| No equality on identity-sensitive types | — | Compare UUIDs by value; mind ORM identity map |
| Validate None before use | — | Guard clauses; mypy optional narrowing |
| Idempotency replay safe | — | Cached workflow commit must not double-write |

**LMS-AI pattern:** Domain failures → `AppError`; never mix ad-hoc HTTP shapes.

---

## Vulnerabilities (security)

| Rule theme | Sonar-style ID | Requirement |
|------------|----------------|-------------|
| No hardcoded secrets | python:S2068 | Use `Settings` / env; reject default secret in prod |
| SQL injection | python:S3649 | SQLAlchemy `text()` with bound params only |
| Command injection | python:S2076 | Never `shell=True` with user/LLM input |
| Path traversal | python:S2083 | No user paths to open files outside allowed dirs |
| Weak crypto | python:S5542 | bcrypt for passwords; JWT HS256 with strong secret |
| Debug leakage | — | Generic errors when `APP_DEBUG=false` |
| SSRF from agent tools | — | No arbitrary URL tools; allowlisted workflows only |

Cross-reference: [.cursor/rules/security-and-hardening.md](security-and-hardening.md).

---

## Security hotspots (review required)

Treat as **mandatory human review**, not auto-close:

- Auth and RBAC changes (`StaffAuth`, `AdminAuth`, `require_roles`)
- Agent write tools (`commit_issue`, `cancel_issue`, `transition_fulfillment`)
- PII in logs, Langfuse traces, or LLM prompts
- `eval`, `exec`, `pickle`, `yaml.load` without SafeLoader
- Dynamic SQL string concatenation
- CORS, rate limits, security headers middleware

---

## Code smells (maintainability)

### Complexity

| Rule theme | Sonar-style ID | Limit |
|------------|----------------|-------|
| Cognitive complexity | python:S3776 | ≤ 15 per function; split orchestration steps |
| Function length | — | Target &lt; 20 lines (Clean Code); extract helpers |
| Nesting depth | — | Max 2 levels; use guard clauses |
| Too many parameters | python:S107 | ≤ 5; use dataclass/command object |

### Design smells (SOLID / DDD)

| Smell | Fix |
|-------|-----|
| God class / module | SRP split; move to application or workflow |
| Feature envy | Move logic to owning bounded context |
| Inappropriate intimacy | Port + adapter, not cross-context ORM |
| Shotgun surgery | Stabilize contracts; avoid duplicated policy |
| Divergent change | Split read vs write paths |

### Python-specific smells

| Rule theme | Sonar-style ID | Requirement |
|------------|----------------|-------------|
| Unused imports / variables | F401, F841 | `ruff check` clean |
| Redundant types | — | mypy without unused `cast` |
| Broad `except Exception` | python:S5754 | Only at API boundary handler |
| Magic numbers | python:S109 | Named constants or enums |
| Empty except/pass | python:S108 | Comment why or remove |
| Boolean params proliferation | — | Prefer enums or separate functions (Beck) |

---

## Duplication

| Rule theme | Sonar CPd | Requirement |
|------------|-----------|-------------|
| Identical blocks | — | Extract shared function after second use |
| Copy-paste validation | — | Single `ValidationReport` / validator |
| Repeated error envelopes | — | `AppError` + `error_body()` only |
| Test arrange duplication | — | Fixtures in `conftest.py` |

**Do not** deduplicate unrelated flows into a single mega-function — that violates SRP.

---

## Testing (Sonar coverage alignment)

| Requirement | LMS-AI practice |
|-------------|-----------------|
| New behavior has tests | unit → integration → e2e by scope |
| Name tests as specs | `test_issue_rejected_when_patron_blocked` |
| No assertion on privates | Assert HTTP envelope, state, side effects |
| Agent tests mock LLM | `AGENT_MOCK_LLM=true`; assert routing |
| Security regressions | `tests/hardening/` |

---

## FastAPI / API smells

| Smell | Fix |
|-------|-----|
| Validation in services | Pydantic at route boundary only |
| Leaking stack traces | `register_exception_handlers` generic 500 |
| Missing auth on route | `StaffAuth` / router-level `Depends` |
| Inconsistent response shape | Single `{code, message, retriable, details}` |
| Breaking response fields | Additive optional fields only |

Cross-reference: [.cursor/rules/api-and-interface-design.md](api-and-interface-design.md).

---

## Agent / LangGraph smells

| Smell | Fix |
|-------|-----|
| Business rules in graph nodes | Coordinator + application services |
| Business rules in prompts only | Structural allowlist + HITL |
| Unbounded tool loop | `agent_max_tool_calls_per_turn` |
| PII in traces | `redact_for_audit`, pseudonyms |
| Unrestricted tools | `RESTRICTED_TOOL_NAMES` deny-by-default |
| Multi-slot guard in one helper | Split `_patron_id` / `_holding_id`; compose in `_patron_and_holding` |
| Scattered staff-facing strings | Centralize in `lms/agent/messages.py`; intent + query-echo builders |
| Technical jargon in desk copy | No UUIDs, pseudonyms, tool names, "slots", "HITL" in `assistant_message` |
| Secrets or flags in prompts/graph state | Env via `Settings`; validate at startup |
| Dev-only graph fork | Same graph; `AGENT_MOCK_LLM` / stub tools in config |
| Log files inside containers | Structured stdout + Langfuse spans (redacted) |

Cross-reference: [imda-agentic-ai-governance](../skills/imda-agentic-ai-governance/SKILL.md) (IMDA + Twelve-Factor).

---

## Issue triage

When Sonar flags an issue:

```
1. Blocker/Critical bug or vulnerability → fix before merge
2. Security hotspot → security review + test
3. Code smell on new code → fix if local refactor; else track debt
4. Duplication → extract helper if same bounded context
5. Coverage gap → add behavior test, not line-hitting test
6. False positive → document Sonar suppression with rule ID + reason (narrow scope)
```

**Prefer structural fixes** (port, workflow, validator) over Sonar-only suppressions when the smell indicates SOLID/DDD violation.

---

## Verification checklist

- [ ] `make lint` passes (ruff, import-linter, mypy)
- [ ] Targeted pytest for changed modules
- [ ] No new hardcoded secrets or SQL concatenation
- [ ] Cognitive complexity acceptable on touched functions
- [ ] No cross-context infrastructure imports
- [ ] Sonar new-code gate green (if Sonar is wired to CI)

---

## Related documents

| Document | Role |
|----------|------|
| [clean-code-ddd-python](../skills/clean-code-ddd-python/SKILL.md) | Clean Code, SOLID, DDD |
| [clean-code-ddd-lms-ai](../skills/clean-code-ddd-lms-ai/SKILL.md) | Repo layout, import contracts |
| [python-code-analysis](../skills/python-code-analysis/SKILL.md) | Static/dynamic analysis |
| [code-simplification.md](code-simplification.md) | Refactor without behavior change |
| [security-and-hardening.md](security-and-hardening.md) | App security controls |
