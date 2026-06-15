#!/usr/bin/env bash
# Native deployment (no Docker): venv + migrate + optional seed + API.
# Usage: SEED=1 ./scripts/deploy-native.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example — set DATABASE_URL to your local Postgres."
fi

make ensure-venv
make migrate
make staff-ui-build

if [[ "${SEED:-0}" == "1" ]]; then
  make seed
fi

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
DEBUG="${DEBUG:-0}"

if [[ "$DEBUG" == "1" || "$DEBUG" == "true" || "$DEBUG" == "yes" ]]; then
  export APP_DEBUG=true
  UVICORN_LOG_LEVEL=debug
else
  UVICORN_LOG_LEVEL=info
fi

echo ""
echo "LMS-AI native deployment (no Docker)."
echo "  Health: http://${API_HOST}:${API_PORT}/health"
echo "  Docs:   http://${API_HOST}:${API_PORT}/docs"
if [[ "$DEBUG" == "1" || "$DEBUG" == "true" || "$DEBUG" == "yes" ]]; then
  echo "  Debug:  APP_DEBUG=true, uvicorn log-level=debug"
fi
echo "  Stop:   Ctrl+C"
echo "  Destroy: make destroy-native DESTROY_YES=1"
echo ""

exec .venv/bin/uvicorn lms.main:app --reload --app-dir src --host "$API_HOST" --port "$API_PORT" --log-level "$UVICORN_LOG_LEVEL"
