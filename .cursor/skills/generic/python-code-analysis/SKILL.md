---
name: python-code-analysis
description: Runs static and dynamic code analysis for Python applications — ruff, mypy, import-linter, pytest, security and performance tests, FastAPI TestClient. Use when reviewing code quality, debugging CI failures, adding tests, hardening APIs, or when the user mentions static analysis, dynamic analysis, linting, type checking, or test strategy.
---

# Python Static & Dynamic Code Analysis

Analyze Python code **without changing behavior** unless fixing a verified defect. Prefer the project's configured tools over ad-hoc scripts.

**LMS-AI project commands and markers:** [python-code-analysis-lms-ai.md](../../lms-ai/python-code-analysis-lms-ai.md)

**Related craft skills:** [clean-code-ddd-python](../clean-code-ddd-python/SKILL.md), [clean-code-ddd-lms-ai](../../lms-ai/clean-code-ddd-lms-ai/SKILL.md)

---

## When to use

- Before opening or merging a PR
- CI failed on ruff, import-linter, or pytest
- Adding a feature — choose test level and static checks
- Refactoring — prove equivalence with tests first
- Security or concurrency review
- Agent desk changes — mock LLM, assert routing not prose

---

## Analysis workflow

Copy and track:

```
Analysis progress:
- [ ] 1. Static — ruff (+ format if needed)
- [ ] 2. Static — mypy (strict)
- [ ] 3. Static — import-linter (architecture contracts)
- [ ] 4. Dynamic — targeted pytest (unit → integration → e2e)
- [ ] 5. Dynamic — hardening / security / performance (if touching writes or auth)
- [ ] 6. Agent tests (if touching lms/agent/)
```

**Order:** static fixes are cheap; run them before long pytest suites. Re-run the full static pass after test-driven edits.

---

## Static analysis

Analysis **without executing** the full application (types and linters may spawn subprocesses).

| Tool | Finds | Typical command |
|------|--------|-----------------|
| **Ruff** | Style, bugs, import order, pyupgrade | `ruff check src tests` |
| **Ruff format** | Formatting drift | `ruff format src tests` |
| **mypy** | Type errors, untyped defs (strict) | `mypy` or `python -m mypy` |
| **import-linter** | Forbidden cross-module imports | `lint-imports` with `PYTHONPATH=src` |
| **Pydantic** | Invalid request/response at API edge | Runtime at boundary; models are static contracts |

### Ruff

- Fix auto-fixable issues: `ruff check --fix src tests`
- Do not disable rules globally to green CI — fix or narrow `per-file-ignores` with justification.
- Match project `target-version` and `line-length` in `pyproject.toml`.

### mypy (strict)

- Annotate public functions and dataclass fields; avoid `Any` except at true boundaries.
- Prefer `Protocol` for ports; `TypedDict` for LangGraph state.
- If mypy fails after a correct refactor, narrow with typed helpers — not blanket `# type: ignore`.

### import-linter

- Enforces **architectural** boundaries (DDD bounded contexts), not style.
- Violations mean wrong layer or cross-context leak — fix design, do not add ignores without ADR.

### Optional static (not in LMS-AI CI by default)

| Tool | Use when |
|------|----------|
| **bandit** | Security lint on new auth, file I/O, subprocess, SQL string build |
| **vulture** | Dead code sweep before large deletes |
| **deptry** | Dependency vs import mismatch |

Run optional tools when the change touches security-sensitive paths; document new dev deps if adopted project-wide.

---

## Dynamic analysis

Analysis **by executing** code — tests, probes, and runtime checks.

### Test pyramid (default)

| Layer | Scope | Speed | DB |
|-------|--------|-------|-----|
| **unit** | Pure logic, parsers, validation | Fast | No |
| **integration** | Services + SQLAlchemy session | Medium | Yes |
| **e2e** | HTTP API journeys (`httpx` / `TestClient`) | Slower | Yes |
| **hardening** | Concurrency, idempotency replay | Slower | Yes |
| **performance** | p95 SLO baselines | Slower | Yes |
| **agent** | Intent routing, tools, HITL | Medium | Often yes |

