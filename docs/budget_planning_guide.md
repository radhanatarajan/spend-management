# Budget Planning Module

**Feature Guide — Spend Management Platform**

---

## 1. Overview

The Budget Planning module supports annual budget preparation across two distinct cost categories: **Non-Controllable** (headcount-driven spend like salaries) and **Controllable** (vendor contracts and discretionary spend). Each category is planned independently with its own scenario model, and the results are consolidated in the Budget Report.

**Navigation**

| Path | Purpose |
|---|---|
| `/budget-planning` | Main planning hub — tabs for NC, CTRL, and comparisons |
| `/budget-planning` → Non-Controllable tab | NC budget entry and actuals comparison |
| `/budget-planning` → NC Scenario Comparison tab | Side-by-side NC scenario delta view |
| `/budget-planning` → Controllable tab | CTRL budget entry and contract baseline |
| `/budget-planning` → Ctrl Scenario Comparison tab | Side-by-side CTRL scenario delta view |
| `/reports/budget` | Combined NC + CTRL budget report with dynamic group-by |
| `/reports/budget-audit` | Full audit trail for all budget changes |

**Fiscal year convention** — Jan–Dec calendar year. FY2027 = Jan 2027 – Dec 2027. Prior year for actuals baseline = FY - 1.

---

## 2. Core Concepts

| Concept | Description |
|---|---|
| **Scenario** | A named planning version for one FY and one budget type (NON_CONTROLLABLE or CONTROLLABLE). Scenarios are independent; one per type is marked `is_baseline`. |
| **Baseline scenario** | The canonical version used by the Budget Report and comparison defaults. Only BizAdmin/Admin can set. |
| **NC Entry** | A department-level quarterly budget amount, one row per (scenario, department, entry_type). Entry types: `APPROVED_REC` and `ADDITIONAL_ASK`. |
| **CTRL Entry** | An activity-level quarterly budget amount, tied to a vendor contract or a free-form new request. Entry categories: `EXISTING` and `NEW_REQUEST`. |
| **Line Override** | A per-scenario decision to keep, cancel, or replace the contracted spend for one contract line. Affects the CTRL plan view only; the underlying contract is unchanged. |
| **Activity ID** | Unique identifier linking spend, contracts, and budget entries. NC entries use `NC-{dept_code}-{account}` format; CTRL entries use `AOPEX-NNNNNNN` or `ACAPEX-NNNNNNN`. |
| **NC Config** | FY-level configuration that controls which cost elements and account groups are shown in the NC planning view, and where the actuals cutoff falls. |

---

## 3. Status State Machine

Both NC entries (`budget_entries`) and CTRL entries (`controllable_budget_entries`) share the same status lifecycle.

```
              ┌──────────────────────────────────────────┐
              ▼                                          │
   DRAFT ──► READY_FOR_REVIEW ──► APPROVED ──► FINAL   │  (ADMIN only: FINAL → APPROVED)
     ▲              │                  │                │
     │              ▼                  ▼                │
     │          CANCELLED ◄────────────┘                │
     │                                                   │
     └─────────────── (ADMIN only: CANCELLED → DRAFT) ──┘
```

| Transition | Who can trigger |
|---|---|
| DRAFT → READY_FOR_REVIEW | Service Owner, BizAdmin, Admin |
| DRAFT → CANCELLED | Service Owner, BizAdmin, Admin |
| READY_FOR_REVIEW → DRAFT | BizAdmin, Admin |
| READY_FOR_REVIEW → APPROVED | BizAdmin, Admin |
| READY_FOR_REVIEW → CANCELLED | BizAdmin, Admin |
| APPROVED → READY_FOR_REVIEW | BizAdmin, Admin |
| APPROVED → FINAL | BizAdmin, Admin |
| APPROVED → CANCELLED | BizAdmin, Admin |
| FINAL → APPROVED | Admin only |
| CANCELLED → DRAFT | Admin only |

**FINAL entries** cannot have their amounts edited. Activity ID linking is still permitted after finalization (to associate a newly created reference ID with an existing entry).

---

## 4. Non-Controllable Planning

### 4.1 What is Non-Controllable?

Non-Controllable spend is headcount-driven — primarily salaries, benefits, and employee-related costs. Departments cannot reduce this spend without headcount decisions. The NC budget is planned at the department level with two entry types:

| Entry Type | Meaning |
|---|---|
| `APPROVED_REC` | The department's recommended (baseline) budget for the year |
| `ADDITIONAL_ASK` | An above-baseline request, subject to separate approval |

