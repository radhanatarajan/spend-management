# Contract Database Module

**Feature Guide — Spend Management Platform**

---

## 1. Overview

The Contract Database module tracks software license agreements structured as Purchase Orders (POs). Each contract represents one PO header. A contract has one or more PO lines, where each line covers a service period (typically one year) with its own billing amount and interval.

**Navigation**
- Contract Database (CRUD) → `/contracts`
- Contract Report (monthly breakout) → `/reports/contracts`

**Seed data** — Four contracts are loaded on first startup (skipped if data already exists):

| Vendor | PO Number | Interval | Lines | Status |
|---|---|---|---|---|
| Salesforce | PO-83353 | Monthly | 3 (May-26 → Apr-29) | Active |
| GitHub | PO-91200 | Quarterly | 2 (Jan-26 → Dec-27) | Active |
| Workday | PO-77040 | Yearly | 1 (Apr-26 → Mar-27) | Active |
| Tableau | PO-60301 | Custom (total) | 3 (Jan-23 → Dec-25) | Expired |

---

## 2. Core Concepts

| Concept | Description |
|---|---|
| **Contract** | One PO header: vendor, department, account, PO number, status |
| **Contract Line** | One service period inside a PO: dates, billing interval, entered amount |
| **Monthly Amount** | Canonical per-month value stored on every line, derived from `entered_amount` + `billing_interval` on every write |
| **Multi-year** | A PO group whose lines form a **consecutive chain** (each line's end month + 1 = next line's start month) |
| **Renewal Assumption** | Months beyond the last signed PO line are projected forward at 100% of that line's rate — only for **active** or **pending** contracts |

---

## 3. Billing Intervals

Every PO line has a `billing_interval` that determines how `entered_amount` maps to `monthly_amount`. Both values are stored; `monthly_amount` is always the canonical per-month figure used in all reports and totals.

| Interval | Entered Amount Meaning | Monthly Amount Formula |
|---|---|---|
| **Monthly** | Amount charged per month | `= entered_amount` |
| **Quarterly** | Amount charged per quarter | `= entered_amount ÷ 3` |
| **Annual** | Amount charged per year | `= entered_amount ÷ 12` |
| **Custom (total)** | Total amount for the full service period | `= entered_amount ÷ months_in_period` |

`months_in_period = (end.year − start.year) × 12 + (end.month − start.month) + 1`

Changing the `billing_interval` or `entered_amount` on a line automatically recomputes and stores the new `monthly_amount`.

---

## 4. Multi-Year Detection

A contract group is classified as **multi-year** when it has at least two PO lines whose service periods are **consecutive** — the month immediately after line N ends is the month line N+1 starts.

### Consecutive month rule

For adjacent lines A and B (sorted by `period_start`):

```
next_month = 1              if A.period_end.month == 12
           else A.period_end.month + 1

next_year  = A.period_end.year + 1  if A.period_end.month == 12
           else A.period_end.year

is_consecutive = (B.period_start.year  == next_year  and
                  B.period_start.month == next_month)
```

### Examples

| Line A End | Line B Start | Consecutive? |
|---|---|---|
| 2026-04-30 | 2026-05-01 | ✅ Yes |
| 2026-12-31 | 2027-01-01 | ✅ Yes (year rollover) |
| 2026-04-30 | 2026-06-01 | ❌ No — gap of 1 month |
| 2026-04-30 | 2026-04-01 | ❌ No — overlap |

### Cross-contract grouping

Contracts are grouped **before** the consecutive check, using the key:

`vendor_name + oracle_department + oracle_account_number + purchase_order_number`

This means that if the same PO was entered as two separate Contract DB records (one per year), their lines are merged and the consecutive check is applied across both. This matches the grouping logic on the Contract Database page.

---

## 5. Contract Database Page (`/contracts`)

### 5.1 Grouping

Contracts are displayed grouped by `vendor + department + account + PO number`. If multiple Contract DB records share the same key their lines are merged under one row.

- Groups with 2+ consecutive lines display an indigo **Multi-year** badge.
- The **Terms** column shows the total number of PO lines (e.g. `3 years`).
- **Contract Value** is the sum of all line period totals across the group.
- **Status** reflects the contract that owns the last (most recent) line.

### 5.2 Status Filter

Pill buttons filter by contract status: **All · Active · Pending · Expired · Cancelled**. The summary strip shows the count of visible POs and total value.

### 5.3 Expanding a Group Row

Click any row to expand it. The panel shows:
- Optional contract description
- Lines sub-table: PO Line, Service Period, Months, Interval, Entered Amount, Monthly, Period Total, actions
- **+ Add line** form at the bottom

### 5.4 Editing Contract Lines (Inline)

Hover over any line row to reveal **Edit** and **✕** (delete) buttons. Clicking Edit turns the entire row into an inline form:

| Field | Notes |
|---|---|
| PO Line # | Integer ≥ 1 |
| Service Start | ISO date picker |
| Service End | ISO date picker |
| Interval | Monthly / Quarterly / Annual / Custom (total) |
| Entered Amount | Amount as entered under the chosen interval |
| Notes | Optional free-text |

- **Months** is computed live from the date fields.
- Monthly amount preview updates as you type.
- **Enter** saves · **Escape** cancels.
- On save the backend recomputes `monthly_amount` and stores both values.

### 5.5 Editing the Contract Header

Click the **Edit** button in the rightmost column to open the Edit Contract modal. Fields: Vendor Name, Department Code, Department Name, Account Number, Account Sub-Group, PO Number, Status, Description.

If the group spans multiple Contract DB records, the header update is applied to all records simultaneously.

### 5.6 Adding a New Contract

