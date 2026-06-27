# Template standards — implementation plan

**Status:** Active plan (Jun 2026)  
**Prerequisite spec:** [template-standards-research.md](template-standards-research.md)  
**Principle:** **Test and verify mechanics before** creating the separate template repo or changing LMS-AI CI policy.

**v1 scope:** **Minimal package** (see research §15.8) — delivery profiles only; org tiers deferred; fat rules OK; warn-only CI first.

---

## Overview

```text
Phase 0  Governance lock          → exit: RACI + package chosen
Phase 1  Mechanics lab (local)    → exit: check-standards proven on fixture data
Phase 2  Template repo v1.0.0     → exit: tagged repo; manifest + profiles complete
Phase 3  LMS-AI pilot (warn)      → exit: submodule + copy + CI warn; one upgrade cycle
Phase 4  Contribution loop        → exit: one end-to-end contribution triaged
Phase 5  Fail mode                → exit: diverged managed paths fail CI on LMS-AI
Phase 6  Scale-out                → exit: second repo bootstrapped; org tiers (optional)
```

Each phase has **deliverables**, **verification steps**, and **exit criteria**. Do not start the next phase until exit criteria pass.

---

## Phase 0 — Governance lock

**Goal:** Decide who owns standards and how change flows — without writing tooling yet.

**Duration:** 1 discussion session + short governance doc.

### Deliverables

| # | Deliverable | Owner |
|---|-------------|-------|
| 0.1 | Template owner named (person or team) | Sponsor |
| 0.2 | Pin bump authority for LMS-AI documented in `docs/ai-sdlc/CHARTER.md` | Project lead |
| 0.3 | v1 package choice: **Minimal** / Standard / Full | Template owner |
| 0.4 | Org tiers decision for v1: recommend **Option D** (CHARTER links; org profiles in v1.1) | Template owner |
| 0.5 | Contribution inbox: **GitHub issues** on template repo (v1) | Template owner |
| 0.6 | One-page `GOVERNANCE.md` in future template repo (can draft in LMS-AI `docs/` first) | Template owner |

### Verification

- [x] Every row in research §15.9 decision log has an entry for G4, G5, G6, Package
- [x] CHARTER § human gates mentions who runs `standards upgrade`
- [x] Team agrees: unmanaged generic edits → overlay or upstream PR (not silent drift) — documented in GOVERNANCE §4.2 and CHARTER §4

### Exit criteria

**Phase 0 complete** when governance doc exists and §15.9 rows G4, G5, G6, Package are filled.

