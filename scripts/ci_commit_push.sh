#!/usr/bin/env bash
# Run make ci-native, then interactively commit and push (conventional commits encouraged).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> Running make ci-native"
make ci-native

echo ""
echo "==> Git status"
git status --short

if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
  echo "Nothing to commit — working tree clean."
  exit 0
fi

echo ""
printf "Commit message (required; conventional commits, e.g. feat: …): "
read -r commit_msg

if [ -z "${commit_msg//[[:space:]]/}" ]; then
  echo "Aborted: commit message is required." >&2
  exit 1
fi

git add -A

if git diff --cached --quiet; then
  echo "Nothing staged after git add — aborting."
  exit 1
fi

git commit -m "$(cat <<EOF
${commit_msg}
EOF
)"

branch="$(git rev-parse --abbrev-ref HEAD)"
echo ""
echo "==> Pushing ${branch} to origin"
if git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
  git push
else
  git push -u origin "${branch}"
fi

echo "Done."