Each NC entry carries default metadata: `expense_type = Opex` and `activity_id = NC-{dept_code}-ACC-0301` (the Salaries account), assigned automatically on server startup. These link NC entries to the reference data layer for dimension-based reporting.

### 4.2 NC Configuration

Before planning begins, BizAdmin must configure the NC view for the fiscal year:

**Cost Elements** — Filters which spend rows from the prior year are included in the "Current (Actuals + Forecast)" baseline. Typically set to `Employee Related` to isolate headcount spend.

**Account Groups / Sub Groups** — Further narrows the actuals to specific account groupings (e.g., `Labor → Salaries`).

**Actuals Cutoff Month** — The last month for which real spend data is available. Months up to and including the cutoff show actual amounts; months after the cutoff are **carried forward** (see §4.3).

Config is stored in `budget_nc_config` with a full audit trail. Changes take effect immediately on the NC planning view.

### 4.3 Actuals Carry-Forward Logic

The NC view shows a "Current (Actuals + Forecast)" row alongside user-entered budget amounts. The current row is built as follows:

1. Pull prior FY spend filtered by selected cost elements, account groups, and account sub-groups.
2. For months **≤ cutoff_month_key**: use actual spend amounts from the database.
3. For months **> cutoff_month_key**: repeat the spend from the **last actual month at or before the cutoff** as a carry-forward estimate.
4. Aggregate into Q1–Q4 buckets for the **planning FY** (not the prior year).

If no cutoff is configured, the system auto-detects the last available month in the prior year's spend data.

### 4.4 NC Scenario Workflow

1. **BizAdmin creates a scenario** — assigns a name and fiscal year. The name is auto-prefixed with `NC ` on creation. The first scenario for a FY becomes the baseline.
2. **Copy from existing** — a scenario can be cloned from any other NC scenario of the same FY, copying all entries and resetting their statuses to DRAFT.
3. **Service Owners enter amounts** — edit quarterly cells for their departments in `APPROVED_REC` and/or `ADDITIONAL_ASK` rows.
4. **Submit for review** — Service Owner moves entries to READY_FOR_REVIEW.
5. **BizAdmin reviews** — approves or returns to DRAFT.
6. **Finalize** — BizAdmin moves approved entries to FINAL to lock amounts.

### 4.5 NC Planning View Features

- **KPI strip**: FY Actuals total, FY Forecast total, Approved Rec total, Additional Ask total, Ask Delta (as % of Approved Rec).
- **Department filter**: multi-select; totals recalculate client-side immediately.
- **Inline editing**: click any quarterly cell to enter an amount; saves on blur.
- **Scenario switcher**: compact dropdown in the KPI strip area.
- **Audit log panel**: collapsible, shows all changes made to the current scenario.
- **What-If panel**: experimental scenario creator for quick modelling.

---

## 5. Controllable Planning

### 5.1 What is Controllable?

Controllable spend is vendor-driven — software licenses, SaaS subscriptions, professional services, and similar contracted costs. Departments can renegotiate or cancel these. Each line is tied to an `activity_id` that links the contract database to the budget.

CTRL entries have two categories:

| Category | Meaning |
|---|---|
| `EXISTING` | A vendor relationship already reflected in a signed contract. Auto-seeded from active/pending contracts. |
| `NEW_REQUEST` | A net-new spend request with no existing contract. Added manually by Service Owners. |

### 5.2 Contract Seeding

When a new CONTROLLABLE scenario is created **without** copying from another scenario, the system automatically seeds one `EXISTING` entry per distinct `activity_id` found in active or pending contract lines whose service period overlaps the planning FY. This gives planners a pre-populated baseline of all known contracted spend.

Copying from an existing scenario transfers its entries (including manual `NEW_REQUEST` entries) with statuses reset to DRAFT.

### 5.3 Contract Line Overrides

Each `EXISTING` entry in a CTRL scenario shows the underlying contract lines. Planners can override how each line contributes to the budget:

| Action | Effect |
|---|---|
| **Keep** (default) | Use the contracted monthly amounts for FY quarters |
| **Cancel** | Treat this line as zero spend for budget purposes (does not cancel the actual contract) |
| **Extend** | Replace contracted amounts with manually entered quarterly amounts |

Overrides are stored in `controllable_line_overrides` and are scenario-scoped. The "Current + Forecast" column always shows the raw contracted total, regardless of overrides; overrides only affect the budget plan.

### 5.4 New Requests

Service Owners add net-new spend via the **New Controllable Request** modal:

Required fields:
- **Label** — descriptive name for the spend item
- **Department**, **Cost Element**, **Expense Type** (Opex/Capex)
- Quarterly amounts (Q1–Q4)

