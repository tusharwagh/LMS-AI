---
name: ai-sdlc-change-log-lms-ai
description: LMS-AI AI SDLC addendum — change log path, verification commands, and human gates. Use with generic ai-sdlc-change-log rule.
---

# LMS-AI — AI SDLC change log addendum

Extends [ai-sdlc-change-log.md](../generic/ai-sdlc-change-log.md).

## Change log

| Item | Value |
|------|-------|
| **Path** | `docs/ai-sdlc/CHANGELOG.md` |
| **Template** | `.cursor/templates/ai-sdlc/CHANGELOG.template.md` |

## Verification by stage

| Stage | Minimum verification |
|-------|----------------------|
| implement (Python) | `make lint` |
| implement (agent) | `make test-agent` |
| implement (staff UI) | `make staff-ui-typecheck` |
| verify (pre-merge) | `make ci-native` |
| ship | Human merge; CI green on PR (`.github/workflows/ci.yml`) |

## Human gates (LMS-AI)

| Action | Owner |
|--------|-------|
| Merge to `main` | Human |
| `make ci-ship` / push | Human confirms commit message |
| Production deploy | Human (`make deploy-native` / `deploy-local`) |
| Secrets / `.env` | Human only — never commit |
| Go-live sign-off | Human per `docs/go-live-checklist.md` |

## Traceability

When relevant, link entries to GitHub issues (`#NNN`) and requirements (`REQ-XX` in `docs/plan-mvp.md`).

PRs to `main` must pass `scripts/check_pr_traceability.sh` (`.github/workflows/traceability.yml`). See `docs/ai-sdlc/TRACEABILITY.md`.

**See also:** [ai-sdlc-change-log.md](../generic/ai-sdlc-change-log.md) (generic rule).
