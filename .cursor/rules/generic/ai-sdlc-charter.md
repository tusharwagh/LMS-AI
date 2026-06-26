---
name: ai-sdlc-charter
description: Follow the AI SDLC charter for scope, autonomy levels, human gates, and quality gates. Use when planning or delivering any AI-assisted work in a repo bootstrapped with the AI SDLC template. Complements ai-sdlc-change-log rule.
---

# AI SDLC — charter (generic)

## Read first

Before non-trivial work, align with the project charter:

| Repo | Charter path |
|------|----------------|
| Bootstrapped from template | `docs/ai-sdlc/CHARTER.md` |
| Project addendum | May reference charter — check `.cursor/rules/<project>/` |

## Model

**Option 1 — AI assists humans.** AI drafts and executes; humans own merge, release, secrets, and irreversible operations.

## Quick reference

| SDLC stage | AI default | Human gate |
|------------|------------|------------|
| Plan | Draft issues and acceptance criteria | Scope sign-off |
| Design | Draft ADRs and contracts | Cross-boundary approval |
| Implement | Code and tests | Public API / security changes → advise first |
| Verify | Lint and tests | Merge approval |
| Ship | PR and release notes draft | Push and deploy |

## Autonomy

- **A (autonomous):** boilerplate, tests, changelog — human reviews later
- **Advise:** API shape, dependencies, architecture — confirm before executing
- **Blocked:** merge, push, deploy, secrets — human only

## After work

Append [CHANGELOG.md](../../docs/ai-sdlc/CHANGELOG.md) per [ai-sdlc-change-log.md](ai-sdlc-change-log.md).

## Bootstrap

New repos: copy `CHARTER.template.md` from `.cursor/templates/ai-sdlc/` → `docs/ai-sdlc/CHARTER.md`.
