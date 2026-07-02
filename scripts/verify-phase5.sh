#!/usr/bin/env bash
# Phase 5 verification (fail mode on diverged managed paths).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
FAIL=0

log() { printf '%s\n' "$*"; }
pass() { log "PASS  $1"; }
fail() { log "FAIL  $1"; FAIL=1; }

POLICY="$(tr -d '[:space:]' < .standards-ci-policy 2>/dev/null || echo fail)"
if [[ "$POLICY" != "fail" ]]; then
  fail "policy" "expected .standards-ci-policy=fail, got $POLICY"
fi

STANDARDS_ENV_BASE="STANDARDS_ROOT=$ROOT STANDARDS_REFERENCE=standards \
  STANDARDS_MANIFEST=standards/manifest.json \
  STANDARDS_VERSION_FILE=.standards-version \
  STANDARDS_LATEST_FILE=.standards-latest \
  STANDARDS_PROFILES_FILE=.standards-profiles"

log "=== V5.0 clean baseline ==="
if make check-standards >/tmp/v5-clean.out 2>&1; then
  if grep -q '"status": "clean"' /tmp/v5-clean.out; then
    pass "V5.0 baseline clean"
  else
    fail "V5.0" "not clean"
    cat /tmp/v5-clean.out
  fi
else
  fail "V5.0 baseline"
  cat /tmp/v5-clean.out
fi

log "=== V5.1 diverged fails (managed generic) ==="
TARGET="$ROOT/.cursor/rules/generic/code-simplification.md"
BACKUP="$(mktemp)"
cp "$TARGET" "$BACKUP"
echo "# phase5 drift test" >> "$TARGET"
set +e
make check-standards >/tmp/v5-diverged.out 2>&1
RC=$?
set -e
if [[ "$RC" -ne 0 ]] && grep -q '"status": "fail"' /tmp/v5-diverged.out && grep -q '"type": "diverged"' /tmp/v5-diverged.out; then
  pass "V5.1 diverged blocks check-standards"
else
  fail "V5.1" "rc=$RC expected fail on diverged"
  cat /tmp/v5-diverged.out
fi
cp "$BACKUP" "$TARGET"

log "=== V5.2 overlay edit passes ==="
OVERLAY="$ROOT/.cursor/rules/lms-ai/ai-sdlc-charter-lms-ai.md"
OB="$(mktemp)"
cp "$OVERLAY" "$OB"
echo "# phase5 overlay test" >> "$OVERLAY"
if make check-standards >/tmp/v5-overlay.out 2>&1; then
  if ! grep -q 'lms-ai' /tmp/v5-overlay.out; then
    pass "V5.2 overlay ignored by drift check"
  else
    fail "V5.2 overlay flagged"
  fi
else
  fail "V5.2 overlay should pass"
  cat /tmp/v5-overlay.out
fi
cp "$OB" "$OVERLAY"
rm "$OB"

log "=== V5.3 revert restores clean ==="
rm "$BACKUP"
if make check-standards >/tmp/v5-revert.out 2>&1; then
  if grep -q '"status": "clean"' /tmp/v5-revert.out; then
    pass "V5.3 revert restores clean"
  else
    fail "V5.3" "not clean after revert"
    cat /tmp/v5-revert.out
  fi
else
  fail "V5.3 revert"
  cat /tmp/v5-revert.out
fi

log "=== V5.3 stale warns only (non-blocking) ==="
LATEST_BACKUP="$(mktemp)"
cp .standards-latest "$LATEST_BACKUP"
printf '9.9.9\n' > .standards-latest
set +e
env $STANDARDS_ENV_BASE CI_POLICY=fail ./standards/scripts/check-standards.sh >/tmp/v5-stale.out 2>&1
STALE_RC=$?
set -e
cp "$LATEST_BACKUP" .standards-latest
rm "$LATEST_BACKUP"
if [[ "$STALE_RC" -eq 2 ]] && grep -q '"type": "stale"' /tmp/v5-stale.out && grep -q '"status": "warn"' /tmp/v5-stale.out; then
  pass "V5.3 stale warns (exit 2) not fail"
else
  fail "V5.3 stale" "rc=$STALE_RC"
  cat /tmp/v5-stale.out
fi

log "=== V5.1 make swallows stale exit 2 ==="
LATEST_SAVED="$(cat .standards-latest)"
printf '9.9.9\n' > .standards-latest
set +e
make check-standards >/tmp/v5-make-stale.out 2>&1
MAKE_RC=$?
set -e
printf '%s\n' "$LATEST_SAVED" > .standards-latest
if [[ "$MAKE_RC" -eq 0 ]] && grep -q 'warn (non-blocking)' /tmp/v5-make-stale.out; then
  pass "V5.1 make allows stale warn"
else
  fail "V5.1 make stale" "rc=$MAKE_RC"
  cat /tmp/v5-make-stale.out
fi

exit "$FAIL"
