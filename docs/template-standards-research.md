# Template standards — research & specification

**Status:** Draft (discussion captured Jun 2026)  
**Purpose:** Preserve reasoning for a **separate template / standards repository** before implementation and before advancing AI-Led SDLC.  
**Audience:** Template owner, project leads, AI-assisted delivery participants.

**Related (LMS-AI today):**

| Asset | Path |
|-------|------|
| AI-SDLC bootstrap templates | [.cursor/templates/ai-sdlc/README.md](../.cursor/templates/ai-sdlc/README.md) |
| Generic vs project Cursor layout | [.cursor/README.md](../.cursor/README.md) |
| Live AI-SDLC docs (instantiated) | [docs/ai-sdlc/](ai-sdlc/) |
| LMS-AI research history | [research.md](research.md) |
| **Implementation plan** | [template-standards-plan.md](template-standards-plan.md) |

---

## 0. Session handoff (for new agent / new chat)

**Continue from here.** Open this file as primary context.

### Goal

Create a **separate repo** that acts as a **project template** and **standards source** for all future projects — extracting portable guidelines from LMS-AI without copying domain-specific content.

### Agreed decisions (Jun 2026 discussion)

| Topic | Decision |
|-------|----------|
| Drift enforcement | **Warn on first rollout** in CI; later **fail** on unmanaged divergence |
| Managed generic files | **Git submodule** at `standards/` (pinned to template release tag) |
| Diff reports | **Classify** findings (stale, diverged, contribution_candidate, overlay ignore) |
| Contribution loop | Build-time report → template owner review → accept/reject → template tag → projects bump pin |
| Complexity | **One manifest + profiles + one check script** — no per-risk bespoke process |
| Generic vs project | **Submodule = generic**; **overlay = `<project>/`** (LMS-AI pattern: `generic/` vs `lms-ai/`) |
| Profile bundles | **Canonical store + profile indexes** — files live once under `cursor/`, `docs/`; `profiles/<name>/profile.yaml` lists paths; `manifest.json` generated from indexes |
| Materialization | **Copy-on-init/upgrade** into project paths (`.cursor/rules/generic/`, etc.) — **not symlink** |
| Drift detection | **Deterministic** `check-standards` — diff project copies vs `standards/` at pin; **no agent required** for detection |
| Portable vs Cursor | **Two layers** — `docs/standards/` = source of truth; Cursor rules/skills = thin enforcers linking to docs (see §5.3) |

### Open questions

See **§15 Open backlog (prioritized)** — governance and org-level standards first.

### Suggested next agent prompt

> Read `docs/template-standards-plan.md`. Execute Phase 0 governance lock or Phase 1 mechanics lab (fixture + check-standards + T1–T10). Do not create template repo until Phase 1 exit criteria pass.

---

## 1. Problem statement

LMS-AI already splits **portable** engineering guidance from **project-specific** addenda (`.cursor/rules/generic/` vs `.cursor/rules/lms-ai/`, `.cursor/skills/generic/` vs `lms-ai/`, `.cursor/templates/ai-sdlc/`). Before scaling AI-assisted delivery across repos, that portable layer should live in a **dedicated template repo** with:

- Versioned releases
- Bootstrap / upgrade path for new projects
- Drift detection at build time
- A lightweight path for generic improvements to flow back to the template owner

This is **pre-requisite** to a broader **AI-Led SDLC** stage; current operating model remains **option 1: AI assists humans** ([docs/ai-sdlc/CHARTER.md](ai-sdlc/CHARTER.md)).

---

## 2. Feasibility

**Yes — feasible.** LMS-AI is already a partial prototype:

| Layer | In LMS-AI today | Template repo (future) |
|-------|-----------------|------------------------|
| AI-SDLC bootstrap | `.cursor/templates/ai-sdlc/` | `docs/ai-sdlc/templates/` in template repo |
| Portable standards (human/audit) | *Not yet* — content lives inside fat Cursor rules | `docs/standards/*.md` (source of truth) |
| Generic rules/skills | `.cursor/rules/generic/`, `.cursor/skills/generic/` | Thin enforcers copied to product repo |
| Project addenda | `.cursor/rules/lms-ai/`, `.cursor/skills/lms-ai/` | Stays in each product repo |
| Instantiated governance | `docs/ai-sdlc/CHARTER.md`, `CHANGELOG.md` | Per-project overlay |

---

## 3. Template repo shape (target)

Template repo **root** is the submodule checkout (product repo mounts it at `standards/`).

```text
org-ai-standards/                 # name TBD — submoduled as standards/ in product repos
├── README.md                     # Bootstrap, upgrade, ownership
├── CHANGELOG.md                  # Template releases
├── manifest.json                 # Generated from profile indexes; managed paths, never_manage
├── cursor/
│   ├── rules/generic/
│   └── skills/generic/
├── docs/
│   ├── standards/                # Portable source-of-truth Markdown
│   └── ai-sdlc/templates/
├── profiles/
│   ├── core/profile.yaml
│   ├── python/profile.yaml
│   ├── agentic/profile.yaml
│   └── frontend/profile.yaml
├── makefile-fragments/           # Per-profile .mk blocks (spliced on upgrade)
│   ├── core.mk
│   └── python.mk
├── .github/                      # Issue/PR templates, traceability workflow
├── scripts/
│   ├── check_pr_traceability.sh
│   └── check-standards.sh        # Canonical script; product invokes or wraps
├── contributions/
│   ├── inbox/
│   └── decisions/
└── bootstrap/                    # standards init / upgrade (TBD)
```

