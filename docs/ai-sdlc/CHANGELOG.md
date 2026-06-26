# AI SDLC Change Log

Append-only record of **AI-assisted changes** to this repository. Newest entries first.

**Model:** AI assists humans at each stage; humans approve merge, release, and production operations.

---

## Entry format

Each entry uses this block (copy per change):

```markdown
### YYYY-MM-DD — Short title

| Field | Value |
|-------|-------|
| **Stage** | plan \| design \| implement \| verify \| ship \| chore |
| **Intent** | What was requested or why |
| **Changes** | Key files or areas touched |
| **Verification** | Commands run or gates passed (e.g. `make lint`) |
| **Human gate** | pending \| approved by \<name\> |
| **Follow-ups** | Optional — issues, ADRs, debt |
```

**Stages**

| Stage | When to use |
|-------|-------------|
| plan | Requirements, issues, acceptance criteria |
| design | ADRs, API contracts, architecture |
| implement | Code, config, migrations, UI |
| verify | Tests, review, lint, security checks |
| ship | PR, release notes, deploy prep |
| chore | Tooling, docs-only, repo hygiene |

---

## Entries

### 2026-06-24 — Phase 1 traceability (issue/PR templates + CI)

| Field | Value |
|-------|-------|
| **Stage** | plan |
| **Intent** | Phase 1 — GitHub issue/PR templates; enforce issue + REQ links on PRs via CI |
| **Changes** | `.github/ISSUE_TEMPLATE/*`, `.github/pull_request_template.md`, `.github/workflows/traceability.yml`, `scripts/check_pr_traceability.sh`, `make check-traceability`, `docs/ai-sdlc/TRACEABILITY.md`, `.cursor/templates/ai-sdlc/github/*`, `docs/ai-sdlc/CHARTER.md`, `docs/ai-sdlc/README.md`, `Makefile` |
| **Verification** | `PR_TITLE="chore: test" PR_BODY="Closes #1 N/A — chore" make check-traceability` |
| **Human gate** | pending |
| **Follow-ups** | Phase 2 — review automation |

### 2026-06-24 — Phase 0 AI SDLC charter

| Field | Value |
|-------|-------|
| **Stage** | plan |
| **Intent** | Phase 0 — define scope, autonomy levels, human gates, and quality gates for AI-assisted SDLC (option 1) |
| **Changes** | `docs/ai-sdlc/CHARTER.md`, `docs/ai-sdlc/README.md`, `docs/ai-sdlc.md`, `.cursor/templates/ai-sdlc/CHARTER.template.md`, `.cursor/templates/ai-sdlc/ai-sdlc-charter.rule.md`, `.cursor/rules/generic/ai-sdlc-charter.md`, `.cursor/rules/lms-ai/ai-sdlc-charter-lms-ai.md`, `.cursor/templates/ai-sdlc/README.md`, `.cursor/README.md`, `README.md` |
| **Verification** | not run (docs and Cursor rules only) |
| **Human gate** | pending |
| **Follow-ups** | Phase 1 — done in entry above |

### 2026-06-24 — Bootstrap AI SDLC change logging

| Field | Value |
|-------|-------|
| **Stage** | chore |
| **Intent** | Start AI-led SDLC (option 1: AI assists humans); record all repo changes in an append-only log; reusable template for other repos |
| **Changes** | `.cursor/templates/ai-sdlc/*`, `.cursor/rules/generic/ai-sdlc-change-log.md`, `.cursor/rules/lms-ai/ai-sdlc-change-log-lms-ai.md`, `docs/ai-sdlc/CHANGELOG.md`, `.cursor/README.md` |
| **Verification** | not run (docs and Cursor rules only) |
| **Human gate** | pending |
| **Follow-ups** | Phase 0 charter — done in entry above |
