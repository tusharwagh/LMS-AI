# AI SDLC Charter — PROJECT

**Status:** Active  
**Model:** Option 1 — **AI assists humans** at each stage  
**Owner:** \<team or individual\>

This charter defines how AI agents and humans collaborate in this repository. Customize placeholders (`PROJECT`, paths, commands) when bootstrapping a new repo.

---

## 1. Purpose

Establish a repeatable, auditable software delivery process where:

- AI **accelerates** planning, design, implementation, verification, and shipping.
- Humans **own** decisions with irreversible or high-blast-radius impact.
- Every AI-assisted change batch is **recorded** in the append-only change log.

---

## 2. Scope

| In scope | Out of scope (for now) |
|----------|-------------------------|
| Application code, tests, migrations | Fully autonomous merge/deploy without human approval |
| CI/CD and Makefile targets | AI modifying production infrastructure without human gate |
| Project and Cursor docs (rules, skills) | Committing secrets, credentials, or PII |
| Issue/PR drafting | Replacing human accountability for production incidents |

---

## 3. Autonomy levels

Use these levels at each SDLC stage. Default for this repo: **AI assists; human approves** at boundaries.

| Level | Meaning | Example |
|-------|---------|---------|
| **A — Autonomous** | AI may act without asking; human reviews later in the change log | Formatting, boilerplate tests, changelog entry |
| **Advise — Recommend** | AI proposes; human confirms before execution | API shape changes, new dependencies |
| **Blocked — Human only** | AI must not execute; may draft for human | Merge, push, deploy, secrets, production config |

### By SDLC stage

| Stage | AI may (A) | AI must advise (Advise) | Human only (Blocked) |
|-------|------------|-------------------------|----------------------|
| **Plan** | Draft issues, acceptance criteria, REQ maps | Scope changes, deferrals | Prioritization sign-off |
| **Design** | Draft ADRs, diagrams, API sketches | Cross-boundary design, new aggregates | Final architecture approval |
| **Implement** | Code, tests, migrations, docs | Public API changes, auth/security touch | — |
| **Verify** | Run lint/tests; draft review notes | Security findings, failing CI interpretation | Merge approval |
| **Ship** | Draft PR description, release notes | Version bumps, migration on shared env | Push, deploy, go-live |

---

## 4. Human gates

| Action | Owner | Notes |
|--------|-------|-------|
| Merge to default branch | Human | After CI green |
| `git push` | Human | Including `make ci-ship` flows |
| Production/staging deploy | Human | — |
| Secrets and `.env` | Human | Never commit; never paste into prompts |
| Dependency major upgrades | Human | Review lockfile and advisories |
| Go-live / compliance sign-off | Human | Per project checklist if applicable |

---

## 5. Quality gates

Minimum verification before a change batch is considered complete:

| Stage | Gate | Command / check |
|-------|------|-----------------|
| Implement (default) | Lint | \<e.g. `make lint`\> |
| Implement (UI) | Typecheck | \<e.g. `npm run typecheck`\> |
| Verify | Full CI parity | \<e.g. `make ci-native`\> |
| Ship | Remote CI | \<e.g. GitHub Actions on PR\> |

Record commands run (or `not run` + reason) in [CHANGELOG.md](CHANGELOG.md).

---

## 6. Artifacts

| Artifact | Path | Purpose |
|----------|------|---------|
| **Charter** (this file) | `docs/ai-sdlc/CHARTER.md` | Scope, autonomy, gates |
| **Change log** | `docs/ai-sdlc/CHANGELOG.md` | Append-only AI-assisted change record |
| **Generic rule** | `.cursor/rules/generic/ai-sdlc-change-log.md` | Agent: log every change batch |
| **Project addendum** | `.cursor/rules/<project>/ai-sdlc-change-log-<project>.md` | Paths and project gates |
| **Template pack** | `.cursor/templates/ai-sdlc/` | Bootstrap other repos |

---

## 7. Agent obligations

When modifying this repository, AI agents **must**:

1. Follow this charter and the change-log rule.
2. Append one change-log entry per change batch (newest first) before ending the session.
3. Run verification appropriate to the stage (§5).
4. Set **Human gate** to `pending` until the user merges or explicitly approves.
5. Escalate to human for **Blocked** actions (§3).

When **not** to log: read-only Q&A; user says "do not record."

---

## 8. Traceability (recommended)

Link change-log entries and PRs to:

- Issue tracker: `#NNN`
- Requirements: project requirement IDs (if used)
- ADRs: `docs/adr/` (when introduced)

---

## 9. Rollout phases

| Phase | Focus | Status |
|-------|--------|--------|
| **0 — Charter** | This document; scope and gates | ☑ |
| **1 — Traceability** | Issue/PR templates; REQ/issue links | ☐ |
| **2 — Review automation** | Bugbot/security on PRs | ☐ |
| **3 — Design discipline** | ADRs; doubt-driven triggers | ☐ |
| **4 — Orchestration** | CI triage, release notes automation | ☐ |
| **5 — Metrics** | Cycle time, quality trends | ☐ |

Update status as phases complete.

---

## 10. Related guidance

| Resource | Path |
|----------|------|
| Change log | [CHANGELOG.md](CHANGELOG.md) |
| Cursor template bootstrap | [.cursor/templates/ai-sdlc/README.md](../../.cursor/templates/ai-sdlc/README.md) |
| Project README | \<link to root README\> |
