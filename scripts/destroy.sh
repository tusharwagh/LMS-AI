#!/usr/bin/env bash
# Tear down LMS data, schema, database, and/or local deployment.
#
# Usage:
#   ./scripts/destroy.sh --data              Remove sample seed rows only
#   ./scripts/destroy.sh --schema            Drop all LMS tables
#   ./scripts/destroy.sh --db                Drop application database
#   ./scripts/destroy.sh --all               data + schema + db (native Postgres)
#   ./scripts/destroy.sh --deploy            Full local deploy teardown (Compose + DB)
#   ./scripts/destroy.sh --deploy --yes      Skip confirmation prompt
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DO_DATA=0
DO_SCHEMA=0
DO_DB=0
DO_DEPLOY=0
YES=0

usage() {
  sed -n '2,12p' "$0" | sed 's/^# \?//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --data) DO_DATA=1 ;;
    --schema) DO_SCHEMA=1 ;;
    --db) DO_DB=1 ;;
    --all) DO_DATA=1; DO_SCHEMA=1; DO_DB=1 ;;
    --deploy) DO_DEPLOY=1; DO_DATA=1; DO_SCHEMA=1 ;;
    --yes|-y) YES=1 ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown option: $1" >&2; usage 1 ;;
  esac
  shift
done

if [[ "$DO_DATA$DO_SCHEMA$DO_DB$DO_DEPLOY" == "0000" ]]; then
  DO_DATA=1
  DO_SCHEMA=1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env 2>/dev/null || true
fi

if [[ ! -x .venv/bin/python ]]; then
  make ensure-venv >/dev/null
fi

BIN="$ROOT/.venv/bin"
DB_EXEC="$BIN/python $ROOT/scripts/db_exec.py"

db_reachable() {
  $BIN/python - <<'PY' >/dev/null 2>&1
import sys
sys.path.insert(0, "src")
import psycopg
from lms.config import get_settings
from sqlalchemy.engine import make_url

url = make_url(get_settings().database_url).render_as_string(hide_password=False)
url = url.replace("postgresql+psycopg://", "postgresql://")
with psycopg.connect(url):
    pass
PY
}

confirm() {
  if [[ "$YES" -eq 1 ]]; then
    return 0
  fi
  echo ""
  echo "This will destroy LMS resources:"
  [[ "$DO_DEPLOY" -eq 1 ]] && echo "  - Docker Compose stack and volumes"
  [[ "$DO_DATA" -eq 1 ]] && echo "  - Sample seed data"
  [[ "$DO_SCHEMA" -eq 1 ]] && echo "  - All LMS tables (domain + idempotency + alembic_version)"
  [[ "$DO_DB" -eq 1 ]] && echo "  - Application database (drop + recreate empty)"
  echo ""
  read -r -p "Continue? [y/N] " reply
  [[ "$reply" =~ ^[Yy]$ ]]
}

stop_api() {
  if command -v docker >/dev/null 2>&1 && docker compose ps -q api 2>/dev/null | grep -q .; then
    echo "Stopping API container..."
    docker compose stop api 2>/dev/null || true
  fi
}

destroy_data() {
  echo "Removing sample data..."
  $DB_EXEC "$ROOT/scripts/sql/003_destroy_sample_data.sql"
}

destroy_schema() {
  echo "Dropping LMS schema..."
  $DB_EXEC "$ROOT/scripts/sql/004_destroy_schema.sql"
}

destroy_db() {
  echo "Dropping application database..."
  $BIN/python "$ROOT/scripts/db_exec.py" --drop-database
}

run_db_cleanup() {
  if ! db_reachable; then
    echo "Database unreachable — skipping SQL cleanup."
    return 0
  fi
  stop_api
  if [[ "$DO_DATA" -eq 1 ]]; then destroy_data; fi
  if [[ "$DO_SCHEMA" -eq 1 ]]; then destroy_schema; fi
  if [[ "$DO_DB" -eq 1 ]]; then destroy_db; fi
}

main() {
  confirm || { echo "Aborted."; exit 1; }

  if [[ "$DO_DEPLOY" -eq 1 ]]; then
    echo "Tearing down local deployment..."
    run_db_cleanup
    if command -v docker >/dev/null 2>&1; then
      echo "Removing Compose stack and volumes..."
      docker compose down -v --remove-orphans 2>/dev/null || true
    fi
    echo "Local deployment destroyed."
    exit 0
  fi

  run_db_cleanup
  echo "Destroy complete."
}

main
