---
name: ai-sdlc-change-log
description: Records every AI-assisted repository change in the append-only AI SDLC change log. Use when modifying code, config, docs, CI, or Cursor guidance in any repo bootstrapped with the AI SDLC template. AI assists humans; humans approve merge and release.
---

# AI SDLC — change log (generic)

## Operating model

**Option 1 — AI assists humans.** AI drafts and executes work; humans own merge, release, secrets, and irreversible operations.

## Mandatory: log every change

Before ending a session (or before asking the user to commit), **append one entry** to the project change log for **each distinct AI-assisted change batch**.

| Repo | Change log path |
|------|-----------------|
| Bootstrapped from template | `docs/ai-sdlc/CHANGELOG.md` |
| Project addendum | May override path — check `.cursor/rules/<project>/ai-sdlc-change-log-*.md` |

### What counts as a change batch

One entry per coherent unit of work, for example:

- A feature, fix, or refactor across one or more files
- A doc or rule update tied to one intent
- CI or Makefile target changes for one purpose

Do **not** skip logging because the change is small. Use stage `chore` for hygiene-only work.

### Entry content

Use the format in the change log file. Required fields:

- **Stage** — plan, design, implement, verify, ship, or chore
- **Intent** — user request or problem solved
- **Changes** — principal paths (not every line)
- **Verification** — commands run, or `not run` with reason
- **Human gate** — `pending` until the user merges or explicitly approves

Insert **newest first** (directly under `## Entries`).

### When NOT to log

- Read-only exploration (questions, reviews with no edits)
- User explicitly says "do not record this"

## Agent workflow

1. Read [CHARTER.md](../../docs/ai-sdlc/CHARTER.md) (or project charter path) for scope and gates.
2. Confirm change log path (generic or project addendum).
2. Do the work.
3. Run verification appropriate to the stage (lint, tests — per project addendum).
4. Append the change log entry.
5. Mention the entry title in the final reply so the user can find it.

## Bootstrap

New repos: copy `.cursor/templates/ai-sdlc/` per `README.md` in that folder.
