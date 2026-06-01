# Spend Management

A Finance Ops platform for tracking spend, managing contracts, planning budgets, and generating reports.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19 + Vite + Tailwind CSS + TanStack Query v5 |
| Backend | FastAPI + SQLAlchemy 2.0 + Pydantic v2 |
| Database | MySQL 8 (Docker) |
| Auth | JWT (python-jose) + bcrypt |

---

## Getting Started

### Prerequisites
- Docker Desktop
- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- Node.js 20+

### 1. Start the database

```bash
make dev-db
```

Starts MySQL 8 via Docker Compose on `localhost:3306`.

### 2. Start the API server

```bash
make dev-api
```

FastAPI starts at `http://localhost:8000`. On first run it automatically:
- Creates all database tables and runs idempotent schema migrations
- Seeds ~150 spend transactions across the last 6 months
- Seeds one user per role (see credentials below)
- Seeds 4 sample contracts (Salesforce, GitHub, Workday, Tableau)
- Seeds a baseline FY2027 Non-Controllable budget scenario

### 3. Start the frontend

```bash
make dev-client
```

Vite starts at `http://localhost:5173`.

---

## User Roles & Credentials

| Role | Email | Password | Access Level |
|---|---|---|---|
| **Admin** | admin@example.com | admin123 | Full access |
| **Biz Admin** | bizadmin@example.com | bizadmin123 | Business-level write access |
| **Service Owner** | serviceowner@example.com | serviceowner123 | Write access for own entries |
| **Read Only** | readonly@example.com | readonly123 | View all data, no edits |

| Feature | Admin | Biz Admin | Service Owner | Read Only |
|---|:---:|:---:|:---:|:---:|
| View spend, contracts, budgets | ✓ | ✓ | ✓ | ✓ |
| Edit spend / contracts | ✓ | ✓ | ✓ (own scope) | — |
| Create / manage budget scenarios | ✓ | ✓ | — | — |
| Edit budget entries | ✓ | ✓ | ✓ | — |
| Submit entry for review | ✓ | ✓ | ✓ | — |
| Approve / finalize entries | ✓ | ✓ | — | — |
| Set actuals cutoff month | ✓ | ✓ | — | — |
| Manage users | ✓ | — | — | — |

---

## Pages

### Spend Analytics (`/spend`)
Interactive GL spend table with cross-dependent slicers (Month, Expense Type, Company Code, Department, Account Group, Vendor, JE Source), multi-column sorting, and pagination. KPI summary strip updates in real time.

### Contract Database (`/contracts`)
Full CRUD for multi-year software license contracts. Contracts are grouped by Vendor + Department + Account + PO Number. Each PO can have multiple lines (one per service year) with configurable billing intervals (Monthly, Quarterly, Annual, Custom). Consecutive lines are detected and badged as multi-year.

### Budget Planning (`/budget-planning`)

#### Non-Controllable Budget

Plans employee-related costs (salaries, travel, overtime, bonus) by department for the upcoming fiscal year.

**Scenarios** — Create multiple named planning scenarios, copy from an existing scenario, and compare any two side-by-side. One scenario is pinned as the baseline.

**Current row (actuals + carry-forward)** — Queries the prior fiscal year's spend data as the planning baseline. An admin-controlled actuals cutoff month determines which quarters show confirmed actuals (green) vs carry-forward estimates (italic amber).

**Editable entries** — Each department has two editable rows:
- **Current Approved Rec** — the planned approved budget
- **Additional Ask** — incremental budget above the approved rec

Cells save on blur (or Enter). FINAL entries are locked read-only.

**Row-level status workflow:**

```
DRAFT → READY_FOR_REVIEW → APPROVED → FINAL
         ↘ CANCELLED ←─────────────────┘
```

| Transition | Who can do it |
|---|---|
| DRAFT → READY_FOR_REVIEW / CANCELLED | Service Owner, Biz Admin, Admin |
| READY_FOR_REVIEW → DRAFT / APPROVED / CANCELLED | Biz Admin, Admin |
| APPROVED → READY_FOR_REVIEW / FINAL / CANCELLED | Biz Admin, Admin |
| FINAL → APPROVED | Admin only |
| CANCELLED → DRAFT | Admin only |

**Bulk status update** — Check multiple rows and move them all to a common valid status in one action. Only transitions valid for every selected row are offered.

**Audit log** — Every amount edit and status change is recorded with old/new values. An inline collapsible panel shows the timeline per scenario.

**What-if panel** — Side-by-side FY total comparison between Current, Approved Rec, and Additional Ask with delta indicators.

#### Scenario Comparison
Pick any two scenarios and view a side-by-side quarterly delta table across all departments.

### Reports (`/reports`)

| Report | Path | Status |
|---|---|---|
| Spend Report | `/reports/spend` | Live |
| Contract Report | `/reports/contracts` | Live |
| Budget Change Log | `/reports/budget-audit` | Live |
| Forecast Report | `/reports/forecast` | Coming soon |
| Budget Report | `/reports/budget` | Coming soon |

**Spend Report** — KPI cards, monthly trend chart, spend-by-account-group donut, top vendors bar chart, insights panel, and CSV export.

**Contract Report** — Multi-year contracts only. Monthly dollar breakout across a calendar fiscal year. Months beyond the last signed PO line are projected at 100% renewal (shown in amber italic). Multi-select slicers for Vendor, Department, and Status.

**Budget Change Log** — Full audit trail of all budget entry edits and status transitions, filterable by fiscal year, scenario, department, category (Approved Rec / Additional Ask), event type (Amount / Status), and user. Each row shows old → new values with inline diff formatting.

### Forecasting (`/forecasting`)
Planned.

---

## Budget Audit Trail