Optional fields: Account Group, Account Sub Group.

`NEW_REQUEST` entries start without an activity ID. Once BizAdmin is ready to formalize the request, they use **Create Activity ID** to generate and assign an ID:
- Expense Type = Opex → ID format `AOPEX-NNNNNNN`
- Expense Type = Capex → ID format `ACAPEX-NNNNNNN`

The generated ID is inserted into `activity_ids` reference data and linked to the CTRL entry, enabling it to appear in spend reports and the Budget Report.

### 5.5 CTRL Planning View Features

- **KPI strip**: Current + Forecast (contracted), Budget Total (user-entered), Variance (Budget − C+F).
- **Client-side filters**: Department, Cost Element, Account Group, Account Sub Group, Activity ID.
- **Actuals Cutoff Control**: same mechanism as NC — affects the "Current" column display.
- **Inline editing**: quarterly cells for each entry; saves on blur.
- **Contract line drawer**: each EXISTING row can expand to show individual contract lines and their override controls.

---

## 6. Scenario Comparison

Both NC and CTRL have dedicated comparison views that show two scenarios side by side.

### NC Comparison

Compares `APPROVED_REC` and `ADDITIONAL_ASK` totals per department across two scenarios. Displays:
- Quarterly amounts (Q1–Q4) for each entry type in Scenario A and B
- Delta ($) and delta (%) columns
- Department filter, KPI cards for FY totals and overall variance

### CTRL Comparison

Compares budget plan totals per department, broken out by activity ID (with entry label). Displays:
- Collapsible department groups — click any row to expand/collapse
- Budget total per activity, per scenario, plus delta
- Subtotal row per department with department-level deltas
- Grand total row

---

## 7. Budget Report

The Budget Report (`/reports/budget`) consolidates NC and CTRL entries into a single flat table with flexible grouping.

### 7.1 Scenario Selection

Two independent dropdowns: one for the NC scenario, one for the CTRL scenario. Both default to their respective baselines. Changing the FY resets both selections.

### 7.2 Group-By Dimensions

Up to 8 dimensions can be combined as checkboxes. At least one must always remain checked. The table reshapes dynamically — one column per checked dimension, one row per unique combination.

| Dimension | NC value | CTRL value |
|---|---|---|
| Department | Department name | From entry or enriched via ActivityId join |
| Entry Type | `APPROVED_REC` or `ADDITIONAL_ASK` | `EXISTING` or `NEW_REQUEST` |
| Expense Type | `Opex` (default) | From entry |
| Cost Element | `Employee Related` (via ACC-0301) | From entry or ActivityId join |
| Account Group | `Labor` (via ACC-0301) | From entry or ActivityId join |
| Acct Sub Group | `Salaries` (via ACC-0301) | From entry or ActivityId join |
| Account Number | `ACC-0301` (via ActivityId join) | From ActivityId join |
| Activity ID | `NC-{dept_code}-ACC-0301` | Entry's activity_id |

NC rows with no value for a given dimension show `(NC)`. CTRL rows with no enriched value show `(unknown)`.

### 7.3 Metrics

Columns: Q1 (Jan–Mar) | Q2 (Apr–Jun) | Q3 (Jul–Sep) | Q4 (Oct–Dec) | FY Total (indigo, bold).

A totals footer sums all visible rows.

---

## 8. Data Model

### Tables

| Table | Purpose |
|---|---|
| `budget_scenarios` | Scenario headers — one per FY + budget_type |
| `budget_entries` | NC budget amounts — one per (scenario, department, entry_type) |
| `budget_nc_config` | FY-level NC filter config and actuals cutoff |
| `controllable_budget_entries` | CTRL budget amounts — one per (scenario, activity_id) |
| `controllable_line_overrides` | Per-scenario keep/cancel/extend decisions for contract lines |
| `budget_scenario_audit` | Audit trail for scenario create/update/delete |
| `budget_entry_audit` | Audit trail for NC entry amount and status changes |
| `budget_nc_config_audit` | Audit trail for NC config changes |
| `controllable_budget_audit` | Audit trail for CTRL entry changes |

### Views

| View | Purpose |
|---|---|
| `v_budget_entry_audit` | Unpacked JSON audit log for NC entries (used by Budget Change Log report) |
| `v_budget_scenario_audit` | Unpacked JSON audit log for scenarios |
| `v_budget_nc_config_audit` | Unpacked JSON audit log for NC config |
| `v_controllable_budget_audit` | Unpacked JSON audit log for CTRL entries |

### Key Constraints

