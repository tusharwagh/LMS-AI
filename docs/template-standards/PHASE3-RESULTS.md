# Phase 3 verification results — LMS-AI pilot

**Run:** 2026-06-27  
**Submodule:** `standards/` → https://github.com/tusharwagh/org-ai-standards.git  
**Pin:** `.standards-version` = `1.0.1`  
**Profiles:** `core,python,agentic,frontend`

## Verification

| ID | Check | Result |
|----|-------|--------|
| V3.1 | `make check-standards` clean after materialize | PASS |
| V3.2 | Diverged generic → warn (non-blocking) | PASS |
| V3.3 | Overlay edits ignored | PASS |
| V3.4 | CHARTER excluded from manifest materialize | PASS |
| V3.5 | Upgrade `1.0.0` → `1.0.1` | PASS |
| V3.6 | Cursor paths present | PASS |
| V3.7 | `make ci-native` | Run manually before merge |

```bash
make verify-phase3
```

## Integration layout

```text
standards/                    ← submodule @ v1.0.1 (reference only)
.standards-version            ← 1.0.1
.standards-latest             ← 1.0.1
.standards-profiles           ← core,python,agentic,frontend
.standards-copied-at          ← written on materialize/upgrade
.cursor/rules/generic/        ← managed copies (26 paths)
.cursor/rules/lms-ai/         ← overlay (never drift-checked)
docs/ai-sdlc/CHARTER.md       ← instantiated (never drift-checked)
```

## Commands

```bash
git submodule update --init standards
make standards-materialize
make check-standards
make standards-upgrade VERSION=1.0.1
```

## CI configuration

| Setting | Value |
|---------|-------|
| `.gitmodules` URL | `https://github.com/tusharwagh/org-ai-standards.git` |
| Checkout | `submodules: recursive` in `.github/workflows/ci.yml` |
| Drift step | Warn-only (`continue-on-error: true`; exit code 2 allowed) |

## CI fix: `not our ref adb35c5…` (2026-06-27)

**Symptom:**

```text
fatal: remote error: upload-pack: not our ref adb35c523560e315200a94eeef9db7edfcff2e60
Fetched in submodule path 'standards', but it did not contain adb35c5…
```

**Cause:** LMS-AI recorded submodule commit `adb35c5` (template v1.0.1) before that commit and tags were pushed to GitHub. Remote was still at `a13757e` (v1.0.0).

**Fix applied:**

1. Pushed `org-ai-standards`: `git push origin main --tags`
2. Updated `.gitmodules` from relative `../org-ai-standards` to HTTPS GitHub URL
3. `git submodule sync standards`

**Prevention:** Always follow [release order](https://github.com/tusharwagh/org-ai-standards/blob/main/docs/RELEASE.md):

1. Push template repo (`main` + tags)
2. Then bump LMS-AI submodule pointer and push

## Related

- [README.md](README.md) — LMS-AI standards hub
- [org-ai-standards PHASE3-RESULTS](https://github.com/tusharwagh/org-ai-standards/blob/main/docs/PHASE3-RESULTS.md)
- [org-ai-standards RELEASE.md](https://github.com/tusharwagh/org-ai-standards/blob/main/docs/RELEASE.md)
