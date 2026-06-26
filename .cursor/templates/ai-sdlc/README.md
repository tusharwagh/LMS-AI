# AI SDLC — reusable bootstrap

Portable template for **option 1: AI assists humans** at each SDLC stage. Copy into any repository to start AI-assisted delivery with an auditable change log and charter.

## Bootstrap a new repo

### Core (phase 0)

1. Copy template files:
   ```bash
   mkdir -p docs/ai-sdlc .cursor/rules/generic .cursor/rules/<project>/
   cp .cursor/templates/ai-sdlc/CHANGELOG.template.md docs/ai-sdlc/CHANGELOG.md
   cp .cursor/templates/ai-sdlc/CHARTER.template.md docs/ai-sdlc/CHARTER.md
   cp .cursor/templates/ai-sdlc/ai-sdlc-change-log.rule.md .cursor/rules/generic/ai-sdlc-change-log.md
   cp .cursor/templates/ai-sdlc/ai-sdlc-charter.rule.md .cursor/rules/generic/ai-sdlc-charter.md
   ```
2. Customize `docs/ai-sdlc/CHARTER.md` (project name, commands, links).
3. Create project addenda from `ai-sdlc-change-log.addendum.template.md` → `.cursor/rules/<project>/ai-sdlc-change-log-<project>.md`.
4. Register rule pairs in `.cursor/README.md` (if used).
5. Append bootstrap entries to `docs/ai-sdlc/CHANGELOG.md`.

### Traceability (phase 1)

1. Copy GitHub assets:
   ```bash
   mkdir -p .github/ISSUE_TEMPLATE .github/workflows scripts
   cp .cursor/templates/ai-sdlc/github/pull_request_template.md .github/
   cp .cursor/templates/ai-sdlc/github/ISSUE_TEMPLATE/* .github/ISSUE_TEMPLATE/
   cp .cursor/templates/ai-sdlc/github/workflows/traceability.yml .github/workflows/
   cp .cursor/templates/ai-sdlc/github/check_pr_traceability.sh scripts/check_pr_traceability.sh
   chmod +x scripts/check_pr_traceability.sh
   ```
2. Edit `.github/ISSUE_TEMPLATE/config.yml` — replace `<REPO_URL>` and requirements doc link.
3. Add `docs/ai-sdlc/TRACEABILITY.md` (copy from an bootstrapped repo or author from template).
4. Add `make check-traceability` to Makefile (optional).

## Files in this template

| Path | Purpose |
|------|---------|
| `CHARTER.template.md` | Scope, autonomy, gates |
| `CHANGELOG.template.md` | Append-only change log |
| `ai-sdlc-charter.rule.md` / `ai-sdlc-change-log.rule.md` | Cursor rules |
| `ai-sdlc-change-log.addendum.template.md` | Project gates |
| `github/` | Issue/PR templates, traceability CI script and workflow |

## Operating model

- **AI assists** — drafts, implements, tests, documents; does not merge or deploy without human approval.
- **Humans own** — merge, production release, secrets, and irreversible operations.
- **Charter** — scope and autonomy levels (`docs/ai-sdlc/CHARTER.md`).
- **Traceability** — every PR links `#issue` + `REQ-XX` (or `N/A — chore|docs|…`).
- **Change log** — every AI-assisted repo modification gets one append-only entry before the session ends.
