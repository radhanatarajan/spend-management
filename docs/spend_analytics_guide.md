# Spend Analytics Module

**Feature Guide — Spend Management Platform**

---

## 1. Overview

The Spend Analytics module is the primary data-exploration surface of the platform. It presents all Oracle-aligned General Ledger (GL) spend transactions in a fully interactive table with cross-dependent slicers, multi-column sorting, pagination, KPI summary cards, and a dedicated Spend Report page with charts and CSV export.

**Navigation**
- Spend Analytics table → `/spend`
- Spend Report (charts + export) → `/reports/spend`

**Seed data** — ~177 synthetic transactions are loaded on first startup across multiple vendors, departments, and the last 6 months. Seeding is skipped if rows already exist.

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

Eight dropdown slicers appear above the table. Each slicer shows only the values present in the data **after the other slicers are applied** (cross-dependent filtering). Selecting a value triggers a backend query that re-fetches both the transaction list and the available filter options.

| Slicer | Field | Notes |
|---|---|---|
| Month | `month_key` | YYYYMM integer; displayed as `Jan 2026` |
| Expense Type | `expense_type` | CAPEX or OPEX |
| Company Code | `company_code` | Oracle company identifier |
| Oracle Dept | `oracle_department` | Oracle dept code + name |
| Acct. Group | `oracle_account_group` | R&D, S&M, G&A, Infra, … |
| Vendor | `vendor_name` | Supplier name |
| JE Source | `je_source` | Coupa, Concur, Workday, Oracle, Manual |
| Activity ID | `activity_id` | Stable cross-month identifier (see §5) |

All slicers support **partial-text search** — type in the dropdown to filter the option list before selecting.

- Select one or multiple values per slicer.
- The badge on each slicer button shows the active selection count.
- Click **Clear selection** inside a slicer to reset only that filter.

### 2.3 Transaction Table

The table shows up to 50 rows per page by default. Each column header is clickable for ascending/descending sort. The header uses a two-row grouped layout to cluster related Oracle columns.

| Column | Field | Notes |
|---|---|---|
| Activity ID | `activity_id` | Stable cross-month identifier; monospace font |
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
| Spend by Account Group | Horizontal bar chart ranked by amount (R&D, S&M, G&A, Infra, …) |
| Vendor Concentration | Donut chart — top 4 vendors + Others |
| Spend by Department | Horizontal bar chart across Oracle departments |
| Spend by Month | Bar chart of spend per month in the period |
| Spend by Cost Element | Horizontal bar chart across all cost elements (Salaries, Data Center, …) |
| Spend by Activity ID | Horizontal bar chart, top 15 activity IDs by spend; scrollable |

### 3.4 Insights Panel

Auto-generated text highlights the largest spend category, the fastest-growing vendor, and period-over-period change.

### 3.5 CSV Export

The **Export CSV** button exports all transactions matching the current period filter to a comma-separated file. The first column is `Activity ID`, followed by all 21 GL columns.

---

## 4. API Reference