- `budget_entries`: unique on `(scenario_id, department_name, entry_type)`
- `controllable_budget_entries`: unique on `(scenario_id, activity_id)`
- `controllable_line_overrides`: unique on `(scenario_id, contract_line_id)`
- `budget_nc_config`: unique on `fiscal_year`

---

## 9. API Reference

All endpoints are under `/api/budget`. Authentication required for all routes.

### Scenarios

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/scenarios` | Any | List scenarios; filter by `fiscal_year` + `budget_type` |
| `POST` | `/scenarios` | BizAdmin | Create scenario; optionally copy from existing |
| `PUT` | `/scenarios/{id}` | BizAdmin | Rename / update description |
| `DELETE` | `/scenarios/{id}` | BizAdmin | Delete (baseline scenarios cannot be deleted) |
| `GET` | `/scenario-audit` | Any | Audit trail; filter by `scenario_id` or `fiscal_year` |

### NC Configuration

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/config` | Any | Load NC config for `fiscal_year`; auto-creates empty record if missing |
| `PUT` | `/config` | BizAdmin | Save cost element / account group selections and cutoff month |
| `GET` | `/config/audit` | Any | Audit trail for config changes |

### Reference Filters

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/cost-elements` | Any | Distinct cost elements from spend table |
| `GET` | `/account-groups` | Any | Distinct account groups from spend table |
| `GET` | `/account-sub-groups` | Any | Distinct account sub-groups from spend table |

### NC Planning

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/non-controllable` | Any | Full NC plan: actuals + budget rows per department |
| `PUT` | `/entries` | Write | Upsert NC entry (create or update by scenario + dept + type) |
| `DELETE` | `/entries/{id}` | Write | Delete NC entry |
| `PATCH` | `/entries/{id}/status` | Write | Transition entry status |
| `GET` | `/audit` | Any | NC entry audit log for a scenario |

### CTRL Planning

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/controllable` | Any | Full CTRL plan: contracted rows + overrides + budget entries |
| `PUT` | `/controllable/entries` | Write | Upsert CTRL entry |
| `DELETE` | `/controllable/entries/{id}` | Write | Delete CTRL entry |
| `PATCH` | `/controllable/entries/{id}/status` | Write | Transition CTRL entry status |
| `PUT` | `/controllable/line-overrides` | Write | Set keep/cancel/extend for a contract line |

### Comparison & Reporting

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/compare` | Any | NC scenario comparison (delta by department) |
| `GET` | `/controllable/compare` | Any | CTRL scenario comparison (delta by activity) |
| `GET` | `/reports/budget` | Any | Combined NC + CTRL report; auto-resolves baselines if no IDs given |
| `GET` | `/reports/audit` | Any | Combined NC + CTRL audit change log for a FY |

---

## 10. Roles and Permissions Summary

| Action | Read Only | Service Owner | BizAdmin | Admin |
|---|---|---|---|---|
| View planning pages and reports | ✓ | ✓ | ✓ | ✓ |
| Edit NC/CTRL entry amounts | — | ✓ | ✓ | ✓ |
| Submit for review (→ READY_FOR_REVIEW) | — | ✓ | ✓ | ✓ |
| Cancel entries | — | ✓ | ✓ | ✓ |
| Approve entries (→ APPROVED) | — | — | ✓ | ✓ |
| Finalize entries (→ FINAL) | — | — | ✓ | ✓ |
| Unlock FINAL (→ APPROVED) | — | — | — | ✓ |
| Restore CANCELLED (→ DRAFT) | — | — | — | ✓ |
| Create / delete scenarios | — | — | ✓ | ✓ |
| Update NC config | — | — | ✓ | ✓ |
| Delete baseline scenarios | — | — | — | — |

---

## 11. Seed Data

On first server startup, the following budget data is seeded (skipped if already present):

**NC Scenarios (FY2027)**
- `NC Baseline 2027` — baseline; 8 departments × 2 entry types (APPROVED_REC + ADDITIONAL_ASK), all in DRAFT/READY_FOR_REVIEW
- `NC What-If Stretch` — non-baseline alternative scenario

**CTRL Scenarios (FY2027)**
- `C Baseline 2027` — baseline; auto-seeded from active/pending contracts in FY2027
- `C Conservative` — non-baseline; cloned from baseline with some overrides

**NC entry defaults (all seeded entries)**
- `expense_type`: Opex
- `activity_id`: `NC-{dept_code}-ACC-0301` (e.g., `NC-1100-ACC-0301` for Engineering)

These can be found in `server/src/db/init_db.py` → `_seed_budget()`.