### Product repo shape (after bootstrap)

```text
my-project/
├── .standards-version            # e.g. 1.3.0 (template release tag)
├── .standards-profiles           # e.g. core,python,agentic
├── .standards-copied-at          # optional audit: tag + profiles at last materialize
├── standards/                    # git submodule → template repo @ tag (reference only)
├── .cursor/rules/generic/        # **copies** — thin enforcers (union of enabled profiles)
├── .cursor/skills/generic/       # **copies** — operational workflows + links to docs
├── docs/standards/               # **copies** — portable source-of-truth Markdown
├── .cursor/rules/<project>/      # overlay — never drift-checked vs template
├── docs/ai-sdlc/CHARTER.md       # instantiated overlay
└── Makefile                      # includes check-standards + profile Makefile fragments
```

---

## 4. Delivery mechanisms (evaluated)

| Approach | Use when | Notes |
|----------|----------|-------|
| **GitHub template repository** | New repo from scratch | Easy; needs drift/submodule for ongoing sync |
| **Git submodule @ tag** | Managed generic files | **Agreed** for managed paths |
| **Cookiecutter / Copier** | Parameterized bootstrap | Optional later; not required for v1 |
| **Copy-on-init/upgrade** | Materialize enabled profiles into project tree | **Agreed** with submodule reference + `check-standards` diff |
| **Copy-only bootstrap** | One-time seed, no ongoing pin | Insufficient alone — causes unmanaged drift |

**Agreed:** Submodule (reference @ tag) + copy materialization + manifest + build-time check.

---

## 5. Risks and mitigations (cohesive model)

One loop serves all risks: **manifest + profiles + submodule + `check-standards`**.

### 5.1 Drift

**Problem:** Projects copy standards once, edit generic files locally, or fall behind template releases.

**Drift types:**

| Type | Meaning | Behavior |
|------|---------|----------|
| **A. Stale** | Pin `v1.2`, template at `v1.5` | Warn; suggest `standards upgrade` |
| **B. Local edit** | Changed managed generic file | Warn (rollout) → fail |
| **C. Missing** | Template added files; project lacks them | Warn; upgrade adds them |
| **D. Contribution candidate** | Local generic improvement | Suggest upstream; async review |
| **E. Intentional overlay** | `<project>/` addenda | **Exclude** from comparison |

**Agreed mitigations:**

1. **Pin version** — `.standards-version`; CI compares to that tag, not floating `main`
2. **Manifest-only checks** — only paths listed in `manifest.json`
3. **Warn first rollout** — then fail on unmanaged divergence
4. **Contribution inbox** — report to template owner; accept/reject → new tag; traceability in template repo
5. **`standards upgrade`** — one command to bump submodule for managed paths; overlays untouched
6. **Classified diff report** — see §7

**User proposal (accepted in spirit):** Any drift addressed at **build**; generic improvements **suggested** to template owner; **report** generated for review; history in template repo. **Not** auto-merge into template. **Not** block product delivery on contribution review (only on unmanaged divergence once fail mode is on).

### 5.2 Over-templating

**Problem:** One mega-template for every stack and domain.

**Mitigations:**

- **Profiles** — optional bundles (`core`, `python`, `agentic`, `frontend`); drift check only enabled profiles
- **Generic-only in submodule** — no domain nouns in template
- **Mandatory addenda pattern** — project-specific only under `.cursor/rules/<project>/`
- **Makefile fragments** — marked blocks included from profile, not monolithic template Makefile

**LMS-AI precedent:** `generic/` vs `lms-ai/` split ([.cursor/README.md](../.cursor/README.md)).

**Agreed bundle model (canonical store + profile indexes):**

1. **Canonical store** — each file exists once under `cursor/`, `docs/`, `.github/`, etc. in the template repo (no per-profile duplicates).
2. **Profile indexes** — `profiles/<name>/profile.yaml` lists path globs; optional `extends: [core]` for layering.
3. **Single `manifest.json`** — generated from indexes (or indexes are the source); each entry: `path`, `profiles[]`, `materialize_to`, `managed`, `never_manage`.
4. **Monolithic submodule** — one pin (`.standards-version`); profiles control **what gets copied** and **what drift-check runs**, not separate repos.
5. **Orthogonal profiles + required `core`** — projects declare `.standards-profiles` (e.g. `core,python,agentic`); presets like `fullstack` are aliases only.
6. **Selective copy** — `standards init` / `upgrade` copies the union of enabled profile paths into project-visible locations; overlay dirs untouched.

Example `profiles/python/profile.yaml`:

```yaml
extends: [core]
includes:
  - docs/standards/python/**
  - cursor/skills/generic/clean-code-ddd-python/**
  - cursor/skills/generic/python-code-analysis/**
  - cursor/rules/generic/security-and-hardening.md
  - cursor/rules/generic/api-and-interface-design.md
  - cursor/rules/generic/sonarqube-quality.md
  - makefile-fragments/python.mk
```

### 5.3 Cursor-specific vs portable (agreed model)

