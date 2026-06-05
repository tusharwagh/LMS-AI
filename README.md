# LMS — K-12 Library Management (MVP)

Python modular monolith. Specs: [MVP.md](docs/MVP.md) · Implementation plan: [plan-mvp.md](docs/plan-mvp.md) · All docs: [docs/](docs/).

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
docker compose up -d db
alembic upgrade head

uvicorn lms.main:app --reload --app-dir src
```

Health: `GET http://localhost:8000/health`
