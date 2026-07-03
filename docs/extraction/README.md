# LMS-AI extraction index

Reusable infrastructure is wired via [org-python-platform](https://github.com/tusharwagh/org-python-platform) packages.

**Pinned version:** `.platform-version` (currently matches git tag `v0.1.0` in `pyproject.toml`).

## Wired packages

| LMS shim | Package | Notes |
|----------|---------|-------|
| `shared/llm/models`, `cost`, `routing`, `guardrails` | `litellm-gateway` | `Settings.to_llm_gateway_settings()` |
| `shared/llm/gateway` | `litellm-gateway` + LMS NeMo | Delegates to platform gateway |
| `shared/observability/tracing` | `langfuse-tracing` | `Settings.to_langfuse_tracing_settings()` |
| `shared/http/errors`, `health` | `fastapi-platform-kit` | Debug flag from `get_settings()` |
| `shared/auth/jwt` | `fastapi-platform-kit` | `Settings.to_jwt_settings()` |
| `shared/db/mixins` | `fastapi-platform-kit` | Re-export |
| `shared/idempotency/` | `sqlalchemy-idempotency` | `make_idempotency_model(Base)` |
| `shared/privacy/redaction` | `agent-desk-starter` | Re-export |
| `agent/graph` | `agent-desk-starter` | Re-export |

## Stays in LMS

- `shared/llm/setup.py`, `spend.py`, `nemo_guardrails.py` — LMS-specific LiteLLM callbacks
- Domain bounded contexts and agent coordinator/tools
- `agent/masking.py`, `agent/session.py` — LMS domain slots

## Install

```bash
pip install -e ".[dev]"
```

### Consumption options (this repo and others)

| Method | When to use |
|--------|-------------|
| **Git URL `@vX.Y.Z`** | Default in `pyproject.toml`; no registry auth |
| **GitHub Packages** | Faster CI; set `PIP_EXTRA_INDEX_URL` + version pins |

Full guide: [org-python-platform/docs/CONSUMING.md](https://github.com/tusharwagh/org-python-platform/blob/main/docs/CONSUMING.md)

Release order: push platform tag **before** bumping `.platform-version` / `pyproject.toml` pins. See [PUBLISH.md](https://github.com/tusharwagh/org-python-platform/blob/main/docs/PUBLISH.md).

### Upgrade platform packages

1. Note new version in upstream [CHANGELOG](https://github.com/tusharwagh/org-python-platform/blob/main/CHANGELOG.md).
2. Update `.platform-version` and `@vX.Y.Z` refs in `pyproject.toml` (or `==X.Y.Z` for GitHub Packages).
3. `pip install -e ".[dev]"` and run `make test-unit` (or `make ci-native`).

## Canonical manifest

See [org-python-platform/EXTRACTION.md](https://github.com/tusharwagh/org-python-platform/blob/main/EXTRACTION.md).
