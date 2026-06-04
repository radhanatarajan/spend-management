# CLAUDE.md — Spend Management

Project-specific instructions for Claude Code. These override default behavior.

---

## Behavioral Guidelines

### Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" that wasn't requested.
- No error handling for impossible scenarios.

### Surgical Changes

**Touch only what you must. Clean up only your own mess.**

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- Remove imports/variables/functions that YOUR changes made unused — don't remove pre-existing dead code unless asked.

### Goal-Driven Execution

**Define success criteria. Loop until verified.**

- "Fix the bug" → write a test that reproduces it, then make it pass.
- "Add a feature" → state a brief plan with verify steps before coding.
- All backend tests must pass before any commit.

---

## Git Workflow

- Active development branch: `develop`
- PRs target: `main` — never commit directly to `main`
- Always work on `develop` unless creating a PR

### Pre-Push Checklist

Run these before every `git push`. Do not push if any step fails.

```bash
# 1. Backend tests — all must pass
cd server && uv run pytest -q

# 2. Frontend lint — zero errors required
cd client && npm run lint

# 3. Frontend build — must compile clean
cd client && npm run build
```

If a test fails: fix the root cause, do not skip or suppress.
If lint fails: fix the code, do not add `// eslint-disable` unless genuinely necessary and approved by the user.

GitHub Actions runs the same checks automatically on every push to `develop` and every PR to `main` (see `.github/workflows/ci.yml`). A red CI badge = do not merge.

### Branch Protection — Required Check Names

The required status checks on `main` are named exactly:
- `Backend tests (Python 3.14)`
- `Frontend lint + build (Node 20)`

These are the `name:` fields of the jobs in `.github/workflows/ci.yml` — **not** the job IDs (`backend`, `frontend`) and **not** prefixed with the workflow name (`CI / ...`).

If branch protection ever needs to be reconfigured, always verify the exact names first:
```bash
gh api repos/radhanatarajan/spend-management/commits/{sha}/check-runs --jq '.check_runs[].name'
```

---

## Local Database Connection

| Field | Value |
|---|---|
| Host | 127.0.0.1 |
| Port | 3306 |
| Username | spend_user |
| Password | spend_pass |
| Schema | spend_management |

**Tables:** `account_numbers`, `activity_ids`, `budget_entries`, `budget_entry_audit`, `budget_nc_config`, `budget_nc_config_audit`, `budget_scenarios`, `budget_scenario_audit`, `contract_audit`, `contract_lines`, `contract_lines_audit`, `contracts`, `departments`, `project_departments`, `project_ids`, `reference_audit`, `spend`, `users`

**Views:** `v_budget_entry_audit`, `v_budget_nc_config_audit`, `v_budget_scenario_audit`, `v_contract_audit`, `v_contract_lines_audit`, `v_contracts_enriched`, `v_reference_audit_accounts`, `v_reference_audit_activities`, `v_reference_audit_departments`, `v_reference_audit_projects`, `v_spend_account_gaps`, `v_spend_activity_gaps`, `v_spend_department_gaps`

Connect via Python:
```python
import pymysql
conn = pymysql.connect(host='127.0.0.1', port=3306, user='spend_user', password='spend_pass', database='spend_management')
```

---

## Dev Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite + Tailwind CSS + TanStack Query v5 |
| Backend | FastAPI + SQLAlchemy 2.0 + Pydantic v2 |
| Database | MySQL 8 (Docker) |
| Auth | JWT (python-jose) + bcrypt |
| Package mgr (server) | `uv` |
| Package mgr (client) | `npm` |

---

## Running the Stack

```bash
make dev-db       # Start MySQL 8 via Docker on localhost:3306
make dev-api      # FastAPI on http://localhost:8000 (auto-reloads)
make dev-client   # Vite on http://localhost:5173 (auto-reloads)
make stop         # Stop Docker DB
```

API interactive docs: `http://localhost:8000/docs`

---

## Running Tests

```bash
# Backend (all must pass before committing)
cd server && uv run pytest

# Frontend
cd client && npm test
```

Tests use SQLite in-memory (StaticPool) — no MySQL needed. The `client` fixture in `conftest.py` patches `src.main.init_db` to suppress the MySQL startup call.

---

## Project Layout

```
spend-management/
├── server/
│   └── src/
│       ├── api/           # FastAPI routers (one file per domain)
│       │   ├── budget.py
│       │   ├── contracts.py
│       │   └── spend.py
│       ├── models/        # SQLAlchemy ORM models
│       │   ├── budget.py  # BudgetScenario, BudgetEntry, BudgetNcConfig, BudgetEntryAudit
│       │   ├── contract.py
│       │   ├── spend.py
│       │   └── user.py
│       ├── schemas/       # Pydantic v2 schemas (In/Out/Update)
│       ├── db/
│       │   ├── init_db.py # Table creation, idempotent migrations, seed data
│       │   └── session.py # Engine + get_db dependency
│       └── core/
│           └── dependencies.py  # require_any, require_write, require_biz_admin, get_current_user
└── client/
    └── src/
        ├── pages/
        │   ├── Spend/
        │   ├── Contracts/
        │   ├── BudgetPlanning/
        │   │   ├── NonControllablePage.jsx
        │   │   ├── NcScenarioComparisonPage.jsx
        │   │   └── components/   # ActualsCutoffControl, AuditLogPanel, NonControllableTable, etc.
        │   └── Reports/          # SpendReportPage, ContractReportPage, BudgetAuditReportPage, etc.
        ├── data/
        │   ├── budget/           # api.js + hooks.js + index.js
        │   ├── contracts/
        │   └── spend/
        └── components/
            └── Layout.jsx        # Sidebar nav + role badge
```

---

## Key Conventions

### Backend

