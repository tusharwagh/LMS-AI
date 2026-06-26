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

<!-- Append new entries below this line. Newest first. -->
