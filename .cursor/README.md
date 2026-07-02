# Cursor guidance layout

Portable engineering guidance is split from LMS-AI-specific addenda.

## Directory structure

```text
.cursor/
  rules/
    generic/          # Managed copies from standards/ — do not edit in place
    lms-ai/           # LMS-AI overlay (never drift-checked)
  skills/
    generic/          # Managed copies from standards/
    lms-ai/           # LMS-AI overlay
  templates/ai-sdlc/  # Managed bootstrap templates (from standards/)
```

## What Cursor loads

| Path | Content |
|------|---------|
| `.cursor/rules/generic/*.md` | Generic rules (materialized @ pin) |
| `.cursor/rules/lms-ai/*.md` | LMS-AI rule addenda |
| `.cursor/skills/generic/<name>/` | Generic skills |
| `.cursor/skills/lms-ai/<name>/` | LMS-AI skill addenda |

## Editing guidance

1. **Generic standards** — upstream PR to [org-ai-standards](https://github.com/tusharwagh/org-ai-standards), then `make standards-upgrade`. Do **not** edit `.cursor/rules/generic/` or `.cursor/skills/generic/` in place (CI fail mode).
2. **LMS-AI conventions** — edit `.cursor/rules/lms-ai/` or `.cursor/skills/lms-ai/`.

See [docs/template-standards/RUNBOOK-DIVERGED.md](../docs/template-standards/RUNBOOK-DIVERGED.md) if `make check-standards` reports diverged paths.

## Skill pairs

| Generic skill | LMS-AI addendum |
|---------------|-----------------|
| `skills/generic/clean-code-ddd-python` | `skills/lms-ai/clean-code-ddd-lms-ai` |
| `skills/generic/python-code-analysis/SKILL.md` | `skills/lms-ai/python-code-analysis-lms-ai.md` |
| `skills/generic/imda-agentic-ai-governance` | `skills/lms-ai/imda-agentic-ai-governance-lms-ai.md` |

## Rule pairs

| Generic rule | LMS-AI addendum |
|--------------|-----------------|
| `rules/generic/frontend-ui-engineering.md` | `rules/lms-ai/frontend-ui-engineering-lms-ai.md` |
| `rules/generic/api-and-interface-design.md` | `rules/lms-ai/api-and-interface-design-lms-ai.md` |
| `rules/generic/security-and-hardening.md` | `rules/lms-ai/security-and-hardening-lms-ai.md` |
| `rules/generic/sonarqube-quality.md` | `rules/lms-ai/sonarqube-quality-lms-ai.md` |
| `rules/generic/ai-sdlc-change-log.md` | `rules/lms-ai/ai-sdlc-change-log-lms-ai.md` |
| `rules/generic/ai-sdlc-charter.md` | `rules/lms-ai/ai-sdlc-charter-lms-ai.md` |

Standalone generic rules: `code-simplification.md`, `doubt-driven-development.md`.

Live governance: `docs/ai-sdlc/CHARTER.md`, `docs/ai-sdlc/CHANGELOG.md`.
