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
- Creates all database tables
- Seeds ~150 spend transactions
- Seeds one user per role (see credentials below)
- Seeds 4 sample contracts (Salesforce, GitHub, Workday, Tableau)

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
| **Service Owner** | serviceowner@example.com | serviceowner123 | Write access scoped to their own services |
| **Read Only** | readonly@example.com | readonly123 | View all data, no edits |

| Feature | Admin | Biz Admin | Service Owner | Read Only |
|---|:---:|:---:|:---:|:---:|
| View spend & contracts | ✓ | ✓ | ✓ | ✓ |
| Edit / upload data | ✓ | ✓ | ✓ (own scope) | — |
| Manage budgets | ✓ | ✓ | — | — |
| Manage users | ✓ | — | — | — |

---

## Pages

### Spend Analytics (`/spend`)
Interactive GL spend table with cross-dependent slicers (Month, Expense Type, Company Code, Department, Account Group, Vendor, JE Source), multi-column sorting, and pagination. KPI summary strip updates in real time.

### Contract Database (`/contracts`)
Full CRUD for multi-year software license contracts. Contracts are grouped by Vendor + Department + Account + PO Number. Each PO can have multiple lines (one per service year) with configurable billing intervals (Monthly, Quarterly, Annual, Custom). Consecutive lines are detected and badged as multi-year.

### Reports (`/reports`)

| Report | Path | Status |
|---|---|---|
| Spend Report | `/reports/spend` | Live |
| Contract Report | `/reports/contracts` | Live |
| Forecast Report | `/reports/forecast` | Coming soon |
| Budget Report | `/reports/budget` | Coming soon |

**Spend Report** — KPI cards, monthly trend chart, spend-by-account-group donut, top vendors bar chart, insights panel, and CSV export.

**Contract Report** — Multi-year contracts only. Monthly dollar breakout across a calendar fiscal year. Months beyond the last signed PO line are projected at 100% renewal (shown in amber italic). Multi-select slicers for Vendor, Department, and Status.

### Budget Planning (`/budget-planning`)
Planned.

### Forecasting (`/forecasting`)
Planned.

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

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/auth/login` | Returns JWT + user object |
| `GET` | `/api/auth/me` | Current user (requires auth) |
| `GET` | `/api/spend/transactions` | Paginated, filtered, sorted spend |
| `GET` | `/api/spend/filter-options` | Cross-filtered slicer values |
| `GET` | `/api/contracts` | List all contracts with lines |
| `POST` | `/api/contracts` | Create contract with optional lines |
| `GET` | `/api/contracts/{id}` | Get a single contract |
| `PUT` | `/api/contracts/{id}` | Update contract header |
| `DELETE` | `/api/contracts/{id}` | Delete contract and all lines |
| `POST` | `/api/contracts/{id}/lines` | Add a line to a contract |
| `PUT` | `/api/contracts/{id}/lines/{line_id}` | Update a line |
| `DELETE` | `/api/contracts/{id}/lines/{line_id}` | Remove a line |
| `GET` | `/api/contracts/report?fiscal_year={year}` | Monthly breakout report |

---

## Detailed Guides

Full feature documentation is in the [`docs/`](docs/) folder:

| Document | Description |
|---|---|
| [spend_analytics_guide.md](docs/spend_analytics_guide.md) | Spend Analytics page, Spend Report, filters, API, data model |
| [contract_database_guide.md](docs/contract_database_guide.md) | Contract Database, billing intervals, multi-year detection, Contract Report business rules, API, data model |
| [spend_management_setup.docx](docs/spend_management_setup.docx) | Initial dev environment setup (session 1) |

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
