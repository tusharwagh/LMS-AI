# Traceability — LMS-AI

How issues, pull requests, and requirements connect in this repository.

---

## Rules

Every **pull request** to `main` must include in the **title or body**:

1. **GitHub issue** — `#NNN` or `https://github.com/tusharwagh/LMS-AI/issues/NNN`
2. **Requirement** — `REQ-XX` (from [plan-mvp.md §5](../plan-mvp.md)) **or** an explicit exemption:
   - `N/A — chore`
   - `N/A — docs`
   - `N/A — tooling`
   - `N/A — ci`
   - `N/A — deps`
   - `N/A — refactor`
   - `N/A — test`

CI enforces this via [scripts/check_pr_traceability.sh](../../scripts/check_pr_traceability.sh) (workflow: [.github/workflows/traceability.yml](../../.github/workflows/traceability.yml)).

---

## Issue templates

| Template | File | When |
|----------|------|------|
| Feature | `.github/ISSUE_TEMPLATE/feature.yml` | New capability |
| Bug | `.github/ISSUE_TEMPLATE/bug.yml` | Incorrect behavior |
| Chore | `.github/ISSUE_TEMPLATE/chore.yml` | Hygiene, CI, docs |

Blank issues are disabled — use a template.

---

## Pull request template

[.github/pull_request_template.md](../../.github/pull_request_template.md) — summary, traceability, test plan, AI SDLC checkbox.

---

## Local check

```bash
make check-traceability PR_BODY_FILE=.github/pull_request_template.md
# Or:
PR_TITLE="feat: example" PR_BODY="Closes #1 REQ-26" make check-traceability
```

---

## Requirement catalog

[plan-mvp.md §5](../plan-mvp.md) — REQ-01 through REQ-34.

Go-live mapping: [go-live-checklist.md](../go-live-checklist.md) (G1–G13).

---

## Bootstrap another repo

Copy `.cursor/templates/ai-sdlc/github/` — see [template README](../../.cursor/templates/ai-sdlc/README.md).