**Problem:** Rules and skills are Cursor-native (YAML frontmatter, `description` triggers, skill discovery). Humans, security reviewers, and auditors need **tool-agnostic** standards they can read without Cursor. Today LMS-AI embeds most normative content directly in Cursor artifacts — e.g. `security-and-hardening.md` (~470 lines), `api-and-interface-design.md` (~310 lines) — and has **no** `docs/standards/` tree yet.

**Audiences:**

| Audience | Reads | Why |
|----------|-------|-----|
| Cursor / AI agent | `.cursor/rules/generic/`, `.cursor/skills/generic/` | Trigger conditions, workflows, pointers |
| Engineers (any editor) | `docs/standards/` | Day-to-day reference, onboarding |
| Auditors / compliance | `docs/standards/`, `docs/ai-sdlc/CHARTER.md` | Evidence without IDE plugins |
| Template owner | Template repo + drift reports | Versioned, diffable standards |

**Agreed two-layer model:**

```text
docs/standards/<topic>.md     ← SOURCE OF TRUTH (portable, no Cursor frontmatter)
        ▲
        │  canonical link (required in thin enforcer)
        │
.cursor/rules/generic/<topic>.md   ← THIN ENFORCER (frontmatter + when-to-use + link)
.cursor/skills/generic/<name>/SKILL.md   ← OPERATIONAL (workflow/checklists + link to doc)
```

**What belongs where:**

| Content type | `docs/standards/` | Cursor rule/skill |
|--------------|-------------------|-------------------|
| Normative principles, patterns, examples | Yes — full body | No — link only |
| YAML `name` / `description` (agent triggers) | No | Yes — rule/skill frontmatter |
| "When to use" / "When NOT to use" (short) | Optional summary in doc | Yes — keeps agent routing local |
| Step-by-step agent workflow, checklists | No | Yes — `SKILL.md` |
| Deep reference tables (IMDA factors, DDD map) | Yes | Link from skill |
| Project-specific gates | No — `docs/ai-sdlc/CHARTER.md` overlay | Yes — `<project>/` addenda |

**LMS-AI precedents to extend:**

| Pattern today | Target in template repo |
|---------------|-------------------------|
| `ai-sdlc-charter` rule → `docs/ai-sdlc/CHARTER.md` | **Already two-layer** — charter is per-project instantiated doc; rule stays thin (~40 lines) |
| Skills with co-located `reference.md` | **Migrate depth** to `docs/standards/`; `reference.md` retired or becomes a one-line redirect |
| Fat generic rules (security, API, frontend, …) | **Extract** body to `docs/standards/`; shrink rule to thin enforcer |
| `python-code-analysis` skill (operational commands) | Skill stays operational; normative "why" moves to `docs/standards/python/code-analysis.md` if any |

**Target `docs/standards/` layout (template repo):**

```text
docs/standards/
├── README.md                       # Index, how this relates to .cursor/ and ai-sdlc
├── core/
│   ├── code-simplification.md
│   └── doubt-driven-development.md
├── python/
│   ├── security-and-hardening.md
│   ├── api-and-interface-design.md
│   └── sonarqube-quality.md
├── agentic/
│   ├── imda-agentic-ai-governance.md
│   └── agent-security.md           # if split from security doc
└── frontend/
    └── ui-engineering.md
```

**Thin enforcer shape (target):**

```markdown
---
name: security-and-hardening
description: Hardens code against vulnerabilities. Use when handling user input...
canonical_doc: docs/standards/python/security-and-hardening.md
---

# Security and Hardening

**Canonical standard:** [docs/standards/python/security-and-hardening.md](../../../docs/standards/python/security-and-hardening.md)

Read the canonical doc before non-trivial security work. This rule exists for Cursor agent discovery only.

## When to use
- Building anything that accepts user input
- Implementing authentication or authorization
…
```

**Skill shape (target):**

```markdown
---
name: imda-agentic-ai-governance
description: Applies IMDA MGF v1.5 …
canonical_doc: docs/standards/agentic/imda-agentic-ai-governance.md
---

# IMDA Agentic AI Governance

**Canonical standard:** [docs/standards/agentic/imda-agentic-ai-governance.md](../../../docs/standards/agentic/imda-agentic-ai-governance.md)

## Workflow
- [ ] 1. Assess and bound risks upfront
…
```

**Relationship to `docs/ai-sdlc/`:**

| Path | Role | Managed by template? |
|------|------|----------------------|
| `docs/standards/` | Generic engineering standards | Yes — copied per profile |
| `docs/ai-sdlc/CHARTER.md` | Per-project autonomy, scope, gates | No — instantiated overlay |
| `docs/ai-sdlc/CHANGELOG.md` | Per-project change log | No — instantiated overlay |
| `docs/ai-sdlc/templates/` | Bootstrap templates | Yes — in template repo; copied once at init |

**Manifest pairing:** Where a standard has both a doc and a Cursor artifact, `manifest.json` lists **paired entries** with the same `profiles[]` and two `materialize_to` targets:

