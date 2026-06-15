FROM node:24-slim AS staff-ui

WORKDIR /build/staff-ui

COPY src/lms/staff/ui/package.json src/lms/staff/ui/package-lock.json* ./
RUN npm install

COPY src/lms/staff/ui/ ./
RUN npm run build

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY --from=staff-ui /build/staff/static ./src/lms/staff/static
COPY alembic ./alembic
COPY alembic.ini ./

RUN pip install .

COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