All changes to `budget_entries` are recorded in `budget_entry_audit` using an `event_type` + `changes` JSON design — only the fields that actually changed are stored per event.

| event_type | changes payload example |
|---|---|
| `AMOUNT_CHANGED` | `{"q1_amount": {"old": "0.00", "new": "150000"}}` |
| `STATUS_CHANGED` | `{"status": {"old": "DRAFT", "new": "READY_FOR_REVIEW"}}` |

A MySQL view `v_budget_entry_audit` joins `budget_entry_audit → budget_entries → budget_scenarios` and unpacks the JSON into named columns for easy querying:

```sql
SELECT * FROM v_budget_entry_audit WHERE fiscal_year = 2027;

-- Before / after for specific entries
SELECT entry_id, row_type, department_name, entry_type,
       q1_amount, q2_amount, q3_amount, q4_amount, status, as_of
FROM (
  SELECT 1 AS sort_order, 'ORIGINAL' AS row_type, be.id AS entry_id,
    be.department_name, be.entry_type,
    COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(fa.changes,'$.q1_amount.old')) AS DECIMAL(14,2)), be.q1_amount) AS q1_amount,
    COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(fa.changes,'$.q2_amount.old')) AS DECIMAL(14,2)), be.q2_amount) AS q2_amount,
    COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(fa.changes,'$.q3_amount.old')) AS DECIMAL(14,2)), be.q3_amount) AS q3_amount,
    COALESCE(CAST(JSON_UNQUOTE(JSON_EXTRACT(fa.changes,'$.q4_amount.old')) AS DECIMAL(14,2)), be.q4_amount) AS q4_amount,
    COALESCE(JSON_UNQUOTE(JSON_EXTRACT(fa.changes,'$.status.old')), be.status) AS status,
    fa.changed_at AS as_of
  FROM budget_entries be
  JOIN (SELECT *, ROW_NUMBER() OVER (PARTITION BY entry_id ORDER BY changed_at) AS rn
        FROM budget_entry_audit WHERE entry_id IN (1,9)) fa ON fa.entry_id = be.id AND fa.rn = 1
  WHERE be.id IN (1,9)
  UNION ALL
  SELECT 2, 'CURRENT', id, department_name, entry_type,
    q1_amount, q2_amount, q3_amount, q4_amount, status, updated_at
  FROM budget_entries WHERE id IN (1,9)
) t ORDER BY entry_id, sort_order;
```

---

## Contract Billing Intervals

| Interval | Entered Amount | Monthly Amount |
|---|---|---|
| Monthly | Per-month charge | = entered amount |
| Quarterly | Per-quarter charge | ÷ 3 |
| Annual | Per-year charge | ÷ 12 |
| Custom (total) | Total for full period | ÷ months in period |

---

## API Reference

Base URL: `http://localhost:8000` — Interactive docs at `http://localhost:8000/docs`

### Auth
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/login` | Returns JWT + user object |
| `GET` | `/api/auth/me` | Current user |

### Spend
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/spend/transactions` | Paginated, filtered, sorted spend |
| `GET` | `/api/spend/filter-options` | Cross-filtered slicer values |

### Contracts
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/contracts` | List all contracts with lines |
| `POST` | `/api/contracts` | Create contract with optional lines |
| `GET` | `/api/contracts/{id}` | Get a single contract |
| `PUT` | `/api/contracts/{id}` | Update contract header |
| `DELETE` | `/api/contracts/{id}` | Delete contract and all lines |
| `POST` | `/api/contracts/{id}/lines` | Add a line |
| `PUT` | `/api/contracts/{id}/lines/{line_id}` | Update a line |
| `DELETE` | `/api/contracts/{id}/lines/{line_id}` | Remove a line |
| `GET` | `/api/contracts/report` | Monthly breakout report (`?fiscal_year=`) |

### Budget
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/budget/config` | NC config for a fiscal year (`?fiscal_year=`) |
| `PUT` | `/api/budget/config` | Update cost elements + actuals cutoff |
| `GET` | `/api/budget/cost-elements` | All available cost elements |
| `GET` | `/api/budget/scenarios` | List scenarios (`?fiscal_year=&budget_type=`) |
| `POST` | `/api/budget/scenarios` | Create scenario (optionally copy from another) |
| `PUT` | `/api/budget/scenarios/{id}` | Rename / update scenario |
| `DELETE` | `/api/budget/scenarios/{id}` | Delete non-baseline scenario |
| `GET` | `/api/budget/scenarios/{id}/audit` | Audit log for a scenario |
| `GET` | `/api/budget/non-controllable` | Full plan with actuals + entries (`?fiscal_year=&scenario_id=`) |
| `PUT` | `/api/budget/entries` | Upsert a budget entry (saves on blur) |
| `PATCH` | `/api/budget/entries/{id}/status` | Transition entry status |
| `DELETE` | `/api/budget/entries/{id}` | Delete an entry |
| `GET` | `/api/budget/compare` | Side-by-side scenario comparison |
| `GET` | `/api/budget/reports/audit` | Budget change log report (`?fiscal_year=`) |

---

## Detailed Guides

Full feature documentation is in the [`docs/`](docs/) folder:

| Document | Description |
|---|---|
| [spend_analytics_guide.md](docs/spend_analytics_guide.md) | Spend Analytics page, Spend Report, filters, API, data model |
| [contract_database_guide.md](docs/contract_database_guide.md) | Contract Database, billing intervals, multi-year detection, Contract Report business rules, API, data model |
| [spend_management_setup.md](docs/spend_management_setup.md) | Initial dev environment setup |

---

## Running Tests

### Backend

```bash
cd server && uv run pytest
```

### Frontend

```bash
cd client && npm test
```
