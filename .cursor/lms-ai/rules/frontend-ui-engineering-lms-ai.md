---
name: frontend-ui-engineering-lms-ai
description: LMS-AI staff desk UI addendum — React/TypeScript build, Playwright E2E, MVC layout, agent chat copy. Use with generic frontend-ui-engineering rule.
---

# LMS-AI staff UI — React + TypeScript

Staff desk source lives in `src/lms/staff/ui/` (Vite, React 18+, strict TypeScript). Build output is served from `src/lms/staff/static/` at `/staff/` and `/staff/static/*`.

## Build artifact strategy

**Do not commit Vite build output** (`src/lms/staff/static/assets/*`, hashed `index.html`). Only `src/lms/staff/static/.gitkeep` is tracked.

- **Build:** `make staff-ui-build` — runs in CI, Docker (`Dockerfile` staff-ui stage), `make setup-native`, `scripts/deploy-native.sh`, and `make ensure-staff-ui` before E2E
- **Dev:** `make staff-ui-dev` with API on `:8000` (Vite proxies `/api`)
- **Styling:** CSS modules + shared design tokens in `src/styles/tokens.css` — no inline style chaos
- **API layer:** typed clients under `src/api/` matching REST endpoints

## Browser E2E (Playwright)

- **Tests:** `tests/e2e/test_staff_playwright.py` — login, issue wizard, return wizard, agent pending approval, agent HITL approve
- **Run:** `make test-e2e-playwright` (builds staff UI + installs Chromium)
- **Fixtures:** `tests/e2e/conftest.py` — live uvicorn server, seed data via API, `AGENT_MOCK_LLM` for agent tab

## Agent chat copy

The **AI assist** tab renders `assistant_message`, `pending_approval.summary`, and `agent_disclosure` from the agent API **verbatim** — do not duplicate or rewrite desk copy in the frontend.

- **Single source of truth:** `src/lms/agent/messages.py`
- **Change copy in the backend** + run `pytest tests/agent/test_intent_and_masking.py`
- UI may add layout, approval buttons, and `agent_disclosure` — not alternate phrasing for tool/slot errors

## MVC module layout (staff desk)

Inspired by CRM/admin dashboards (grouped sidebar, sticky header, breadcrumb, content panel):

| Layer | Path | Responsibility |
|-------|------|----------------|
| **Model** | `src/models/` (re-exports `src/api/`) | Types + HTTP clients — no React |
| **Controller** | `src/controllers/` | Hooks: state, side effects, actions (`useIssueWizardController`, etc.) |
| **View** | `src/views/*/*View.tsx` | Presentation only — bind controller output to components |
| **Config** | `src/config/navigation.ts` | Grouped nav + page titles (single source for sidebar/header) |
| **Layout** | `src/layout/` | CRM shell: `AppSidebar`, `AppHeader`, `ShellContext`, `AppLayout` |
| **Components** | `src/components/` | Reusable UI (`PageShell`, `Button`, `Card`, …) |

**Rules:**

- Views must not call `@/api/*` directly — use `@/models` via controllers (migrate incrementally).
- Page chrome (title, subtitle, breadcrumb) lives in `AppHeader` + `VIEW_META` — not duplicated in each view.
- Wrap view bodies in `PageShell` for consistent CRM content panel styling.
- Navigation groups: Circulation, Catalog, Patrons, Administration (config-driven, role-filtered).

**See also:** [frontend-ui-engineering.md](../../generic/rules/frontend-ui-engineering.md) (generic UI engineering rule).
