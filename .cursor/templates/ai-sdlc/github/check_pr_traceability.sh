#!/usr/bin/env bash
# Verify PR title/body links to a GitHub issue and a requirement (or declared N/A).
# Copy to scripts/check_pr_traceability.sh in your repo.
set -euo pipefail

read_text() {
  if [ -n "${PR_BODY_FILE:-}" ] && [ -f "$PR_BODY_FILE" ]; then
    cat "$PR_BODY_FILE"
  else
    printf '%s\n%s' "${PR_TITLE:-}" "${PR_BODY:-}"
  fi
}

TEXT="$(read_text)"
if [ -z "${TEXT//[[:space:]]/}" ]; then
  echo "check_pr_traceability: no PR text." >&2
  echo "Set PR_TITLE/PR_BODY or PR_BODY_FILE=path/to/body.md" >&2
  exit 1
fi

fail=0

if ! printf '%s' "$TEXT" | grep -qE '(#[0-9]+|https://github\.com/[^/]+/[^/]+/issues/[0-9]+)'; then
  echo "FAIL: Missing GitHub issue reference (#NNN or .../issues/NNN)." >&2
  fail=1
fi

if printf '%s' "$TEXT" | grep -qE 'REQ-[0-9]{2}'; then
  echo "OK: REQ reference found."
elif printf '%s' "$TEXT" | grep -qiE 'N/A[[:space:]]*[—–-][[:space:]]*(chore|docs|tooling|ci|deps|refactor|test)'; then
  echo "OK: Traceability N/A exemption found."
else
  echo "FAIL: Missing REQ-XX or N/A — chore|docs|tooling|ci|deps|refactor|test." >&2
  fail=1
fi

if [ "$fail" -ne 0 ]; then
  exit 1
fi

echo "Traceability check passed."
