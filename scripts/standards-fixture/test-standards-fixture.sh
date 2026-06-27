#!/usr/bin/env bash
# Phase 1 fixture tests T1–T10 (see README.md).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FIXTURE="$ROOT/scripts/standards-fixture"
WORK="$FIXTURE/test-workspace"
PASS=0
FAIL=0
RESULTS="$FIXTURE/TEST-RESULTS.md"

cd "$ROOT"
chmod +x "$ROOT/scripts/check-standards.sh" "$ROOT/scripts/standards-materialize.sh" "$FIXTURE/sync-reference.sh"

log() { printf '%s\n' "$*"; }
pass() { PASS=$((PASS + 1)); log "PASS  $1"; }
fail() { FAIL=$((FAIL + 1)); log "FAIL  $1"; [[ -n "${2:-}" ]] && log "      $2"; }

run_check() {
  if (($# > 0)); then
    env "$@" "$ROOT/scripts/check-standards.sh" 2>/dev/null
  else
    "$ROOT/scripts/check-standards.sh" 2>/dev/null
  fi
}

run_check_expect_status() {
  local expected=$1
  shift
  set +e
  local out
  out="$(env "$@" "$ROOT/scripts/check-standards.sh" 2>/dev/null)"
  local code=$?
  set -e
  printf '%s' "$out"
  [[ "$code" -eq "$expected" ]]
}

json_field() {
  python3 -c 'import json,sys; d=json.load(sys.stdin); print(d'"$1"')'
}

setup_workspace() {
  rm -rf "$WORK"
  mkdir -p "$WORK"
  cp "$FIXTURE/manifest.json" "$WORK/manifest.json"
  cp -R "$FIXTURE/reference" "$WORK/reference"
  printf 'fixture-0.1.0\n' > "$WORK/.standards-version.fixture"
  printf 'fixture-0.1.0\n' > "$WORK/.standards-latest.fixture"
  printf 'core,python,agentic,frontend\n' > "$WORK/.standards-profiles.fixture"
}

# --- T0: sync reference + manifest ---
log "=== Sync reference ==="
"$FIXTURE/sync-reference.sh" fixture-0.1.0 >/dev/null
ENTRY_COUNT="$(python3 -c 'import json; print(len(json.load(open("'"$FIXTURE/manifest.json"'"))["entries"]))')"
log "Manifest entries: $ENTRY_COUNT"

# --- T1: Clean (real repo) ---
log "=== T1 Clean ==="
if out="$(run_check_expect_status 0)"; then
  status="$(printf '%s' "$out" | json_field '["status"]')"
  if [[ "$status" == "clean" ]]; then
    pass "T1 clean"
  else
    fail "T1 clean" "status=$status"
  fi
else
  fail "T1 clean" "unexpected exit code"
fi

# --- T2: Stale ---
log "=== T2 Stale ==="
printf 'fixture-0.2.0\n' > "$ROOT/.standards-latest.fixture"
if out="$(run_check_expect_status 2)"; then
  if printf '%s' "$out" | python3 -c 'import json,sys; fs=json.load(sys.stdin)["findings"]; sys.exit(0 if any(f["type"]=="stale" for f in fs) else 1)'; then
    pass "T2 stale"
  else
    fail "T2 stale" "no stale finding"
  fi
else
  fail "T2 stale" "expected exit 2"
fi
printf 'fixture-0.1.0\n' > "$ROOT/.standards-latest.fixture"

# --- T3: Diverged ---
log "=== T3 Diverged ==="
TARGET="$ROOT/.cursor/rules/generic/code-simplification.md"
BACKUP="$(mktemp)"
cp "$TARGET" "$BACKUP"
echo "# drift marker" >> "$TARGET"
if out="$(run_check_expect_status 2)"; then
  if printf '%s' "$out" | python3 -c 'import json,sys; fs=json.load(sys.stdin)["findings"]; sys.exit(0 if any(f["type"]=="diverged" for f in fs) else 1)'; then
    pass "T3 diverged"
  else
    fail "T3 diverged" "no diverged finding"
  fi
else
  fail "T3 diverged" "expected exit 2"
fi
cp "$BACKUP" "$TARGET"
rm "$BACKUP"

# --- T7: Contribution candidate (same setup as T3) ---
log "=== T7 Contribution candidate ==="
cp "$TARGET" "$BACKUP"
echo "# drift marker" >> "$TARGET"
if out="$(run_check_expect_status 2)"; then
  if printf '%s' "$out" | python3 -c 'import json,sys; fs=json.load(sys.stdin)["findings"]; sys.exit(0 if any(f.get("classification")=="contribution_candidate" for f in fs) else 1)'; then
    pass "T7 contribution_candidate"
  else
    fail "T7 contribution_candidate" "missing classification"
  fi
else
  fail "T7 contribution_candidate" "expected exit 2"
fi
cp "$BACKUP" "$TARGET"
rm "$BACKUP"

# --- T4: Missing ---
log "=== T4 Missing ==="
cp "$TARGET" "$BACKUP"
rm "$TARGET"
if out="$(run_check_expect_status 2)"; then
  if printf '%s' "$out" | python3 -c 'import json,sys; fs=json.load(sys.stdin)["findings"]; sys.exit(0 if any(f["type"]=="missing" for f in fs) else 1)'; then
    pass "T4 missing"
  else
    fail "T4 missing" "no missing finding"
  fi
else
  fail "T4 missing" "expected exit 2"
fi
cp "$BACKUP" "$TARGET"
rm "$BACKUP"

# --- T5: Overlay ignore ---
log "=== T5 Overlay ignore ==="
OVERLAY="$ROOT/.cursor/rules/lms-ai/ai-sdlc-charter-lms-ai.md"
OB="$(mktemp)"
cp "$OVERLAY" "$OB"
echo "# overlay drift" >> "$OVERLAY"
if out="$(run_check_expect_status 0)"; then
  if printf '%s' "$out" | python3 -c 'import json,sys; fs=json.load(sys.stdin)["findings"]; sys.exit(0 if not any("lms-ai" in f.get("path","") for f in fs) else 1)'; then
    pass "T5 overlay ignore"
  else
    fail "T5 overlay ignore" "overlay path in findings"
  fi
else
  fail "T5 overlay ignore" "expected clean exit 0"
fi
cp "$OB" "$OVERLAY"
rm "$OB"

# --- T6: Profile filter ---
log "=== T6 Profile filter ==="
cp "$TARGET" "$BACKUP"
echo "# python-only drift" >> "$ROOT/.cursor/rules/generic/security-and-hardening.md"
printf 'core\n' > "$ROOT/.standards-profiles.fixture"
if out="$(run_check_expect_status 0 CI_POLICY=warn)"; then
  if printf '%s' "$out" | python3 -c 'import json,sys; fs=json.load(sys.stdin)["findings"]; sys.exit(0 if not any("security-and-hardening" in f.get("path","") for f in fs) else 1)'; then
    pass "T6 profile filter"
  else
    fail "T6 profile filter" "python path checked under core-only"
  fi
else
  # core-only may still warn on other things? should be clean if only python diverged
  fail "T6 profile filter" "unexpected exit"
fi
cp "$BACKUP" "$TARGET"
cp "$FIXTURE/reference/cursor/rules/generic/security-and-hardening.md" "$ROOT/.cursor/rules/generic/security-and-hardening.md"
printf 'core,python,agentic,frontend\n' > "$ROOT/.standards-profiles.fixture"
rm "$BACKUP"

# Fix T6 - I appended to security file, restored from reference. Good.

# --- T8: Materialize ---
log "=== T8 Materialize ==="
setup_workspace
mkdir -p "$WORK/.cursor/rules/generic" "$WORK/.cursor/skills/generic" "$WORK/.cursor/templates/ai-sdlc"
env STANDARDS_ROOT="$WORK" \
  STANDARDS_REFERENCE="reference" \
  STANDARDS_MANIFEST="manifest.json" \
  STANDARDS_PROFILES_FILE=".standards-profiles.fixture" \
  DRY_RUN=0 \
  "$ROOT/scripts/standards-materialize.sh" >/dev/null
expected="$(python3 -c 'import json; m=json.load(open("'"$WORK/manifest.json"'")); enabled=set("core python agentic frontend".split()); print(sum(1 for e in m["entries"] if enabled.intersection(e["profiles"])))')"
actual="$(find "$WORK/.cursor" -type f | wc -l | tr -d ' ')"
if [[ "$actual" -ge "$expected" ]]; then
  pass "T8 materialize ($actual files)"
else
  fail "T8 materialize" "expected >= $expected files, got $actual"
fi

# --- T9: Upgrade overwrite ---
log "=== T9 Upgrade overwrite ==="
echo "# diverged" >> "$WORK/.cursor/rules/generic/code-simplification.md"
env STANDARDS_ROOT="$WORK" \
  STANDARDS_REFERENCE="reference" \
  STANDARDS_MANIFEST="manifest.json" \
  STANDARDS_PROFILES_FILE=".standards-profiles.fixture" \
  DRY_RUN=0 \
  "$ROOT/scripts/standards-materialize.sh" >/dev/null
if env STANDARDS_ROOT="$WORK" STANDARDS_REFERENCE="reference" STANDARDS_MANIFEST="manifest.json" \
  STANDARDS_VERSION_FILE=".standards-version.fixture" STANDARDS_LATEST_FILE=".standards-latest.fixture" \
  STANDARDS_PROFILES_FILE=".standards-profiles.fixture" \
  "$ROOT/scripts/check-standards.sh" >/dev/null 2>&1; then
  pass "T9 upgrade overwrite"
else
  fail "T9 upgrade overwrite" "not clean after re-materialize"
fi

# --- T10: never_manage ---
log "=== T10 never_manage ==="
if python3 -c 'import json,sys; m=json.load(open("'"$FIXTURE/manifest.json"'")); sys.exit(1 if any(e["materialize_to"]==".env" for e in m["entries"]) else 0)'; then
  pass "T10 never_manage (.env not in manifest)"
else
  fail "T10 never_manage" ".env appears in manifest entries"
fi

# --- Timing ---
log "=== Performance ==="
START=$(python3 -c 'import time; print(time.time())')
run_check >/dev/null || true
END=$(python3 -c 'import time; print(time.time())')
ELAPSED="$(python3 -c "print(round($END - $START, 2))")"
log "check-standards elapsed: ${ELAPSED}s"
if python3 -c "import sys; sys.exit(0 if float('$ELAPSED') < 30 else 1)"; then
  pass "Performance <30s"
else
  fail "Performance" "${ELAPSED}s >= 30s"
fi

# --- Write results ---
{
  echo "# Standards fixture test results"
  echo ""
  echo "**Run:** $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "**Manifest entries:** $ENTRY_COUNT"
  echo "**Passed:** $PASS"
  echo "**Failed:** $FAIL"
  echo ""
  echo "| ID | Scenario | Result |"
  echo "|----|----------|--------|"
  echo "| T1 | Clean | see run |"
  echo "| T2 | Stale | see run |"
  echo "| T3 | Diverged | see run |"
  echo "| T4 | Missing | see run |"
  echo "| T5 | Overlay ignore | see run |"
  echo "| T6 | Profile filter | see run |"
  echo "| T7 | Contribution candidate | see run |"
  echo "| T8 | Materialize | see run |"
  echo "| T9 | Upgrade overwrite | see run |"
  echo "| T10 | never_manage | see run |"
  echo ""
  echo "Check elapsed: ${ELAPSED}s"
} > "$RESULTS"

log ""
log "Results: $PASS passed, $FAIL failed"
log "Wrote $RESULTS"

if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
