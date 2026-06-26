# Cursor guidance layout

Portable engineering guidance is split from LMS-AI-specific addenda. Generic and project-specific content each live under **`rules/`** and **`skills/`** — not as top-level folders under `.cursor/`.

## Directory structure

```
.cursor/
  rules/
    generic/          # Portable rules (no LMS-AI repo paths as primary content)
    lms-ai/           # LMS-AI rule addenda / overrides
  skills/
    generic/          # Portable skills
    lms-ai/           # LMS-AI skill addenda
  README.md           # This file
```

## What Cursor loads

Cursor discovers **rules** under `.cursor/rules/` (including subfolders) and **skills** under `.cursor/skills/` (including subfolders).

| Path | Content |
|------|---------|
| `.cursor/rules/generic/*.md` | Portable rules |
| `.cursor/rules/lms-ai/*.md` | LMS-AI rule addenda |
| `.cursor/skills/generic/<name>/` | Portable skills |
| `.cursor/skills/lms-ai/<name>/` or `*.md` | LMS-AI skill addenda |

## Editing guidance

1. **Generic content** — edit under `.cursor/rules/generic/` or `.cursor/skills/generic/`.
2. **LMS-AI addenda** — edit under `.cursor/rules/lms-ai/` or `.cursor/skills/lms-ai/`.

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

Standalone generic rules (no addendum): `code-simplification.md`, `doubt-driven-development.md`.

| Generic rule | LMS-AI addendum |
|--------------|-----------------|
| `rules/generic/ai-sdlc-change-log.md` | `rules/lms-ai/ai-sdlc-change-log-lms-ai.md` |
| `rules/generic/ai-sdlc-charter.md` | `rules/lms-ai/ai-sdlc-charter-lms-ai.md` |

**AI SDLC template** (bootstrap other repos): `.cursor/templates/ai-sdlc/` — see `README.md` there. Live docs: `docs/ai-sdlc/CHARTER.md`, `docs/ai-sdlc/CHANGELOG.md`.
