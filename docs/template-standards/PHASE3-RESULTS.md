# Phase 3 verification results — LMS-AI pilot

**Run:** 2026-06-27  
**Submodule:** `standards/` @ `v1.0.1`  
**Pin:** `.standards-version` = `1.0.1`

| ID | Check | Result |
|----|-------|--------|
| V3.1 | `make check-standards` clean after materialize | PASS |
| V3.2 | Diverged generic → warn (non-blocking) | PASS |
| V3.3 | Overlay edits ignored | PASS |
| V3.4 | CHARTER excluded from manifest materialize | PASS |
| V3.5 | Upgrade `1.0.0` → `1.0.1` | PASS |
| V3.6 | Cursor paths present | PASS |
| V3.7 | `make ci-native` | Run manually before merge |

## Commands

```bash
git submodule update --init standards
make standards-materialize
make check-standards
make standards-upgrade VERSION=1.0.1   # when template releases
make verify-phase3
```

## CI note

`.gitmodules` currently uses a relative path (`../org-ai-standards`). GitHub Actions needs a published remote URL and `submodules: recursive` checkout (configured in `.github/workflows/ci.yml`). Until the template repo is pushed, CI skips drift check when `standards/manifest.json` is absent.