**Status: complete (2026-06-26).** Next: [Phase 1 — Mechanics lab](#phase-1--mechanics-lab-verify-before-separate-repo).

---

## Phase 1 — Mechanics lab (verify before separate repo)

**Goal:** Prove `manifest` + `profiles` + `check-standards` + **copy materialization** work on **fixture data inside LMS-AI** — no submodule, no new repo yet.

**Why first:** Cheapest way to validate drift classification, profile filtering, and copy paths before extraction and CI commitment.

### Deliverables

| # | Deliverable | Location (pilot) |
|---|-------------|------------------|
| 1.1 | Profile indexes for `core`, `python`, `agentic`, `frontend` | `scripts/standards-fixture/profiles/` |
| 1.2 | Generated or hand-written `manifest.json` from indexes | `scripts/standards-fixture/manifest.json` |
| 1.3 | Reference tree (simulates template @ tag) | `scripts/standards-fixture/reference/` — copy of current `.cursor/rules/generic`, `.cursor/skills/generic`, `.cursor/templates/ai-sdlc` |
| 1.4 | `check-standards.sh` | `scripts/check-standards.sh` |
| 1.5 | `standards-materialize.sh` (copy union of profiles) | `scripts/standards-materialize.sh` |
| 1.6 | Fixture config | `.standards-profiles.fixture`, `.standards-version.fixture` |
| 1.7 | Test cases document | `scripts/standards-fixture/README.md` |

### Build reference fixture

Populate `scripts/standards-fixture/reference/` from LMS-AI today:

```text
reference/
├── cursor/rules/generic/       ← from .cursor/rules/generic/
├── cursor/skills/generic/      ← from .cursor/skills/generic/
├── docs/ai-sdlc/templates/     ← from .cursor/templates/ai-sdlc/
└── profiles/                   ← profile.yaml files
```

Pin fixture version: e.g. `.standards-version.fixture` = `fixture-0.1.0` (directory hash or fixed tag label).

### Verification tests (must all pass)

Run from repo root. Record results in `scripts/standards-fixture/TEST-RESULTS.md`.

| ID | Scenario | Setup | Expected `check-standards` result |
|----|----------|-------|-------------------------------------|
| T1 | **Clean** | Materialized copies match reference @ pin | `status: clean`, exit 0 |
| T2 | **Stale** | Reference label bumped; project pin unchanged | `type: stale`, warn |
| T3 | **Diverged** | Edit one file under `.cursor/rules/generic/` | `type: diverged`, warn |
| T4 | **Missing** | Delete one managed copy after materialize | `type: missing`, warn |
| T5 | **Overlay ignore** | Edit `.cursor/rules/lms-ai/*` | No finding on overlay paths |
| T6 | **Profile filter** | `.standards-profiles` = `core` only | No findings for `python`-only paths |
| T7 | **Contribution candidate** | Same as T3 | `classification: contribution_candidate` |
| T8 | **Materialize** | Run materialize for `core,python,agentic` | All manifest paths present at `materialize_to` |
| T9 | **Upgrade overwrite** | Diverged copy + re-materialize | Copy matches reference; diverged cleared |
| T10 | **never_manage** | `.env` not in manifest | Never copied or diffed |

### Commands (target)

```bash
# Materialize fixture reference into project paths (dry-run first)
make standards-materialize-fixture DRY_RUN=1

# Run drift check against fixture pin
make check-standards-fixture

# Run full fixture test suite
make test-standards-fixture
```

Add Makefile targets in Phase 1 implementation (not required to exist yet for this plan).

### Exit criteria

**Phase 1 complete** when:

- [x] T1–T10 pass and are recorded in `TEST-RESULTS.md`
- [x] Profile membership table covers all LMS-AI generic files (research §8 + §5.3)
- [x] Script runs in &lt;30s on LMS-AI tree (0.22s measured)
- [x] No dependency on a separate git repo or submodule

**Status: complete (2026-06-27).** Next: [Phase 2 — Template repository v1.0.0](#phase-2--template-repository-v100).

---

## Phase 2 — Template repository v1.0.0

**Goal:** Create the real template repo by **moving** proven fixture layout; tag `v1.0.0`.

**Start only after Phase 1 exit criteria pass.**

### Deliverables

| # | Deliverable |
|---|-------------|
| 2.1 | New repo `org-ai-standards` (name TBD) with structure from research §3 |
| 2.2 | Content extracted from LMS-AI (research §11) |
| 2.3 | `manifest.json` + four profile indexes (same as Phase 1, paths adjusted) |
| 2.4 | `scripts/check-standards.sh` and `bootstrap/standards-materialize.sh` (promoted from Phase 1) |
| 2.5 | `GOVERNANCE.md`, `README.md` (bootstrap, upgrade, ownership) |
| 2.6 | `CHANGELOG.md` + git tag **`v1.0.0`** |
| 2.7 | `.standards-profiles` example: `core,python,agentic,frontend` |

**Deferred in v1.0.0 (Minimal package):**

- `docs/standards/` extraction (fat rules stay in `cursor/rules/generic/`)
- Org profiles (`org-architecture`, etc.)
- Committed `contributions/inbox/` YAML
- Makefile fragment splicing automation

### Verification

| ID | Check |
|----|-------|
| V2.1 | Clone template repo; run `check-standards.sh` in **template repo itself** with self-reference → clean |
| V2.2 | Tag `v1.0.0` points at manifest + all profile paths |
| V2.3 | Second clone at tag: file count matches Phase 1 reference fixture |
| V2.4 | No LMS-AI domain nouns in generic paths (spot-check CHARTER templates vs rules) |
| V2.5 | Template repo CI: shellcheck on scripts; optional manifest schema validation |

### Exit criteria

**Phase 2 complete** when `v1.0.0` tag exists and V2.1–V2.5 pass.

**Status: complete (2026-06-27).** Template repo: `../org-ai-standards` · tag `v1.0.0` · [PHASE2-RESULTS](../org-ai-standards/docs/PHASE2-RESULTS.md). Next: [Phase 3 — LMS-AI pilot](#phase-3--lms-ai-pilot-warn-only).

---

## Phase 3 — LMS-AI pilot (warn-only)

**Goal:** Wire LMS-AI to template submodule + copy materialization + **warn** in CI — without removing working copies until verified.

### Approach: incremental (low risk)

```text
Step A  Add standards/ submodule @ v1.0.0 (reference only; keep existing .cursor paths)
Step B  Add .standards-version, .standards-profiles
Step C  Run materialize to sync copies; diff must be clean vs submodule
Step D  Add make check-standards → warn on drift
Step E  Add to CI (warn, non-blocking) alongside make ci-native
Step F  One deliberate standards upgrade cycle (v1.0.0 → v1.0.1 patch)
```

### Deliverables

| # | Deliverable |
|---|-------------|
| 3.1 | `standards/` submodule @ `v1.0.0` |
| 3.2 | `.standards-version`, `.standards-profiles` (`core,python,agentic,frontend`) |
| 3.3 | `make check-standards` (wraps template script) |
| 3.4 | `make standards-upgrade` (bump pin + re-materialize) |
| 3.5 | CI job: `check-standards` **allow_failure: true** or warn-only exit code |
| 3.6 | Remove duplicate source-of-truth only after T1 clean on real submodule (optional: delete old `.cursor/templates/ai-sdlc` from LMS-AI once template consumed) |
| 3.7 | Entry in `docs/ai-sdlc/CHANGELOG.md` |

### Verification

| ID | Check |
|----|-------|
| V3.1 | `make check-standards` → clean on main after materialize |
| V3.2 | Local edit to `.cursor/rules/generic/` → warn in CI |
| V3.3 | Edit to `.cursor/rules/lms-ai/` → no diverged finding |
| V3.4 | `docs/ai-sdlc/CHARTER.md` unchanged by materialize |
| V3.5 | Patch release `v1.0.1` on template; `make standards-upgrade` on LMS-AI; check-standards clean |
| V3.6 | Cursor still loads rules from `.cursor/rules/generic/` (manual smoke: agent sees rules) |
| V3.7 | `make ci-native` still passes |

### Exit criteria

**Phase 3 complete** when V3.1–V3.7 pass and one upgrade cycle (V3.5) is documented in CHANGELOG.

**Status: complete (2026-06-27).** See [PHASE3-RESULTS.md](template-standards/PHASE3-RESULTS.md). Next: [Phase 4 — Contribution loop](#phase-4--contribution-loop).

### CI submodule troubleshooting

If GitHub Actions fails with `not our ref <sha>` on `standards/`:

1. Push template first: `git push origin main --tags` in [org-ai-standards](https://github.com/tusharwagh/org-ai-standards)
2. Ensure `.gitmodules` uses `https://github.com/tusharwagh/org-ai-standards.git` (not a relative path)
3. Re-run CI

Detail: [template-standards/PHASE3-RESULTS.md](template-standards/PHASE3-RESULTS.md) · template [docs/RELEASE.md](https://github.com/tusharwagh/org-ai-standards/blob/main/docs/RELEASE.md)

---

## Phase 4 — Contribution loop

**Goal:** Prove project improvement → template owner → tag → projects bump.

### Deliverables

| # | Deliverable |
|---|-------------|
| 4.1 | GitHub issue template on template repo: "Standard contribution" |
| 4.2 | `standards contribute` helper (optional): opens issue from drift report summary |
| 4.3 | One **real or dry-run** contribution: LMS-AI diverged fix → issue → template PR → `v1.0.2` |
| 4.4 | `contributions/decisions/` note for accept/reject (template repo) |

### Verification

| ID | Check |
|----|-------|
| V4.1 | End-to-end: contribution merged → tag → LMS-AI upgrade → clean |
| V4.2 | Rejected contribution documented with reason |
| V4.3 | Product delivery not blocked while contribution pending (warn only) |

### Exit criteria

**Phase 4 complete** when one accepted contribution shipped through the full loop (V4.1).

---

## Phase 5 — Fail mode (LMS-AI)

**Goal:** Unmanaged divergence on **managed generic copies** fails CI.

### Deliverables

| # | Deliverable |
|---|-------------|
| 5.1 | Template or LMS-AI config: `ci_policy: fail` for diverged (research §9.2) |
| 5.2 | CI updated: `check-standards` blocking on diverged |
| 5.3 | Stale/missing remain **warn** initially (optional: promote later) |
| 5.4 | Runbook: fix diverged (revert / overlay / upstream PR) |

### Verification

| ID | Check |
|----|-------|
| V5.1 | PR with intentional generic edit fails CI |
| V5.2 | PR with overlay-only edit passes |
| V5.3 | Revert or upstream fix restores green |

### Exit criteria

**Phase 5 complete** when V5.1–V5.3 pass and team has used runbook at least once.

---

## Phase 6 — Scale-out

**Goal:** Validate template is not LMS-shaped; optional org tiers.

### Deliverables

| # | Deliverable |
|---|-------------|
| 6.1 | Bootstrap second repo from template (`standards init`) |
| 6.2 | Second repo uses different overlay name (not `lms-ai`) |
| 6.3 | Profile subset only (e.g. `core,python` without agentic) |
| 6.4 | (Optional v1.1) Org profiles: `org-technology`, `org-architecture`, `org-business` |
| 6.5 | (Optional) `docs/standards/` extraction for core/python per research §5.3 |

### Verification

| ID | Check |
|----|-------|
| V6.1 | Second repo check-standards clean after init |
| V6.2 | No LMS-AI paths required in generic layer |
| V6.3 | Template CHANGELOG documents breaking vs non-breaking releases |

### Exit criteria

**Phase 6 complete** when second repo pilot passes V6.1–V6.3.

---

## Profile membership (Phase 1 prerequisite)

Complete before locking `manifest.json`. LMS-AI mapping:

| Asset | Profile(s) |
|-------|------------|
| `.cursor/templates/ai-sdlc/**` | `core` |
| `rules/generic/ai-sdlc-*.md` | `core` |
| `rules/generic/code-simplification.md` | `core` |
| `rules/generic/doubt-driven-development.md` | `core` |
| `rules/generic/security-and-hardening.md` | `python` |
| `rules/generic/api-and-interface-design.md` | `python` |
| `rules/generic/sonarqube-quality.md` | `python` |
| `rules/generic/frontend-ui-engineering.md` | `frontend` |
| `skills/generic/clean-code-ddd-python/**` | `python` |
| `skills/generic/python-code-analysis/**` | `python` |
| `skills/generic/imda-agentic-ai-governance/**` | `agentic` |

**LMS-AI pilot profiles:** `core,python,agentic,frontend` (all four).

---

## What stays in LMS-AI always

| Path | Role |
|------|------|
| `.cursor/rules/lms-ai/` | Project overlay |
| `.cursor/skills/lms-ai/` | Project overlay |
| `docs/ai-sdlc/CHARTER.md` | Instantiated governance |
| `docs/ai-sdlc/CHANGELOG.md` | Append-only audit trail |
| `docs/ai-sdlc/TRACEABILITY.md` | Repo-specific traceability |
| Domain docs, app code | Product |

---

## Risk controls

| Risk | Mitigation in plan |
|------|-------------------|
| Big-bang break Cursor rules | Phase 1 fixture; Phase 3 incremental submodule |
| CI noise | Warn-only through Phase 3–4 |
| Duplicate content | Remove LMS-AI template folder only after V3.1 clean |
| Org standards scope creep | Phase 6.4 optional; Phase 0 locks Option D for v1 |
| Over-engineering | Minimal package; defer docs/standards split |

---

## Immediate next steps

1. ~~**Complete Phase 0**~~ — done 2026-06-26 ([GOVERNANCE.md](template-standards/GOVERNANCE.md)).
2. ~~**Complete Phase 1**~~ — done 2026-06-27 (`make test-standards-fixture`).
3. ~~**Complete Phase 2**~~ — done 2026-06-27 (`../org-ai-standards` @ `v1.0.0`).
4. ~~**Complete Phase 3**~~ — done 2026-06-27 (submodule pilot @ `v1.0.1`, [PHASE3-RESULTS](template-standards/PHASE3-RESULTS.md)).
5. **Start Phase 4** — contribution loop (GitHub issues on template repo).

---

## References

- [template-standards-research.md](template-standards-research.md) — spec, agreed decisions, §15 backlog
- [.cursor/README.md](../.cursor/README.md) — generic vs lms-ai layout
- [docs/ai-sdlc/CHARTER.md](ai-sdlc/CHARTER.md) — per-project governance

---

*Last updated: Jun 2026 — verification-first phased plan; Phase 1 is the active starting point after Phase 0 governance lock.*
