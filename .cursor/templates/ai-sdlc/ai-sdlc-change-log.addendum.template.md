---
name: ai-sdlc-change-log-PROJECT
description: PROJECT AI SDLC addendum — change log path and verification commands. Use with generic ai-sdlc-change-log rule.
---

# PROJECT — AI SDLC change log addendum

Extends [ai-sdlc-change-log.md](../generic/ai-sdlc-change-log.md).

## Change log

| Item | Value |
|------|-------|
| **Path** | `docs/ai-sdlc/CHANGELOG.md` |
| **Template** | `.cursor/templates/ai-sdlc/CHANGELOG.template.md` |

## Verification by stage

| Stage | Minimum verification |
|-------|----------------------|
| implement (Python) | `make lint` or project equivalent |
| implement (UI) | `make staff-ui-typecheck` or equivalent |
| verify | `make ci-native` or full CI before merge |
| ship | Human merge + CI green on PR |

## Human gates (this project)

| Action | Owner |
|--------|-------|
| Merge to main | Human |
| Production deploy | Human |
| Secrets / `.env` | Human only — never commit |

## Traceability (optional)

Link entries to issues (`#NNN`) and requirements when applicable.