Base URL: `http://localhost:8000` — Swagger UI: `http://localhost:8000/docs`

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/spend/transactions` | Paginated, filtered, sorted transaction list |
| `GET` | `/api/spend/filter-options` | Distinct slicer values (cross-filtered by active filters) |
| `GET` | `/api/spend/summary` | Aggregated totals and breakdowns for the report page |
| `GET` | `/api/spend/export` | Download filtered transactions as a CSV file |

### 4.1 Common Filter Parameters

All four endpoints accept the same set of filter query parameters:

| Parameter | Type | Description |
|---|---|---|
| `month_keys` | int[] | Filter by one or more YYYYMM keys |
| `expense_types` | str[] | Filter by expense type(s) |
| `company_codes` | str[] | Filter by company code(s) |
| `oracle_departments` | str[] | Filter by department code(s) |
| `oracle_account_groups` | str[] | Filter by account group(s) |
| `vendors` | str[] | Filter by vendor name(s) |
| `je_sources` | str[] | Filter by journal entry source(s) |
| `activity_ids` | str[] | Filter by Activity ID(s) |

### 4.2 `GET /api/spend/transactions` — Additional Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number (1-indexed) |
| `page_size` | int | 50 | Rows per page (max 200) |
| `sort_by` | string | `month_key` | Column to sort by |
| `sort_order` | string | `desc` | `asc` or `desc` |

### 4.3 `GET /api/spend/filter-options`

Returns distinct values for each slicer dimension, cross-filtered by all **other** active slicers. For example, selecting dept `1100` narrows the vendor list to vendors with Engineering spend — but the dept slicer itself still shows all departments.

Response includes: `months`, `expense_types`, `company_codes`, `oracle_departments`, `oracle_account_groups`, `vendors`, `je_sources`, `activity_ids`.

### 4.4 `GET /api/spend/summary`

Returns aggregated breakdowns used by the Spend Report page:

| Field | Description |
|---|---|
| `total_amount` | Sum of all filtered transactions |
| `total_transactions` | Count of filtered rows |
| `by_account_group` | Amount + % per account group, sorted descending |
| `by_vendor` | Top 8 vendors by amount |
| `by_department` | Amount per department, sorted descending |
| `by_month` | Amount per month, sorted ascending by `month_key` |
| `by_cost_element` | Amount per cost element, sorted descending |
| `by_activity_id` | Top 15 activity IDs by amount |

---

## 5. Data Model

### `spend` table

| Column | Type | Notes |
|---|---|---|
| `id` | INT PK | Auto-increment |
| `month_key` | INT | YYYYMM format, e.g. `202601` |
| `month_label` | VARCHAR(20) | e.g. `Jan 2026` |
| `expense_type` | VARCHAR | `CAPEX` or `OPEX` |
| `company_code` | VARCHAR | Oracle company code |
| `oracle_organization` | VARCHAR | Business unit |
| `oracle_account_number` | VARCHAR | GL account number |
| `oracle_department` | VARCHAR | Department code |
| `oracle_department_name` | VARCHAR | Department name |
| `oracle_cost_center_hierarchy` | VARCHAR | Rollup path |
| `oracle_account_group` | VARCHAR | R&D / S&M / G&A / … |
| `oracle_account_sub_group` | VARCHAR | Sub-classification |
| `oracle_cost_element` | VARCHAR | Salaries / Data Center / … |
| `line_desc` | TEXT | Free-text description (nullable) |
| `vendor_name` | VARCHAR | Supplier name |
| `po_recon` | VARCHAR | PO reconciliation flag (nullable) |
| `po_description` | TEXT | PO description (nullable) |
| `purchase_order_number` | VARCHAR | (nullable) |
| `purchase_order_line_number` | VARCHAR | (nullable) |
| `invoice_number` | VARCHAR | (nullable) |
| `invoice_line_number` | VARCHAR | (nullable) |
| `je_source` | VARCHAR | Journal entry source (nullable) |
| `activity_id` | VARCHAR(20) | Cross-month stable identifier (nullable, indexed) |
| `amount_usd` | DECIMAL(14,2) | Transaction amount in USD |

### Activity ID

Activity IDs group logically related spend rows across months so a recurring charge on the same PO (or the same department payroll bucket) can be tracked over time.

**Format:** `ACAPEX-NNNNNNN` for CAPEX rows, `AOPEX-NNNNNNN` for OPEX rows (7-digit zero-padded sequential number per prefix).

**Grouping rules:**

| Condition | Group key (rows that share the same ID) |
|---|---|
| Has `purchase_order_number` | `expense_type` + `purchase_order_number` + `purchase_order_line_number` |
| No PO and `oracle_cost_element = 'Employee Related'` | `expense_type` + `oracle_department` + `oracle_cost_element` + `oracle_account_sub_group` |
| No PO, all other cost elements | `expense_type` + `vendor_name` + `oracle_cost_element` + `oracle_account_sub_group` |

IDs are assigned by running `server/scripts/populate_activity_ids.py` against the live database. The script is idempotent — re-running it will overwrite existing IDs with freshly computed ones.
