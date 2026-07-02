# Template standards — refactor audit (pre–Phase 4)

**Goal:** Separate **LMS-AI product** files from **template / mechanics / duplicate** files before Phase 4.

**Current clutter:** Three overlapping layers for generic standards:

```text
org-ai-standards (GitHub)     ← source of truth
        │
        ▼ submodule
standards/                    ← reference @ pin (not edited in LMS)
        │
        ▼ materialize (copy)
.cursor/rules|skills/generic/ ← managed copies (Cursor + drift check)
.cursor/templates/ai-sdlc/    ← managed copies (same content as standards/docs/ai-sdlc/templates/)

PLUS legacy (Phase 1 lab):
scripts/standards-fixture/    ← duplicate of standards/ layout
scripts/check-standards.sh    ← duplicate of standards/scripts/
scripts/standards-materialize.sh ← duplicate of standards/bootstrap/
.standards-*.fixture          ← superseded by .standards-version etc.
```

---

## 1. Keep in LMS-AI (product)

These belong to the LMS project.

| Path | Role |
|------|------|
| `standards/` | Submodule pointer only — external template @ pin |
| `.gitmodules` | Submodule URL |
| `.standards-version`, `.standards-latest`, `.standards-profiles`, `.standards-copied-at` | Product pin + audit |
| `.cursor/rules/lms-ai/`, `.cursor/skills/lms-ai/` | **Project overlay** (never drift-checked) |
| `.cursor/rules/generic/`, `.cursor/skills/generic/` | **Managed copies** for Cursor (from materialize) |
| `.cursor/templates/ai-sdlc/` | **Managed copies** (from materialize; same as submodule templates) |
| `.cursor/README.md` | Documents generic vs lms-ai split |
| `docs/ai-sdlc/CHARTER.md`, `CHANGELOG.md`, `TRACEABILITY.md` | Instantiated governance |
| `docs/ai-sdlc/README.md`, `docs/ai-sdlc.md` | LMS AI-SDLC index |
| `docs/template-standards/README.md` | Thin LMS adoption hub (ops + links) |
| `docs/template-standards/PHASE3-RESULTS.md` | LMS pilot record |
| `scripts/standards-upgrade.sh` | Product upgrade wrapper |
| `scripts/verify-phase3.sh` | Optional; can archive after refactor |
| `scripts/check_pr_traceability.sh` | **Deployed** LMS script (`.github/workflows/`) |
| `.github/` | LMS CI (`check-standards` fails on diverged since Phase 5) |
| `Makefile` targets | `check-standards`, `standards-materialize`, `standards-upgrade` only |

**Note:** Managed copies under `.cursor/` stay in git so Cursor works without a post-clone materialize step. They are not a second source of truth — `standards/` @ pin is.

---

## 2. Remove from LMS-AI (Phase 1 lab — superseded)

Safe to **delete** from LMS-AI; history preserved in git. Equivalent lives in `org-ai-standards` or is obsolete.

| Path | Why remove | Replacement |
|------|------------|-------------|
| `scripts/standards-fixture/` | Phase 1 mechanics lab | `org-ai-standards`: `bootstrap/verify-template.sh`, `scripts/verify-phase2.sh` |
| `scripts/check-standards.sh` | Duplicate of submodule script | `standards/scripts/check-standards.sh` via `make check-standards` |
| `scripts/standards-materialize.sh` | Duplicate | `standards/bootstrap/standards-materialize.sh` |
| `.standards-version.fixture` | Test-only | `.standards-version` |
| `.standards-latest.fixture` | Test-only | `.standards-latest` |
| `.standards-profiles.fixture` | Test-only | `.standards-profiles` |

**Makefile targets to remove:**

- `standards-sync-fixture`
- `check-standards-fixture`
- `standards-materialize-fixture`
- `test-standards-fixture`

**`.gitignore` entries to remove:**

- `scripts/standards-fixture/reference/`
- `scripts/standards-fixture/test-workspace/`

---

## 3. Move to org-ai-standards (not LMS-owned)

| Path (today in LMS-AI) | Action | Target in org-ai-standards |
|------------------------|--------|----------------------------|
| `scripts/bootstrap-org-ai-standards.sh` | **Move** | `bootstrap/build-from-lms-ai.sh` or keep as maintainer-only script in template repo |
| `docs/template-standards-research.md` | **Move** (optional) | `docs/SPEC.md` — full spec |
| `docs/template-standards-plan.md` | **Split** | Rollout complete phases → template `docs/PLAN-LINK.md`; LMS keeps short adoption note only |
| `docs/template-standards/GOVERNANCE.md` | **Remove** from LMS | Canonical: `standards/GOVERNANCE.md` (submodule) |

