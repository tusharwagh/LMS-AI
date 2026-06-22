# Cursor guidance layout

Portable engineering guidance is split from LMS-AI-specific addenda so generic rules and skills can be reused across projects.

## Directory structure

```
.cursor/
  generic/
    rules/          # Portable rules (no LMS-AI repo paths as primary content)
    skills/         # Portable skills
  lms-ai/
    rules/          # LMS-AI rule addenda / overrides
    skills/         # LMS-AI skill addenda
  rules/            # Symlinks → generic rules + lms-ai addenda (Cursor discovery)
  skills/           # Symlinks → generic skills + lms-ai addendum files
  README.md         # This file
```

## What Cursor loads

Cursor discovers **rules** under `.cursor/rules/` and **skills** under `.cursor/skills/`. Those folders contain symlinks to the canonical content in `generic/` and `lms-ai/`.

| Discovery path | Canonical source |
|----------------|------------------|
| `.cursor/rules/*.md` | `.cursor/generic/rules/` or `.cursor/lms-ai/rules/` |
| `.cursor/skills/<name>/` | `.cursor/generic/skills/<name>/` or `.cursor/lms-ai/skills/<name>/` |
| `.cursor/skills/python-code-analysis/lms-ai.md` | `.cursor/lms-ai/skills/python-code-analysis-lms-ai.md` |

## Editing guidance

1. **Generic content** — edit under `.cursor/generic/` (portable across repos).
2. **LMS-AI addenda** — edit under `.cursor/lms-ai/` (module map, Makefile, agent desk, RBAC, env tables).
3. **Do not edit symlinks** in `.cursor/rules/` or `.cursor/skills/` directly; update the target file in `generic/` or `lms-ai/`.

## Skill pairs

| Generic skill | LMS-AI addendum |
|---------------|-----------------|
| `clean-code-ddd-python` | `clean-code-ddd-lms-ai` |
| `python-code-analysis/SKILL.md` | `python-code-analysis-lms-ai.md` (linked as `lms-ai.md`) |
| `imda-agentic-ai-governance` | `imda-agentic-ai-governance-lms-ai.md` |

## Rule pairs

| Generic rule | LMS-AI addendum |
|--------------|-----------------|
| `frontend-ui-engineering.md` | `frontend-ui-engineering-lms-ai.md` |
| `api-and-interface-design.md` | `api-and-interface-design-lms-ai.md` |
| `security-and-hardening.md` | `security-and-hardening-lms-ai.md` |
| `sonarqube-quality.md` | `sonarqube-quality-lms-ai.md` |

Standalone generic rules (no addendum): `code-simplification.md`, `doubt-driven-development.md`.
