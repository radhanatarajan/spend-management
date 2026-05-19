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

Starts MySQL 8 and Redis via Docker Compose on `localhost:3306`.

### 2. Start the API server

```bash
make dev-api
```

FastAPI starts at `http://localhost:8000`. On first run it automatically:
- Creates all database tables
- Seeds 150 spend transactions
- Seeds one user per role (see credentials below)

### 3. Start the frontend

```bash
make dev-client
```

Vite starts at `http://localhost:5173`.

---

## User Roles & Credentials

The app has four roles with different levels of access. Seed accounts are created automatically on first startup.

| Role | Email | Password | Access Level |
|---|---|---|---|
| **Admin** | admin@example.com | admin123 | Full access — manage users, all data, all settings |
| **Biz Admin** | bizadmin@example.com | bizadmin123 | Business-level write access — edit spend, contracts, budgets |
| **Service Owner** | serviceowner@example.com | serviceowner123 | Write access scoped to their own services/cost centers |
| **Read Only** | readonly@example.com | readonly123 | View all data, no edits |

### Role Capabilities

| Feature | Admin | Biz Admin | Service Owner | Read Only |
|---|:---:|:---:|:---:|:---:|
| View spend data | ✓ | ✓ | ✓ | ✓ |
| View contracts | ✓ | ✓ | ✓ | ✓ |
| Edit / upload data | ✓ | ✓ | ✓ (own scope) | — |
| Manage budgets | ✓ | ✓ | — | — |
| Manage users | ✓ | — | — | — |

> These are the intended access boundaries. Backend guards (`require_admin`, `require_biz_admin`, `require_write`) enforce them at the API level.

---

## Pages

### Spend Analytics (`/spend`)

See the [Spend Page](#spend-page) section below for full details.

### Contract Database (`/contracts`)
Planned — tracks vendor contracts, renewal dates, and spend commitments.

### Budget Planning (`/budget-planning`)
Planned — set and track budgets by department, cost center, or account group.

### Forecasting (`/forecasting`)
Planned — project future spend based on historical trends.

### Reports (`/reports`)
Planned — exportable summaries and executive dashboards.

---

## Spend Page

The Spend Analytics page (`/spend`) is a fully interactive table covering all Oracle-aligned GL spend data.

### Columns

| Column | Field | Notes |
|---|---|---|
| Month | `month_label` | Derived from `month_key` (YYYYMM integer) |
| Expense Type | `expense_type` | e.g. Capex, Opex, Travel |
| Co. Code | `company_code` | Oracle company code |
| Oracle › Org | `oracle_organization` | Business unit |
| Oracle › Acct. No. | `oracle_account_number` | GL account number |
| Oracle Dept › Code | `oracle_department` | Department code |
| Oracle Dept › Name | `oracle_department_name` | Department name |
| Hierarchy | `oracle_cost_center_hierarchy` | Cost center rollup path |
| Oracle Account › Group | `oracle_account_group` | e.g. R&D, S&M, G&A |
| Oracle Account › Sub Group | `oracle_account_sub_group` | Sub-classification |
| Cost Element | `oracle_cost_element` | e.g. Salaries, Licenses |
| Line Desc. | `line_desc` | Free-text line description |
| Vendor | `vendor_name` | Supplier name |
| PO | `po_recon` | PO reconciliation code (hover for description) |
| PO Number | `purchase_order_number` | |
| PO Line | `purchase_order_line_number` | |
| Invoice No. | `invoice_number` | |
| Invoice Line | `invoice_line_number` | |
| JE Source | `je_source` | Journal entry source (e.g. Coupa, Concur) |
| $ | `amount_usd` | USD amount, right-aligned |

The table uses a **grouped two-row header** to visually cluster Oracle, Oracle Dept, and Oracle Account columns.

### Filters

Each filter is a dropdown slicer showing distinct values from the data. Filters are **cross-dependent** — selecting a value in one slicer narrows the options in all others based on what's actually in the data.

| Filter | Field |
|---|---|
| Month | `month_key` |
| Expense Type | `expense_type` |
| Company Code | `company_code` |
| Oracle Department | `oracle_department` |
| Account Group | `oracle_account_group` |
| Vendor | `vendor_name` |
| JE Source | `je_source` |

- Select one, multiple, or all values per slicer
- Click **Apply Filters** to update the table
- Click **Clear** inside any slicer to reset it

### Sorting & Pagination

- Click any column header to sort ascending; click again to sort descending
- Default page size: 50 rows
- Page controls at the bottom of the table

---

## API Reference

Base URL: `http://localhost:8000`

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/login` | Returns JWT + user object |
| `GET` | `/api/auth/me` | Returns current user (requires auth) |
| `GET` | `/api/spend/transactions` | Paginated, filtered, sorted spend list |
| `GET` | `/api/spend/filter-options` | Distinct slicer values (cross-filtered) |

Interactive docs available at `http://localhost:8000/docs`.

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