Click **+ New Contract** (top-right). The modal accepts all header fields plus one or more PO lines. Monthly amount preview appears for non-monthly intervals.

### 5.7 Deleting

- **Delete** on a group row: removes all Contract DB records in the group after confirmation.
- **✕** on a line: removes only that line.

---

## 6. Contract Report Page (`/reports/contracts`)

### 6.1 What Appears in the Report

**All contracts** that have actual or assumed coverage in the selected fiscal year are included — not just multi-year ones. A contract is excluded only if its FY total is zero (no actual lines covering the FY and no renewal assumption applies).

Rows are annotated with a **Multi-yr** badge when the group has 2+ consecutive lines.

### 6.2 Fiscal Year

The fiscal year is a **calendar year (Jan – Dec)**. FY 2027 covers January 2027 – December 2027. The FY picker (top-right) shows only years for which at least one contract has coverage.

### 6.3 Renewal Assumption Rules

For months that fall **after the last signed PO line**:

| Contract Status | Behaviour |
|---|---|
| **Active** | Months projected forward at **100%** of last line's `monthly_amount` — shown in amber italic with `~` prefix |
| **Pending** | Same as Active — renewal projected at 100% |
| **Expired** | **No assumption** — months beyond last line show `–` |
| **Cancelled** | **No assumption** — months beyond last line show `–` |

This means an expired contract will only show up in a FY if one of its actual PO lines covers a month within that year.

### 6.4 Month Coverage Logic (per month, per group)

```
1. If month < first line's start  → null (contract not yet started)
2. If month falls within a line   → actual amount, assumed = false
3. If month > last line's end AND status is active/pending
                                  → assumed amount (last line's rate), assumed = true
4. If month > last line's end AND status is expired/cancelled
                                  → null
5. If month falls in a gap between lines → null (data quality issue)
```

### 6.5 Slicers

Three multi-select pill slicers filter the report client-side: **Vendor**, **Department**, **Status**. The monthly totals row and all KPI cards update to reflect the filtered rows.

### 6.6 KPI Cards

| Card | Description |
|---|---|
| **Contracts** | Count of groups visible after slicers; sub-label shows how many are multi-year |
| **Vendors** | Distinct vendor count |
| **FY Total Value** | Sum of all monthly amounts (actual + assumed) across the FY |
| **Assumed (renewal)** | Portion of FY Total that is projected, not yet signed |

### 6.7 Monthly Table

Columns: **Vendor** (sticky), **Department**, **Account**, one column per month (12 total), **FY Total**.

- Footer row shows per-month totals and grand total.
- Actual amounts → dark monospace font.
- Assumed amounts → amber italic with `~` prefix, tooltip: `100% renewal assumption`.
- Months with no coverage → `–` in light gray.

---

## 7. API Reference

Base URL: `http://localhost:8000` — Swagger UI: `http://localhost:8000/docs`

All contract endpoints require a valid JWT (`Authorization: Bearer <token>`).

### 7.1 Contract CRUD

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/contracts` | List all contracts with lines, ordered by vendor name |
| `POST` | `/api/contracts` | Create a contract with optional PO lines |
| `GET` | `/api/contracts/{id}` | Get a single contract |
| `PUT` | `/api/contracts/{id}` | Update contract header fields (partial update supported) |
| `DELETE` | `/api/contracts/{id}` | Delete contract and all its lines |

### 7.2 Contract Line CRUD

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/contracts/{id}/lines` | Add a line; `monthly_amount` computed on write |
| `PUT` | `/api/contracts/{id}/lines/{line_id}` | Update a line; `monthly_amount` recomputed |
| `DELETE` | `/api/contracts/{id}/lines/{line_id}` | Remove a line |

### 7.3 Contract Report

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/contracts/report?fiscal_year={year}` | Monthly breakout for all contracts with FY coverage |

> **Note:** The `/report` route is declared before `/{id}` in the router to prevent FastAPI from matching `report` as a contract ID.

---

## 8. Data Model

### `contracts` table

| Column | Type | Notes |
|---|---|---|
| `id` | INT PK | Auto-increment |
| `vendor_name` | VARCHAR | |
| `description` | TEXT | Optional |
| `oracle_department` | VARCHAR | Dept code, e.g. `1200` |
| `oracle_department_name` | VARCHAR | Dept name, e.g. `Sales` |
| `oracle_account_number` | VARCHAR | GL account, e.g. `ACC-6385` |
| `oracle_account_sub_group` | VARCHAR | e.g. `Software Licenses` |
| `purchase_order_number` | VARCHAR | e.g. `PO-83353` |
| `status` | ENUM | `active` / `pending` / `expired` / `cancelled` |
| `created_at` | DATETIME | Auto-set on insert |
| `updated_at` | DATETIME | Auto-updated on save |

### `contract_lines` table

| Column | Type | Notes |
|---|---|---|
| `id` | INT PK | Auto-increment |
| `contract_id` | INT FK | → `contracts.id` (cascade delete) |
| `po_line_number` | INT | PO line number, e.g. `4` |
| `period_start` | DATE | First day of the service period |
| `period_end` | DATE | Last day of the service period |
| `billing_interval` | ENUM | `monthly` / `quarterly` / `yearly` / `custom` |
| `entered_amount` | DECIMAL(14,2) | Amount as entered under the chosen interval |
| `monthly_amount` | DECIMAL(14,2) | Computed per-month value; recomputed on every save |
| `notes` | TEXT | Optional free-text note |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | |

### Computed fields (not stored in DB)

| Field | Formula |
|---|---|
| `months_in_period` | `(end.year − start.year) × 12 + (end.month − start.month) + 1` |
| `total_amount` | `monthly_amount × months_in_period` |
| `contract_total` | Sum of `total_amount` across all lines in the contract |
