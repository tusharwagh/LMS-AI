#!/usr/bin/env bash
# Phase 4 verification (LMS-AI contribution loop consumer).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
FAIL=0

log() { printf '%s\n' "$*"; }
pass() { log "PASS  $1"; }
fail() { log "FAIL  $1"; FAIL=1; }

log "=== V4.1 check-standards clean @ pin ==="
if make check-standards >/tmp/v4-check.out 2>&1; then
  if grep -q '"status": "clean"' /tmp/v4-check.out; then
    pass "V4.1 clean after upgrade"
  else
    fail "V4.1" "not clean"
    cat /tmp/v4-check.out
  fi
else
  fail "V4.1"
  cat /tmp/v4-check.out
fi

log "=== V4.1 standards-contribute script ==="
if [[ -x standards/scripts/standards-contribute.sh ]]; then
  pass "V4.1 contribute helper in submodule"
else
  fail "V4.1 contribute missing"
fi

log "=== V4.2 contribute with no drift ==="
if make standards-contribute 2>&1 | grep -q 'No contribution candidates'; then
  pass "V4.2 no-candidate message"
else
  fail "V4.2"
fi

log "=== V4.3 diverged warns (non-blocking) ==="
TARGET="$ROOT/.cursor/rules/generic/code-simplification.md"
BACKUP="$(mktemp)"
cp "$TARGET" "$BACKUP"
echo "# drift test" >> "$TARGET"
set +e
make check-standards >/tmp/v4-warn.out 2>&1
RC=$?
set -e
cp "$BACKUP" "$TARGET"
rm "$BACKUP"
if [[ "$RC" -eq 0 ]] && grep -q '"type": "diverged"' /tmp/v4-warn.out; then
  pass "V4.3 warn-only on diverged"
else
  fail "V4.3" "rc=$RC"
  cat /tmp/v4-warn.out
fi

log "=== V4.3 contribute generates body from drift ==="
cp "$TARGET" "$BACKUP"
echo "# drift test" >> "$TARGET"
if make standards-contribute >/tmp/v4-contrib.out 2>&1; then
  if grep -q 'Affected managed paths' /tmp/v4-contrib.out; then
    pass "V4.3 contribute body from drift"
  else
    fail "V4.3 contribute body"
  fi
else
  fail "V4.3 contribute"
fi
cp "$BACKUP" "$TARGET"
rm "$BACKUP"

log "=== V4.1 pin version ==="
PIN="$(tr -d '[:space:]' < .standards-version)"
if [[ "$PIN" == "1.0.2" ]]; then
  pass "V4.1 pinned at 1.0.2"
else
  fail "V4.1 pin" "got $PIN (run make standards-upgrade VERSION=1.0.2)"
fi

exit "$FAIL"