**Do not duplicate GOVERNANCE in LMS** — link to submodule or GitHub.

---

## 4. Duplicate content map (same bytes, two paths)

Verified: `.cursor/rules/generic/` ≡ `standards/cursor/rules/generic/` after materialize.

| LMS managed copy | Submodule canonical | Count |
|------------------|---------------------|-------|
| `.cursor/rules/generic/*.md` | `standards/cursor/rules/generic/` | 8 rules |
| `.cursor/skills/generic/**` | `standards/cursor/skills/generic/` | 3 skills |
| `.cursor/templates/ai-sdlc/**` | `standards/docs/ai-sdlc/templates/` | ~15 files |

**Refactor options for `.cursor/templates/ai-sdlc/`:**

| Option | Pros | Cons |
|--------|------|------|
| **A. Keep in git** (current) | Clone works; Cursor works; CI drift-checks | Duplicate tree vs submodule |
| **B. Gitignore + materialize in CI** | Cleaner repo | Requires `git submodule update` + `make standards-materialize` on every clone/CI |
| **C. Keep rules/skills in git; drop templates from git** | Templates rarely edited by agents | Split model; bootstrap docs need update |

**Recommendation:** **Option A for Phase 4** — keep managed copies in git; remove Phase 1 lab and duplicate scripts only. Revisit Option B when a second product repo exists.

---

## 5. Docs consolidation (LMS after refactor)

**Keep (minimal LMS surface):**

```text
docs/
├── ai-sdlc/                    # instantiated governance (unchanged)
├── ai-sdlc.md                  # index
└── template-standards/
    ├── README.md               # ops hub (submodule, make targets, CI)
    ├── PHASE3-RESULTS.md       # pilot record
    └── REFACTOR-AUDIT.md       # this file
```

**Move or link-only:**

| File | Action |
|------|--------|
| `docs/template-standards-research.md` | Move to org-ai-standards **or** replace with one-line link in README |
| `docs/template-standards-plan.md` | Archive completed phases in org-ai-standards; LMS README links to GitHub |
| `docs/template-standards/GOVERNANCE.md` | Delete; link `standards/GOVERNANCE.md` |

---

## 6. Makefile after refactor

**Keep:**

```makefile
check-standards          → standards/scripts/check-standards.sh (STANDARDS_ENV)
standards-materialize    → standards/bootstrap/standards-materialize.sh
standards-upgrade        → scripts/standards-upgrade.sh
verify-phase3            → optional until archived
```

**Remove:** all `*-fixture` and `bootstrap-org-ai-standards` (moved to template repo).

**Optional:** `bootstrap-org-ai-standards` → document as `git clone` + manual steps in org-ai-standards README only.

---

## 7. What is NOT LMS code (mental model)

| Layer | Location | In LMS git? |
|-------|----------|-------------|
| Template source | github.com/tusharwagh/org-ai-standards | Submodule ref only |
| Reference checkout | `standards/` | Yes (submodule) |
| Managed copies | `.cursor/.../generic`, `.cursor/templates/ai-sdlc` | Yes (copies) |
| Project overlay | `.cursor/.../lms-ai`, `docs/ai-sdlc/CHARTER` | Yes |
| Phase 1 lab | `scripts/standards-fixture/` | **Remove** |
| Spec / cross-repo plan | research.md, plan.md | **Move or link** |

---

## 8. Recommended refactor steps (order)

| Step | Action | Status |
|------|--------|--------|
| 1 | Delete `scripts/standards-fixture/`, fixture files, duplicate scripts | Done 2026-06-27 |
| 2 | Trim Makefile + `.gitignore` | Done |
| 3 | Delete `docs/template-standards/GOVERNANCE.md`; update links → `standards/GOVERNANCE.md` | Done |
| 4 | Remove `bootstrap-org-ai-standards.sh` (obsolete; template repo exists) | Done |
| 5 | Move `template-standards-research.md` + trim `template-standards-plan.md` to org-ai-standards | Deferred — LMS keeps historical docs with links |
| 6 | Update `.cursor/README.md`, CHARTER, ai-sdlc docs | Done |
| 7 | (Optional) Gitignore `.cursor/templates/ai-sdlc` + CI materialize step | Deferred |

**Do not** remove `standards/` submodule or `.cursor/rules/lms-ai/`.

---

## 9. Phase 4 prerequisite

After steps 1–4, LMS-AI should have:

- One standards entry point: `docs/template-standards/README.md`
- One drift path: `make check-standards` → submodule scripts
- No Phase 1 fixture or duplicate shell scripts
- Governance read from `standards/GOVERNANCE.md` or GitHub

Then proceed to Phase 4 (contribution loop on org-ai-standards).