```json
{
  "id": "security-and-hardening",
  "profiles": ["python"],
  "canonical": "docs/standards/python/security-and-hardening.md",
  "enforcers": [
    "cursor/rules/generic/security-and-hardening.md"
  ],
  "materialize": {
    "docs/standards/python/security-and-hardening.md": "docs/standards/python/security-and-hardening.md",
    "cursor/rules/generic/security-and-hardening.md": ".cursor/rules/generic/security-and-hardening.md"
  }
}
```

Drift check diffs **both** copies independently against `standards/` at pin.

**`check-standards` additions for §5.3 (v1):**

| Check | Purpose |
|-------|---------|
| **Link integrity** | Every managed rule/skill with `canonical_doc` or `docs/standards/` link → target exists in materialized tree |
| **Pair completeness** | If manifest declares paired doc + enforcer, both present after materialize |
| **Orphan doc** | `docs/standards/` file in manifest but no enforcer → warn (doc-only standards are allowed for human-only topics) |
| **Fat enforcer** | Optional warn if rule body exceeds line threshold without `canonical_doc` — nudges extraction |

No agent required — grep + line count + manifest validation.

**Extraction cadence (proposed — open question #6):**

| Phase | Action |
|-------|--------|
| **Template v1.0** | Extract at least **core** + **python** fat rules; migrate skill `reference.md` content into `docs/standards/` |
| **Ongoing** | New standards: write `docs/standards/` first, add thin enforcer second |
| **Edits** | Substantive change to a fat rule → extract to doc in same PR (template repo) |

**LMS-AI extraction map (§5.3 — draft pairing):**

| Current Cursor artifact | Target canonical doc | Notes |
|-------------------------|----------------------|-------|
| `rules/generic/security-and-hardening.md` | `docs/standards/python/security-and-hardening.md` | Extract ~90% of body |
| `rules/generic/api-and-interface-design.md` | `docs/standards/python/api-and-interface-design.md` | Extract body |
| `rules/generic/sonarqube-quality.md` | `docs/standards/python/sonarqube-quality.md` | Extract body |
| `rules/generic/frontend-ui-engineering.md` | `docs/standards/frontend/ui-engineering.md` | `frontend` profile |
| `rules/generic/code-simplification.md` | `docs/standards/core/code-simplification.md` | `core` profile |
| `rules/generic/doubt-driven-development.md` | `docs/standards/core/doubt-driven-development.md` | `core` profile |
| `rules/generic/ai-sdlc-charter.md` | *(none — points to instantiated CHARTER)* | Stays thin; links overlay |
| `rules/generic/ai-sdlc-change-log.md` | *(none — points to instantiated CHANGELOG)* | Stays thin |
| `skills/.../clean-code-ddd-python/SKILL.md` | `docs/standards/python/clean-code-ddd.md` | Merge SKILL depth + `reference.md` |
| `skills/.../python-code-analysis/SKILL.md` | `docs/standards/python/code-analysis.md` | Operational commands stay in skill |
| `skills/.../imda-agentic-ai-governance/SKILL.md` | `docs/standards/agentic/imda-agentic-ai-governance.md` | Merge SKILL depth + `reference.md` |

### 5.4 Secrets

**Problem:** Template or drift tooling touches secrets.

**Mitigations:**

- Manifest **`never_manage`**: `.env`, secrets dirs (exclude from diff/bootstrap)
- **`.env.example` only** with placeholders
- Drift reports: paths + summaries for sensitive globs, not full content
- Align with AI-SDLC charter: no real secrets in chat, commits, or reports

---

## 6. Operating loop

```text
                    ┌─────────────────────┐
                    │  template-repo      │
                    │  (tagged v1.x.y)    │
                    └──────────┬──────────┘
                               │ submodule @ tag
                               ▼
┌──────────────┐    warn/fail   ┌──────────────────────┐
│ make ci-native│ ────────────►│ check-standards       │
│ + check-standards             │ manifest + profiles   │
└──────────────┘                └──────────┬───────────┘
                                           │
         ┌─────────────────────────────────┼─────────────────────────────────┐
         ▼                                 ▼                                 ▼
    clean / stale                      diverged                    contribution_candidate
    (notice)                           (warn → fail)               → contributions/inbox/
         │                                 │                                 │
         └─────────────────────────────────┴─────────────────────────────────┘
                                           │
                              template owner: accept → tag → projects bump pin
```

### Developer commands (target)

| Command | Purpose |
|---------|---------|
| `standards init` | Add submodule, profiles, pin, overlay dirs; **copy** enabled profile paths |
| `standards upgrade` | Bump submodule to new tag; **re-copy** managed paths; merge Makefile fragments |
| `check-standards` | Diff copies vs `standards/` @ pin; classify; CI artifact |
| `standards contribute` | Optional: open template issue from report (agent may summarize diff) |

---

## 7. Drift report schema (draft)

Human-readable `standards-drift-report.md` + machine `standards-drift-report.yaml`:

```yaml
project: lms-ai
standards_version: "1.3.0"
submodule_commit: abc123
template_latest: "1.4.0"
profiles: [core, python, agentic]
status: warn  # clean | stale | diverged | contribution_suggested
ci_policy: warn  # warn | fail

findings:
  - type: stale
    message: Template v1.4.0 available; project pinned at 1.3.0

  - type: diverged
    path: .cursor/rules/generic/security-and-hardening.md
    reference: standards/cursor/rules/generic/security-and-hardening.md
    classification: local_edit

  - type: contribution_candidate
    path: .cursor/rules/generic/api-and-interface-design.md
    summary: Added idempotency header convention
    suggested_action: template_inbox

contribution_inbox_path: contributions/inbox/2026-06-25-lms-ai.yaml
```

Template owner triage: **accept** (PR + tag + decision note) | **reject** (close + reason in `contributions/decisions/`).

---

## 8. Profile manifest (draft — to finalize)

| Profile | Purpose | Candidate contents (from LMS-AI) |
|---------|---------|----------------------------------|
| **core** | Every repo | AI-SDLC charter/change-log/traceability templates, GitHub issue/PR templates, traceability CI, generic ai-sdlc rules |
| **python** | Python services | `clean-code-ddd-python`, `python-code-analysis`, security/API/sonarqube generic rules, ruff/mypy/import-linter fragments |
| **agentic** | LLM / agents | `imda-agentic-ai-governance` skill, agent security standards doc |
| **frontend** | React/TS UI | `frontend-ui-engineering` rule |

**Rule:** Drift check runs only paths belonging to enabled profiles.

---

## 9. Submodule wiring and copy materialization (agreed)

### 9.1 Wiring

- Submodule root: **`standards/`** at product repo root → template repo @ tag (reference tree; not edited in place)
- **Copy materialization:** `standards init` / `upgrade` copies files from `standards/<path>` to `materialize_to` (e.g. `standards/cursor/rules/generic/foo.md` → `.cursor/rules/generic/foo.md`) for the union of enabled profiles
- **Cursor discovery:** normal paths — `.cursor/rules/generic/`, `.cursor/skills/generic/` hold real files (copies), not symlinks
- **Developer rule:** Edit managed generics only via template upstream PR + `standards upgrade`, or move changes to overlay (`.cursor/rules/<project>/`). Local edits to copies → **diverged** finding

### 9.2 Copy-based drift (`check-standards`)

Deterministic at build time — **no agent required** for detection.

```text
For each path in manifest ∩ enabled_profiles:
  expected  = read from standards/ @ .standards-version (submodule commit)
  actual    = read from materialized copy (e.g. .cursor/rules/generic/...)
  compare   = hash or diff
```

| Check | Purpose |
|-------|---------|
| Pin integrity | Submodule checkout matches `.standards-version` tag |
| Profile filter | Only paths for profiles in `.standards-profiles` |
| Pairwise diff | Managed copy vs submodule reference at same relative path |
| Missing | Path in manifest for enabled profile but no copy in project |
| Orphan | Copy exists at managed location but not in manifest (warn) |
| Overlay exclude | `.cursor/rules/<project>/`, `docs/ai-sdlc/CHARTER.md` — never compared |
| `never_manage` | `.env`, secrets dirs — excluded from bootstrap and diff |

**Contribution candidate:** any `diverged` finding on a managed generic path is classified `contribution_candidate` (rule-based). Optional agent summary when running `standards contribute` — not in CI hot path.

**Day-one pilot (proposed warn rules):** `stale` → warn; `diverged` → warn; `missing` → warn; `clean` → pass; overlay → ignore. Fail mode (phase 3) applies only to `diverged` on managed paths.

### 9.3 Copy vs symlink (decided)

| | **Copy (agreed)** | Symlink (rejected for v1) |
|---|-------------------|---------------------------|
| After submodule bump | Re-run `standards upgrade` to refresh copies | Content follows submodule automatically |
| Local generic edit | Clear **diverged** diff vs pin | Risk edits land inside submodule working tree |
| Drift detection | Two trees, straightforward diff | Symlink integrity + submodule edit checks |
| Cursor / Windows | No symlink edge cases | Tooling variance |

---

## 10. Rollout phases

**Detailed plan:** [template-standards-plan.md](template-standards-plan.md) (verification-first).

| Phase | Summary | Exit signal |
|-------|---------|-------------|
| **0** | Governance lock (owner, package, org-tier defer) | §15.9 decisions filled |
| **1** | **Mechanics lab** — fixture + `check-standards` + copy in LMS-AI | T1–T10 tests pass |
| **2** | Template repo `v1.0.0` | Tag + clone verification |
| **3** | LMS-AI pilot submodule + warn CI + one upgrade | V3.1–V3.7 pass |
| **4** | Contribution loop (GitHub issues) | One E2E contribution shipped |
| **5** | Fail mode on diverged managed paths | CI blocks generic drift |
| **6** | Second repo bootstrap; org tiers optional | Not LMS-shaped |

---

## 11. Extraction map (LMS-AI → template repo)

**Move to template repo:**

- `.cursor/templates/ai-sdlc/**`
- `.cursor/rules/generic/**`
- `.cursor/skills/generic/**`
- Generic GitHub traceability assets (from template folder)

**Keep in LMS-AI only:**

- `.cursor/rules/lms-ai/**`, `.cursor/skills/lms-ai/**`
- `docs/ai-sdlc/CHARTER.md` (instantiated)
- Domain docs (`MVP.md`, bounded contexts, app code)

**After extraction:** LMS-AI consumes template via submodule; overlay unchanged.

---

## 12. AI-Led SDLC relationship

Template repo encodes **option 1 (AI assists humans)** gates:

- Charter autonomy levels
- Traceability (issue → PR → REQ)
- Change log append-only
- CI quality gates before merge

Future **AI-Led** stages can raise autonomy in **per-project CHARTER** without changing the drift/submodule machinery — only manifest profiles and fail/warn policy.

---

## 13. Conversation log (summary)

| Session | Topics |
|---------|--------|
| Jun 2026 — initial | Separate template repo feasibility; LMS-AI already has generic vs lms-ai split and `.cursor/templates/ai-sdlc/` |
| Jun 2026 — drift | Build-time check; contribution reports to template owner; manifest; pin version; warn-first |
| Jun 2026 — cohesion | Over-templating → profiles; Cursor vs portable → docs/standards + thin rules; secrets → never_manage |
| Jun 2026 — decisions | **Warn first rollout**; **submodule for managed generics**; classified reports; agreed mitigations |
| Jun 2026 — profiles | Over-templating → **canonical store + profile indexes**; monolithic submodule; orthogonal profiles + required `core` |
| Jun 2026 — materialization | **Copy-on-init/upgrade** (not symlink); deterministic `check-standards` diff; no agent for drift detection |
| Jun 2026 — portable layer | **Two-layer model** — `docs/standards/` SOT; thin Cursor enforcers; paired manifest entries; link-integrity checks |
| Jun 2026 — backlog | §15 open items prioritized; governance + org-level standards (architecture/technology/business); simplification packages |
| Jun 2026 — plan | [template-standards-plan.md](template-standards-plan.md) — verification-first phases 0–6 |
| Jun 2026 — Phase 0 | Governance locked — [GOVERNANCE.md](template-standards/GOVERNANCE.md); maintainers own template; Minimal package; Option D org tiers |
| Jun 2026 — Phase 1 | Mechanics lab — `check-standards`, materialize, profiles, T1–T10 pass ([TEST-RESULTS.md](../scripts/standards-fixture/TEST-RESULTS.md)) |
| Jun 2026 — Phase 2 | Template repo `../org-ai-standards` @ `v1.0.0`; V2.1–V2.4 pass |
| Jun 2026 — Phase 3 | LMS-AI `standards/` submodule pilot @ `v1.0.1`; warn-only CI; upgrade cycle |

---

## 15. Open backlog (prioritized)

**Purpose:** Single ordered list of unresolved decisions from this discussion. Use to decide whether the full model can be **simplified for v1** before implementation.

**Priority lens:** Template and standards **governance** (who owns what, how change flows, how projects adopt and upgrade) is the highest-leverage block. Mechanics (scripts, CI rules, extraction) follow once governance is clear.

### Priority map (at a glance)

```text
P0  Governance model          ← decide first (this section §15.1–15.2)
P1  Lifecycle commands         init · upgrade · apply · contribute
P2  Profiles                  list · membership · add new profile
P3  Enforcement               check-standards · warn→fail · inbox
P4  Content & extraction      docs/standards split · LMS-AI move · v1.0 scope
P5  Rollout                    pilot · second repo · fail mode
```

---

### §15.1 P0 — Governance model (decide first)

| # | Open item | Question to answer | Full model (current spec) | Simplified v1 option |
|---|-----------|-------------------|---------------------------|----------------------|
| G1 | **Template ownership** | Who owns the template repo, merges, and tags? Single platform team vs guild? | Named **template owner** in README; PR + review for all template changes | Same — non-negotiable minimum |
| G2 | **Change authority** | Who can approve a new/changed standard? | Template owner + optional reviewers per **tier** (see G6) | Template owner only; expand tiers later |
| G3 | **Release cadence** | How often are template tags cut? | Semver tags; `CHANGELOG.md`; projects pin explicitly | Monthly or on-demand tags; semver still |
| G4 | **Pin bump authority** | Who may bump `.standards-version` and run `standards upgrade` in a product repo? | Project lead or delegated maintainer; PR required; CI runs `check-standards` | Any merge approver; document in CHARTER |
| G5 | **Contribution vs divergence** | When a project improves a generic standard, what happens? | Drift report → `contribution_candidate` → inbox → owner accept/reject → tag → projects bump | Same loop; inbox = GitHub issues only (no committed YAML) |
| G6 | **Standards tiers** | How do **delivery** standards relate to **organization** standards? | See §15.2 — layered tiers with optional enablement | **Defer org tiers to v1.1**; delivery template only |
| G7 | **Project overlay authority** | Who owns `.cursor/rules/<project>/` and `docs/ai-sdlc/CHARTER.md`? | Project team; never drift-checked vs template | Same |
| G8 | **Escalation** | Unmanaged divergence at fail mode — who grants exception? | Time-boxed waiver file in repo (e.g. `standards-waiver.yaml`) with expiry + owner approval | No waivers in v1; fix or overlay |

**Governance loop (target — all tiers):**

```text
  propose change
       │
       ▼
  template PR (+ tier reviewers if org standard)
       │
       ▼
  merge → semver tag → CHANGELOG
       │
       ├──► projects: standards upgrade (bump pin + re-copy)
       │
       └──► drift reports from projects still on old pin → stale finding
```

---

### §15.2 P0 — Organization-level standards (architecture · technology · business)

**New requirement (not yet in agreed decisions):** Mechanisms to include **organization-level** standards — not just repo delivery mechanics (AI-SDLC, Python, agentic, frontend).

| Tier | Typical content | Audience | Example topics |
|------|-----------------|----------|----------------|
| **Business** | Product principles, compliance, data classification | PM, eng leads | PII handling policy, approval workflows |
| **Architecture** | Reference architectures, integration patterns, ADR templates | Architects, senior eng | Event-driven boundaries, API gateway pattern |
| **Technology** | Approved stacks, versions, cloud guardrails | Platform, SRE | Azure regions, logging baseline, identity |
| **Delivery** *(agreed)* | AI-SDLC, Cursor rules, profiles `core`/`python`/… | All AI-assisted repos | Traceability, security rule, DDD skill |

**Open item G6 — choose one layering model:**

| Option | Shape | Pros | Cons | Simplified? |
|--------|-------|------|------|-------------|
| **A. Org profiles in same repo** | `profiles/org-architecture`, `org-technology`, `org-business` under same template repo; optional in `.standards-profiles` | One submodule, one manifest, one upgrade | Org and delivery coupled in release cadence | Medium |
| **B. Two submodules** | `standards/` (delivery template) + `org-standards/` (architecture/tech/business) @ separate pins | Independent cadence and owners per repo | Two pins, two upgrade commands, version matrix | No |
| **C. Tier field in manifest** | Same repo; `tier: delivery \| org-architecture \| org-technology \| org-business`; owners per tier in CODEOWNERS | One repo; clear RACI per path | Still one release tag affects all tiers | Medium |
| **D. Doc-only org handbook (defer)** | Org standards in separate handbook repo or wiki; linked from CHARTER, **not** in drift machinery | Fastest v1; no new machinery | Agents may not load org rules reliably; manual linking | **Yes — simplest v1** |
| **E. CHARTER + overlay only** | Org standards as project or division docs; thin rules in `.cursor/rules/<org>/` | No template repo change | Per-project duplication; weak central governance | Simplest but weak |

**Recommended sequencing:**

1. **v1:** Delivery template only (`core`, `python`, `agentic`, `frontend`) — prove governance loop on LMS-AI.
2. **v1.1:** Add **Option A or C** for org tiers — same repo, new profiles, `docs/standards/org/{architecture,technology,business}/`.
3. **v2:** If org release cadence must diverge from delivery → **Option B** (second submodule).

**Open sub-items for org standards:**

| # | Item | Notes |
|---|------|-------|
| O1 | Which tiers are mandatory vs optional per project? | e.g. all repos `core` + `org-technology`; architecture optional for small services |
| O2 | Do org standards get Cursor enforcers or doc-only? | Business/architecture often doc-only; technology may need thin rules |
| O3 | Who approves org-tier PRs? | Architecture review board vs template owner |
| O4 | Materialization paths | `docs/standards/org/architecture/` copied like delivery docs |
| O5 | Drift scope | `check-standards` includes enabled org profiles same as delivery |

---

### §15.3 P1 — Lifecycle: apply · upgrade · change

| # | Open item | Question | Full model | Simplified v1 |
|---|-----------|----------|------------|---------------|
| L1 | **`standards init`** | Exact steps for new repo vs adopting existing (LMS-AI)? | Submodule + pin + profiles + copy + overlay dirs + Makefile fragments | LMS-AI manual pilot checklist before script |
| L2 | **`standards upgrade`** | Merge strategy when local copies were intentionally customized? | Re-copy overwrites managed paths; overlay untouched; diverged → warn | Same; document "move to overlay first" |
| L3 | **Apply new profile** | How to add e.g. `frontend` to existing project? | Edit `.standards-profiles` → `standards upgrade` → copies new paths | Same |
| L4 | **Remove profile** | What happens to materialized files when profile removed? | `upgrade --prune` deletes managed copies not in new profile set (with confirm) | Manual delete in v1 |
| L5 | **Breaking template changes** | Major version bump rules? | Semver: breaking manifest path removal = MAJOR | Document in template README |
| L6 | **Bootstrap scripts** | Shell vs Make vs CI job? | `bootstrap/standards-init.sh` + `standards-upgrade.sh` in template repo | Make targets wrapping scripts |

---

### §15.4 P2 — Profiles

| # | Open item | Question | Full model | Simplified v1 |
|---|-----------|----------|------------|---------------|
| P1 | **Profile list** | Final set for delivery template? | `core` (required), `python`, `agentic`, `frontend` orthogonal | Same four; no org profiles until v1.1 |
| P2 | **Profile membership table** | Every file → profile(s) | Complete table in §8 + §5.3 extraction map | LMS-AI pilot set only |
| P3 | **Add new profile** | Process for e.g. `data` or `mobile` | New `profiles/<name>/profile.yaml` + template tag + CHANGELOG; projects opt in | Owner PR + tag; no generator |
| P4 | **`extends` depth** | Allow `python extends core` only, or chains? | One level `extends` recommended | `core` only as parent |
| P5 | **Presets** | Documented aliases (`fullstack` = all delivery profiles)? | Convenience in README only | Skip presets in v1 |

---

### §15.5 P3 — Enforcement & contribution

| # | Open item | Question | Full model | Simplified v1 |
|---|-----------|----------|------------|---------------|
| E1 | **Contribution inbox** | GitHub issues vs `contributions/inbox/` commits? | Committed YAML for audit trail + optional issue link | **GitHub issues only** |
| E2 | **Day-one warn rules** | LMS-AI pilot CI behavior | `stale`, `diverged`, `missing` → warn; overlay ignore (§9.2) | Same |
| E3 | **Warn → fail criteria** | When to flip? | After N projects on stable tag OR fixed date OR manual flag in template | Manual flag in template repo when LMS-AI stable |
| E4 | **`check-standards` location** | Script in template vs product wrapper? | Canonical in template `scripts/`; product `make check-standards` invokes it | Copy script into LMS-AI `scripts/` for pilot |
| E5 | **§5.3 link checks** | Include in v1? | Link integrity + pair completeness | Defer fat-enforcer nudge to v1.1 |
| E6 | **Drift report artifact** | CI uploads YAML? | `standards-drift-report.yaml` as CI artifact | Markdown stdout only in v1 |

---

### §15.6 P4 — Content & extraction

| # | Open item | Question | Full model | Simplified v1 |
|---|-----------|----------|------------|---------------|
| C1 | **Extraction cadence** | Fat rules → `docs/standards/` when? | `core` + `python` at template v1.0; doc-first for new | **Defer extraction** — ship fat rules in template v1.0; extract in v1.1 |
| C2 | **Thin enforcer migration** | Required before pilot? | Paired doc + thin rule per §5.3 | Keep fat rules; add `docs/standards/` incrementally |
| C3 | **Template repo name & home** | GitLab group, visibility | TBD | Decide before phase 0 |
| C4 | **LMS-AI extraction** | Big-bang vs incremental submodule | Phase 0 extracts generics; LMS-AI keeps working overlays | Submodule alongside existing files first; remove duplicates later |
| C5 | **AI-SDLC templates path** | Move `.cursor/templates/ai-sdlc/` → `docs/ai-sdlc/templates/` | As spec §3 | Can alias old path during transition |

---

### §15.7 P5 — Rollout

| # | Open item | Question | Full model | Simplified v1 |
|---|-----------|----------|------------|---------------|
| R1 | **Phase 0 scope** | What ships in template v1.0.0? | Manifest, 4 profiles, bootstrap scripts, check-standards, LMS-AI generics | Manifest + profiles + check-standards warn; scripts manual |
| R2 | **LMS-AI pilot** | First adopter criteria | Submodule + warn CI + one successful upgrade cycle | Same |
| R3 | **Second project** | Validates not LMS-shaped | Phase 4 | Defer until LMS-AI pilot complete |
| R4 | **Fail mode (phase 3)** | Org-wide or per-repo? | Per-repo `ci_policy` in report or repo config | LMS-AI first |

---

### §15.8 Simplification packages (choose your weight class)

Use this to pick an overall v1 scope without re-deciding every row above.

| Package | Includes | Defers | Best when |
|---------|----------|--------|-----------|
| **Minimal** | G1–G4 governance doc; delivery template repo; submodule + copy; `check-standards` warn; 4 delivery profiles; fat rules (no docs/standards split); GitHub issues for contributions; org standards = links in CHARTER (Option D) | Org profiles, thin enforcers, prune, committed inbox, fail mode, bootstrap scripts | Prove governance loop on one repo fast |
| **Standard** *(current spec lean)* | Minimal + `docs/standards/` extraction for core/python; paired manifest; link integrity checks; bootstrap scripts; org tiers as profiles v1.1 | Second submodule, fail mode, waivers | Balance audit readiness and effort |
| **Full** | Everything in §1–§14 as written; org tiers in manifest; committed contribution inbox; phased fail rollout | Nothing significant | Multi-repo rollout with compliance needs |

**Suggested default for your stated priority:** Start **Minimal** on mechanics, but **decide P0 governance (§15.1–15.2) in full** — especially G6 org-tier model — so v1 does not block v1.1 org standards.

---

### §15.9 Decision log (fill as you decide)

| ID | Decision | Date | Notes |
|----|----------|------|-------|
| G6 | **Option D** — org standards via CHARTER/doc links; org profiles in v1.1 | 2026-06-26 | A/C in v1.1 if needed |
| Package | **Minimal** | 2026-06-26 | Prove loop on LMS-AI first |
| G4 | **Repository maintainers via PR** | 2026-06-26 | AI blocked unless user requests |
| G5 | **GitHub issues** on template repo | 2026-06-26 | No committed inbox YAML in v1 |
| E3 | Fail after Phase 3 exit + owner sign-off | 2026-06-26 | Not time-based for v1 |
| C1 | **Defer** docs/standards extraction post-v1.0.0 | 2026-06-26 | Fat rules in template v1.0.0 |
| G1 | Template owner = **repository maintainers** | 2026-06-26 | Phase 0 confirmed |

---

## 16. References

- [AI-SDLC bootstrap README](../.cursor/templates/ai-sdlc/README.md)
- [Cursor guidance layout](../.cursor/README.md)
- [docs/ai-sdlc/](ai-sdlc/)
- [IMDA agentic governance skill](../.cursor/skills/generic/imda-agentic-ai-governance/SKILL.md)

---

*Last updated: Jun 2026 — §15 prioritized open backlog with governance and org-tier options; implementation not started.*
