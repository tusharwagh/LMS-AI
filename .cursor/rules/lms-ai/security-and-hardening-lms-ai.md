---
name: security-and-hardening-lms-ai
description: LMS-AI security addendum — Pydantic Settings env vars, middleware, RBAC roles, production validators. Use with generic security-and-hardening rule.
---

# LMS-AI security settings (`src/lms/config.py`)

Shipped controls map to environment variables via Pydantic `Settings` (see `.env.example`).

| Setting | Env var(s) | Purpose |
|---------|------------|---------|
| `app_secret_key` | `APP_SECRET_KEY` | JWT signing; must not stay default in production |
| `app_env` / `app_debug` | `APP_ENV`, `APP_DEBUG` | Production rejects debug + default secret |
| `database_url` | `DATABASE_URL` | Postgres; production rejects default dev credentials |
| `jwt_algorithm` / `jwt_access_token_expire_minutes` | `JWT_*` | Access token lifetime |
| `cors_origins` | `CORS_ORIGINS` | Explicit origins required in production (not `*`) |
| `security_hsts_enabled` | `SECURITY_HSTS_ENABLED` | HSTS middleware |
| `rate_limit_enabled` | `RATE_LIMIT_ENABLED` | API + auth rate limits |
| `auth_rate_limit_*` / `api_rate_limit_*` | `AUTH_RATE_LIMIT_*`, `API_RATE_LIMIT_*` | Brute-force protection |
| `agent_issue_enabled` / `agent_mock_llm` | `AGENT_ISSUE_ENABLED`, `AGENT_MOCK_LLM` | Agent desk; prod requires real LLM keys when enabled |
| LLM provider keys | `GROQ_API_KEY`, `OPENAI_API_KEY`, … | Hosted models; never in prompts or graph state |
| Langfuse | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` | Required in production when agent enabled |

**Code locations:**

| Control | Module |
|---------|--------|
| Password hashing (bcrypt cost 12) | `src/lms/shared/auth/password.py` |
| JWT encode/decode | `src/lms/shared/auth/jwt.py` |
| Auth FastAPI deps | `src/lms/shared/auth/deps.py` |
| RBAC roles (ADMIN/LIBRARIAN/PATRON) | `src/lms/platform/auth/roles.py` |
| Staff/admin RBAC aliases | `src/lms/platform/auth/rbac.py` |
| Auth service + API users | `src/lms/platform/application/auth_service.py` |
| HTTP middleware + errors | `src/lms/shared/http/middleware.py`, `security_middleware.py`, `errors.py` |
| Production validator | `Settings.validate_production_security()` in `config.py` |

**Tests:** `tests/hardening/test_security.py`, `tests/unit/test_shared_and_auth.py`

**See also:** [security-and-hardening.md](../generic/security-and-hardening.md) (generic security rule).
