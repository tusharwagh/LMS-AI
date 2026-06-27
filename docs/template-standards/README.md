# Template standards — LMS-AI

How this repo consumes the [org-ai-standards](https://github.com/tusharwagh/org-ai-standards) delivery template.

## Quick reference

| Item | Location |
|------|----------|
| Submodule (reference @ tag) | `standards/` |
| Pin | `.standards-version` (currently `1.0.1`) |
| Enabled profiles | `.standards-profiles` |
| Managed copies | `.cursor/rules/generic/`, `.cursor/skills/generic/`, `.cursor/templates/ai-sdlc/` |
| Project overlay | `.cursor/rules/lms-ai/`, `.cursor/skills/lms-ai/` |
| Instantiated governance | `docs/ai-sdlc/CHARTER.md`, `CHANGELOG.md` |

## Commands

```bash
git submodule update --init standards   # after clone
make standards-materialize            # copy standards/ → .cursor/
make check-standards                  # drift check (warn-only)
make standards-upgrade VERSION=1.0.1  # bump pin + re-materialize
make standards-contribute             # issue body from drift (v1.0.2+)
make verify-phase3                    # Phase 3 verification
make verify-phase4                    # Phase 4 verification
```

## Rules

- **Do not edit** managed generic copies in place — use `.cursor/rules/lms-ai/` overlay or upstream PR to [org-ai-standards](https://github.com/tusharwagh/org-ai-standards), then `make standards-upgrade`.
- **Template owner** cuts releases; **repository maintainers** bump pin via PR ([standards/GOVERNANCE.md](../../standards/GOVERNANCE.md) §5).

## CI

`.gitmodules` must use the **HTTPS** submodule URL so GitHub Actions can fetch it:

```ini
[submodule "standards"]
	path = standards
	url = https://github.com/tusharwagh/org-ai-standards.git
```

Workflow: `.github/workflows/ci.yml` — `submodules: recursive`, warn-only `check-standards`.

**Release order:** template repo must be pushed (`git push origin main --tags`) **before** LMS-AI records a new submodule commit. See [CI troubleshooting](#ci-troubleshooting) and org-ai-standards [RELEASE.md](https://github.com/tusharwagh/org-ai-standards/blob/main/docs/RELEASE.md).

## CI troubleshooting

### `not our ref <sha>` on submodule checkout

**Cause:** LMS-AI points at a submodule commit that is not on GitHub yet.

**Fix:**

1. In `org-ai-standards`: `git push origin main --tags`
2. Confirm: `git ls-remote https://github.com/tusharwagh/org-ai-standards.git refs/heads/main`
3. Re-run LMS-AI CI

### Relative submodule URL fails in CI

Use HTTPS in `.gitmodules`, not `../org-ai-standards`. Run `git submodule sync standards` after changing.

## Docs

| Doc | Purpose |
|-----|---------|
| [standards/GOVERNANCE.md](../../standards/GOVERNANCE.md) | Roles, change flow, contributions (submodule @ pin) |
| [PHASE3-RESULTS.md](PHASE3-RESULTS.md) | Pilot verification + CI fix |
| [REFACTOR-AUDIT.md](REFACTOR-AUDIT.md) | What stays in LMS vs template repo |
| [template-standards-plan.md](../template-standards-plan.md) | Rollout history (Phases 0–6) |
| [template-standards-research.md](../template-standards-research.md) | Original spec |

## Phase status

| Phase | Status |
|-------|--------|
| 0–3 | Complete (see [org-ai-standards](https://github.com/tusharwagh/org-ai-standards)) |
| 4 Contribution loop | Complete @ v1.0.2 — [PHASE4-RESULTS.md](PHASE4-RESULTS.md) |
| 5 Fail mode | Next |