- Use `Mapped[]` + `mapped_column()` (SQLAlchemy 2.0 style) — no legacy `Column()`
- Pydantic v2: use `model_config = ConfigDict(from_attributes=True)` on Out schemas
- `month_key` = integer `YYYYMM` (e.g. `202601` = Jan 2026)
- Fiscal year = Jan–Dec calendar year (FY2027 = Jan 2027 – Dec 2027)
- Prior year for planning baseline = `fiscal_year - 1`
- Schema migrations: add idempotent `_migrate_*()` functions in `init_db.py` using `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (MySQL 8 syntax). Call them from `init_db()`.
- API route prefix: `/api/<domain>` (e.g. `/api/budget`, `/api/contracts`)
- Auth guards: `require_any` (any authenticated user), `require_write` (SO/BizAdmin/Admin), `require_biz_admin` (BizAdmin/Admin only)

### Frontend

- TanStack Query v5: use `queryKey` arrays, `invalidateQueries({ queryKey: [...] })` after mutations
- Data layer: all fetch functions in `client/src/data/<domain>/api.js`; all hooks in `hooks.js`; public exports via `index.js`
- Tailwind only — no external component libraries
- `NavLink` in Layout.jsx controls sidebar active state; add new routes to `App.jsx` and nav items to `Layout.jsx`

### Audit Design

**Rule: every writable table must have audit coverage.** When adding a new domain table, add audit in the same PR. Which pattern to use depends on data velocity:

### Pattern A — `reference_audit` (shared table, slow-changing data)

Use for master/reference data that changes a few times a year: departments, account numbers, project IDs, activity IDs.

- Single `reference_audit` table with `table_name` + `record_id` string discriminators
- Per-entity views (`v_reference_audit_departments`, etc.) for readable queries
- `record_id` is the entity's natural key as a string

### Pattern B — individual `<domain>_audit` table (high-velocity transactional data)

Use for data that changes frequently during active business cycles: contracts, budget entries, scenarios, nc_config.

- Table name: `<domain>_audit` (e.g. `contract_audit`, `budget_scenario_audit`)
- Include denormalized identity columns so rows survive deletes (e.g. `vendor_name` on `contract_audit`, `fiscal_year` + `scenario_name` on `budget_scenario_audit`)
- Create `v_<domain>_audit` MySQL view with `JSON_EXTRACT` / `JSON_UNQUOTE` columns

### Shared rules (both patterns)

- Always include: `id` (PK), `event_type` (CREATED/UPDATED/DELETED), `changes` (JSON), `changed_by` (user email), `changed_at` (datetime, indexed)
- `changes` shape: `{"field": {"old": "prev_val", "new": "new_val"}}` — only changed fields, serialized to strings via `_serialize_val()` (handles `date`, `Decimal`, `enum`)
- Write no audit row if the changes dict is empty (no-op update guard)
- Audit rows written in the same DB transaction as the data change
- All write endpoints on auditable tables must use `require_write` to capture `current_user.email`
- Expose `GET /api/<domain>/audit` (any authenticated role), registered before `/{id}` routes to avoid FastAPI path conflicts

**`budget_entry_audit` note** (predates this convention):
- Uses `event_type` values `AMOUNT_CHANGED` / `STATUS_CHANGED` instead of CREATED/UPDATED/DELETED
- MySQL view `v_budget_entry_audit` unpacks JSON for the Budget Change Log report

### Status State Machine (`budget_entries.status`)

```
DRAFT → READY_FOR_REVIEW → APPROVED → FINAL
         ↘ CANCELLED ←─────────────────┘
```

Transitions defined in `ALLOWED_TRANSITIONS` dict in `server/src/api/budget.py`. Enforced server-side on every PATCH and reflected client-side in `NonControllableTable.jsx`.

---

## User Roles

| Role | Value | Key Permissions |
|---|---|---|
| Admin | `ADMIN` | Full access including unlocking FINAL entries |
| Biz Admin | `BIZ_ADMIN` | Manage scenarios, approve/finalize entries |
| Service Owner | `SERVICE_OWNER` | Submit own entries for review |
| Read Only | `READ_ONLY` | View only |

Test credentials (seeded on first `make dev-api`):
- `admin@example.com` / `admin123`
- `bizadmin@example.com` / `bizadmin123`
- `serviceowner@example.com` / `serviceowner123`
- `readonly@example.com` / `readonly123`

---

## Test Conventions

- Test file per domain: `test_budget.py`, `test_contracts.py`, `test_spend.py`
- `conftest.py` provides: `db`, `client`, `admin_client`, `bizadmin_client`, `serviceowner_client`, `readonly_client`
- Helper factories: `make_scenario()`, `make_entry()`, `make_spend()`, `make_contract()`
- Never mock the DB — tests run against real SQLite via `StaticPool`
- All tests must pass before pushing
- Endpoints that query MySQL-only views (e.g. `GET /api/budget/reports/audit` → `v_budget_entry_audit`) cannot be tested in SQLite; cover adjacent logic (the view columns, audit writes) in other tests instead

---

## What's Built vs Planned

| Feature | Status |
|---|---|
| Spend Analytics (`/spend`) | Done |
| Contract Database (`/contracts`) | Done |
| Budget Planning — Non-Controllable (`/budget-planning`) | Done |
| Budget Planning — Controllable (contract-seeded) | **Next** |
| Forecasting (`/forecasting`) | Planned |
| Spend Report | Done |
| Contract Report (with GL enrichment from `account_numbers`) | Done |
| Contract Change Log (`/reports/contract-audit`) | Done |
| Budget Change Log (`/reports/budget-audit`) | Done |
| Reference Data Management (`/reference/*`) | Done |
| Forecast Report | Planned |
| Budget Report | Planned |
