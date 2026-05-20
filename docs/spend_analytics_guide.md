# Spend Analytics Module

**Feature Guide — Spend Management Platform**

---

## 1. Overview

The Spend Analytics module is the primary data-exploration surface of the platform. It presents all Oracle-aligned General Ledger (GL) spend transactions in a fully interactive table with cross-dependent slicers, multi-column sorting, pagination, KPI summary cards, and a dedicated Spend Report page with charts and CSV export.

**Navigation**
- Spend Analytics table → `/spend`
- Spend Report (charts + export) → `/reports/spend`

**Seed data** — ~150 synthetic transactions are loaded on first startup across 8 vendors, multiple departments, and the last 12 months. Seeding is skipped if rows already exist.

---

## 2. Spend Analytics Page (`/spend`)

### 2.1 KPI Summary Strip

Four metric cards sit above the table and update in real time as filters change:

| Card | Metric |
|---|---|
| Total Spend | Sum of `amount_usd` across all filtered rows |
| Transactions | Row count after filters are applied |
| Avg per Month | Total spend ÷ distinct months in the filtered result |
| Top Vendor | Vendor name with the highest aggregate spend |

### 2.2 Slicer Filters

Seven dropdown slicers appear above the table. Each slicer shows only the values present in the data **after the other slicers are applied** (cross-dependent filtering). Selecting a value triggers a backend query that re-fetches both the transaction list and the available filter options.

| Slicer | Field | Notes |
|---|---|---|
| Month | `month_key` | YYYYMM integer; displayed as `Jan '25` |
| Expense Type | `expense_type` | Capex, Opex, Travel, etc. |
| Company Code | `company_code` | Oracle company identifier |
| Department | `oracle_department` | Oracle dept code + name |
| Acct Group | `oracle_account_group` | R&D, S&M, G&A, Infra, … |
| Vendor | `vendor_name` | Supplier name |
| JE Source | `je_source` | Coupa, Concur, Workday, Oracle, Manual |

- Select one or multiple values per slicer.
- Click **Apply Filters** to update the table.
- Click **Clear** inside a slicer to reset only that filter.
- Click **Reset All** to clear every filter simultaneously.

### 2.3 Transaction Table

The table shows up to 50 rows per page by default. Each column header is clickable for ascending/descending sort. The header uses a two-row grouped layout to cluster related Oracle columns.

| Column | Field | Notes |
|---|---|---|
| Month | `month_label` | Derived from `month_key` |
| Expense Type | `expense_type` | |
| Co. Code | `company_code` | |
| Oracle Org | `oracle_organization` | Business unit |
| Acct No. | `oracle_account_number` | GL account number |
| Dept Code | `oracle_department` | |
| Dept Name | `oracle_department_name` | |
| Hierarchy | `oracle_cost_center_hierarchy` | Cost center rollup |
| Acct Group | `oracle_account_group` | |
| Acct Sub-Group | `oracle_account_sub_group` | |
| Cost Element | `oracle_cost_element` | Salaries, Licenses, … |
| Line Desc | `line_desc` | Free-text description |
| Vendor | `vendor_name` | |
| PO | `po_recon` | Hover for description |
| PO Number | `purchase_order_number` | |
| PO Line | `purchase_order_line_number` | |
| Invoice No. | `invoice_number` | |
| Invoice Line | `invoice_line_number` | |
| JE Source | `je_source` | |
| $ | `amount_usd` | USD, right-aligned |

### 2.4 Pagination

- Default page size: 50 rows.
- Page controls appear at the bottom of the table.
- Total row count is shown in the summary strip.

---

## 3. Spend Report Page (`/reports/spend`)

The Spend Report page provides an executive-level view with KPI cards, charts, a period comparison panel, and CSV export.

### 3.1 Financial Period Picker

Pill buttons at the top-right select the reporting window. The selected period filters all KPIs, charts, and the insights panel.

### 3.2 KPI Cards

| Card | Description |
|---|---|
| Total Spend | Sum of all transactions in the selected period |
| Transactions | Count of GL lines in the period |
| Top Vendor | Vendor with highest aggregate spend |
| Avg / Month | Total spend divided by months in the period |

### 3.3 Charts

| Chart | Description |
|---|---|
| Monthly Spend Trend | Bar chart of spend per month in the period |
| Spend by Account Group | Donut chart (R&D, S&M, G&A, Infra, …) |
| Top Vendors by Spend | Horizontal bar chart, top 8 vendors |
| Spend by Department | Breakdown across Oracle departments |

### 3.4 Insights Panel

Auto-generated text highlights the largest spend category, the fastest-growing vendor, and period-over-period change.

### 3.5 CSV Export

The **Download CSV** button exports all transactions matching the current filter to a comma-separated file including all 20 GL columns.

---

## 4. API Reference

Base URL: `http://localhost:8000` — Swagger UI: `http://localhost:8000/docs`

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/spend/transactions` | Paginated, filtered, sorted transaction list |
| `GET` | `/api/spend/filter-options` | Distinct slicer values (cross-filtered by active filters) |

### 4.1 `GET /api/spend/transactions` — Query Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number (1-indexed) |
| `page_size` | int | 50 | Rows per page |
| `sort_by` | string | `month_key` | Column to sort by |
| `sort_dir` | string | `desc` | `asc` or `desc` |
| `month_key` | int[] | — | Filter by one or more YYYYMM keys |
| `expense_type` | str[] | — | Filter by expense type(s) |
| `company_code` | str[] | — | Filter by company code(s) |
| `oracle_department` | str[] | — | Filter by department code(s) |
| `oracle_account_group` | str[] | — | Filter by account group(s) |
| `vendor_name` | str[] | — | Filter by vendor name(s) |
| `je_source` | str[] | — | Filter by journal entry source(s) |

### 4.2 `GET /api/spend/filter-options`

Accepts the same filter parameters as `/transactions`. Returns distinct values for each slicer dimension constrained to rows that match the currently applied filters (cross-dependent filtering).

---

## 5. Data Model

### `spend_transactions` table

| Column | Type | Notes |
|---|---|---|
| `id` | INT PK | Auto-increment |
| `month_key` | INT | YYYYMM format, e.g. `202601` |
| `month_label` | VARCHAR | e.g. `Jan 2026` |
| `expense_type` | VARCHAR | Capex / Opex / Travel / … |
| `company_code` | VARCHAR | Oracle company code |
| `oracle_organization` | VARCHAR | Business unit |
| `oracle_account_number` | VARCHAR | GL account number |
| `oracle_department` | VARCHAR | Department code |
| `oracle_department_name` | VARCHAR | Department name |
| `oracle_cost_center_hierarchy` | VARCHAR | Rollup path |
| `oracle_account_group` | VARCHAR | R&D / S&M / G&A / … |
| `oracle_account_sub_group` | VARCHAR | Sub-classification |
| `oracle_cost_element` | VARCHAR | Salaries / Licenses / … |
| `line_desc` | VARCHAR | Free-text description |
| `vendor_name` | VARCHAR | Supplier name |
| `po_recon` | VARCHAR | PO reconciliation code |
| `purchase_order_number` | VARCHAR | |
| `purchase_order_line_number` | VARCHAR | |
| `invoice_number` | VARCHAR | |
| `invoice_line_number` | VARCHAR | |
| `je_source` | VARCHAR | Journal entry source |
| `amount_usd` | DECIMAL(14,2) | Transaction amount in USD |