### pytest practices

- One behavior per test; name as spec: `test_checkout_rejected_when_holding_not_lendable`.
- Use markers (`@pytest.mark.unit`, etc.) — do not run entire suite when a subset suffices.
- **Arrange – Act – Assert**; avoid logic in tests.
- Fixtures in `conftest.py` for DB session and auth tokens — reuse, do not duplicate.
- For bugs: **failing test first**, then fix (Beck).

### FastAPI dynamic checks

```python
def test_issue_start_requires_auth(bare_client):
    response = bare_client.post("/api/v1/workflows/issue/start", json={...})
    assert response.status_code == 401
```

- Assert **status code + error envelope** (`code`, `message`), not only success paths.
- Use staff JWT fixtures for workflow routes; test RBAC denial (403).

### Concurrency & idempotency (dynamic)

- Parallel requests against same holding — exactly one checkout winner.
- Replay same `Idempotency-Key` — identical response, no double write.

### Performance (dynamic, not load test)

- Seed-scale p95 checks — regression signal, not capacity proof.
- If p95 fails, profile before optimizing (do not weaken SLO without ADR).

### Agent dynamic analysis

- Set `AGENT_MOCK_LLM=true` — assert **intent → tool** routing, not LLM text.
- Cover HITL: pending approval, `resume(approved=True/False)`.
- Cover allowlist: restricted tool names never invoked.

### Runtime observability (production dynamic)

- Correlation id on responses; structured logs on errors.
- Langfuse traces for agent turns (redacted args); structured stdout logs — see [imda-agentic-ai-governance](../imda-agentic-ai-governance/SKILL.md) (IMDA + Twelve-Factor XI).

---

## Static vs dynamic — quick map

| Question | Static | Dynamic |
|----------|--------|---------|
| Wrong import across bounded context? | import-linter | — |
| Type mismatch on port adapter? | mypy | integration test |
| API returns 422 shape? | Pydantic models | e2e pytest |
| Race on checkout? | — | hardening pytest |
| Prompt injection via tool args? | bandit (limited) | security pytest + governance review |
| Refactor preserved behavior? | mypy | same pytest green |

---

## CI alignment

Before push, run the same gates CI runs (see [python-code-analysis-lms-ai.md](../../lms-ai/python-code-analysis-lms-ai.md) for LMS-AI):

1. `ruff check`
2. `lint-imports`
3. `alembic upgrade head` (if DB tests)
4. `pytest` with `PYTHONPATH=src`

Cross-reference: [sonarqube-quality.md](../../rules/generic/sonarqube-quality.md) for Sonar-aligned complexity, duplication, and security hotspot rules.

---

## Review output format

When reporting analysis results:

```markdown
## Static
- ruff: pass / N issues (file:line — rule)
- mypy: pass / N errors
- import-linter: pass / contract name

## Dynamic
- unit: pass / fail (test name)
- integration/e2e: ...
- hardening/security/performance: skipped / pass

## Required before merge
- [ ] ...
```

Severity: **blocker** (CI red, security, data loss) vs **should fix** (style, missing marker) vs **follow-up** (optional bandit).

---

## Anti-patterns

| Anti-pattern | Fix |
|--------------|-----|
| Green CI by skipping tests | Fix root cause; use markers to scope, not `-k` permanently |
| `# type: ignore` on new code | Type the boundary properly |
| E2E-only for pure logic | Unit test the rule; one e2e for journey |
| Asserting private methods | Assert observable behavior |
| load test as only perf check | Use project SLO baselines first |
| Live LLM in CI | Mock LLM; test routing |

## Additional resources

- LMS-AI Makefile targets, markers, CI: [python-code-analysis-lms-ai.md](../../lms-ai/python-code-analysis-lms-ai.md)
