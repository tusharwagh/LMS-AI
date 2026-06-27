#!/usr/bin/env bash
# Product repo: bump standards submodule pin and re-materialize managed copies.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TARGET="${1:-$(tr -d '[:space:]' < .standards-latest)}"

if [[ ! -f standards/VERSION ]]; then
  echo "standards/ submodule missing. Run: git submodule update --init --recursive standards" >&2
  exit 1
fi

TAG="v${TARGET#v}"
TEMPLATE_REMOTE="${STANDARDS_TEMPLATE_REMOTE:-$ROOT/../org-ai-standards}"
(
  cd standards
  if [[ -d "$TEMPLATE_REMOTE/.git" ]]; then
    git fetch "$TEMPLATE_REMOTE" "+refs/tags/*:refs/tags/*" 2>/dev/null || true
  fi
  git fetch --tags origin 2>/dev/null || git fetch --tags 2>/dev/null || true
  git checkout "$TAG" 2>/dev/null || git checkout "$TARGET"
)

printf '%s\n' "$TARGET" > .standards-version

chmod +x standards/bootstrap/standards-materialize.sh
STANDARDS_ROOT="$ROOT" \
  STANDARDS_REFERENCE=standards \
  STANDARDS_MANIFEST=standards/manifest.json \
  STANDARDS_PROFILES_FILE=.standards-profiles \
  ./standards/bootstrap/standards-materialize.sh

COPIED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
PROFILES="$(tr -d '[:space:]' < .standards-profiles)"
printf 'version=%s\nprofiles=%s\nat=%s\n' "$TARGET" "$PROFILES" "$COPIED_AT" > .standards-copied-at

echo "standards upgrade complete: $TARGET"
