# Reference Data Module

**Feature Guide — Spend Management Platform**

---

## 1. Overview

The Reference Data module provides master data management for four entity types that are used to classify and contextualize spend transactions: **Departments**, **Account Numbers**, **Project IDs**, and **Activity IDs**. These tables bridge the raw Oracle GL data in the `spend` table to structured, human-readable classifications used in budgeting, reporting, and analytics.

**Navigation** (all under the Reference section in the sidebar)

| Page | URL | Entity |
|---|---|---|
| Departments | `/reference/departments` | Oracle department codes and names |
| Account Numbers | `/reference/accounts` | GL account numbers with group/cost-element classification |
| Project IDs | `/reference/projects` | Project buckets that group related activity IDs |
| Activity IDs | `/reference/activities` | Cross-month stable spend identifiers |

**Access control** — All reference pages are visible to every authenticated user. Create, edit, and delete operations require a `SERVICE_OWNER`, `BIZ_ADMIN`, or `ADMIN` role. Users with the `READ_ONLY` role see the data but not the Add/Edit/Delete controls.

**Seed data** — On first startup the server seeds departments from the eight Oracle department codes, seeds account numbers from every distinct `oracle_account_number` in the spend table, seeds 12 project IDs, and seeds one activity ID record per distinct `activity_id` in spend. Seeding is skipped if any rows already exist in the respective table. A backfill function runs every startup to add any new spend rows whose activity IDs, account numbers, or department codes are not yet in the reference tables.

---

## 2. Departments (`/reference/departments`)

### 2.1 Purpose

Maps Oracle department codes (e.g. `1100`) to human-readable department names (e.g. `Engineering`). Every spend row carries an `oracle_department` code; this table is the authoritative source for resolving that code to a name.

### 2.2 Table Columns

| Column | Description |
|---|---|
| Code | Oracle department code — primary key, immutable after creation |
| Name | Human-readable department name |

### 2.3 Create

Click **Add Department**. Both fields are required. The department code must be unique — a duplicate code is rejected with an inline error before the form is submitted.

### 2.4 Edit

Click **Edit** on any row. Only the department name can be updated; the code is fixed and displayed as read-only.

### 2.5 Delete

Click **Delete** and confirm. A department cannot be deleted if any Activity ID record references it — the API returns a `409 Conflict` in that case.

### 2.6 Seed Data

The following eight departments are seeded on first startup:

| Code | Name |
|---|---|
| 1100 | Engineering |
| 1200 | Sales |
| 1300 | Finance |
| 1400 | Marketing |
| 1500 | Operations |
| 1600 | HR |
| 1700 | Legal |
| 1800 | IT |

---

## 3. Account Numbers (`/reference/accounts`)

### 3.1 Purpose

Maps GL account numbers to an account group / sub-group / cost element classification hierarchy. Each account number also carries an optional free-text description. Account numbers are referenced by Activity IDs to indicate the primary GL account for a recurring spend pattern.

### 3.2 Display Code

Account numbers use a surrogate integer primary key. The human-facing display code is auto-generated as `ACC-{id:04d}` (e.g. `ACC-0042`) at creation time and is immutable. The display code corresponds to the `oracle_account_number` value found in the spend table.

### 3.3 Table Columns

| Column | Description |
|---|---|
| Account # | Auto-generated display code (`ACC-XXXX`) — immutable |
| Description | Optional free-text description |
| Group | Account group (e.g. `Data Services`, `Labor`) |
| Sub-Group | Optional sub-classification (e.g. `DC Power`, `DC Rent`) |
| Cost Element | Cost element classification (e.g. `Data Center`, `Salaries`) |

### 3.4 Filters

The filter bar provides four independent controls:

| Filter | Behaviour |
|---|---|
| Search | Partial-text match across account number, description, group, sub-group, and cost element simultaneously |
| Acct. Group | Multi-select dropdown; options narrow based on active Sub-Group and Cost Element selections (faceted) |
| Sub-Group | Multi-select dropdown; options narrow based on active Group and Cost Element selections (faceted) |
| Cost Element | Multi-select dropdown; options narrow based on active Group and Sub-Group selections (faceted) |

All filtering is client-side — the full account list is fetched once and filtered in the browser with no additional API calls.

**Clear all** appears in the filter bar whenever any filter is active.

### 3.5 Create

Click **Add Account**. Account Group and Cost Element are required. The server auto-generates the display code. A combination of (Account Group + Account Sub-Group + Cost Element) must be unique; duplicates are detected client-side and the submit button is disabled with an inline error.

### 3.6 Edit

Click **Edit**. The display code is shown as read-only. Description, Group, Sub-Group, and Cost Element can all be changed. Duplicate-combination validation applies on edit as well (the currently edited record is excluded from the check).

### 3.7 Delete

Click **Delete** and confirm. An account cannot be deleted if any Activity ID record references it.

### 3.8 Gap View

The SQL view `v_spend_account_gaps` lists every distinct `oracle_account_number` in the `spend` table that has no matching row in `account_numbers`. Query it directly to monitor coverage:

```sql
SELECT * FROM v_spend_account_gaps;
```

A zero-row result means all spend account numbers are represented in the reference table.

---

## 4. Project IDs (`/reference/projects`)

### 4.1 Purpose

Project IDs are logical buckets that group related Activity IDs into named spend programmes. Each project can be linked to one or more departments.

### 4.2 Display Code

Project IDs use a surrogate integer primary key. The human-facing display code is auto-generated as `PRJ-{id:04d}` (e.g. `PRJ-0001`) and is immutable. The project name (e.g. `CAPEX-NET-INFRA`) is user-editable and must be unique.

### 4.3 Table Columns

| Column | Description |
|---|---|
| Project # | Auto-generated display code (`PRJ-XXXX`) — immutable |
| Project Name | Short descriptive name, unique across all projects |
| Departments | Badges listing the departments linked to this project |

### 4.4 Filters

A single **Department** multi-select dropdown filters the table to projects linked to the selected departments.

### 4.5 Create

Click **Add Project**. Project Name is required. Select zero or more departments from the checkbox list. The server auto-generates the display code. Duplicate project names are rejected with a `409 Conflict`.

### 4.6 Edit

Click **Edit**. The Project # is shown as read-only. Project Name and department assignments can be changed. Renaming to a name that already exists on another project is rejected.

### 4.7 Delete

Click **Delete** and confirm. A project cannot be deleted if any Activity ID record references it.

### 4.8 Seeded Projects

Twelve projects are seeded on first startup, derived from the expense type and account classification of spend data:

| Project # | Project Name | Category |
|---|---|---|
| PRJ-0001 | CAPEX-COMPUTE | Compute Hardware Capital (servers, PCs, peripherals) |
| PRJ-0002 | CAPEX-DC | Data Center Capital (DC Rent, hosted) |
| PRJ-0003 | CAPEX-MISC | Misc Capital (CIP, Fixed Assets, Office Equipment) |
| PRJ-0004 | CAPEX-NET-INFRA | Network Infrastructure Capital |
| PRJ-0005 | CAPEX-SOFTWARE | Capitalized Software |
| PRJ-0006 | OPEX-CLOUD | Cloud & Hosted Network Services (AWS, Lumen, Zayo, Verizon) |
| PRJ-0007 | OPEX-CONSULTING | Professional & Consulting Services (Deloitte, Accenture, KPMG) |
| PRJ-0008 | OPEX-DC-OPS | Data Center Operations (power, rent, DC professional services) |
| PRJ-0009 | OPEX-G-AND-A | G&A Operations (travel, office, training, occupancy) |
| PRJ-0010 | OPEX-LABOR | Labor & Employee Costs (overtime, pager pay, spot bonuses) |
| PRJ-0011 | OPEX-SAAS | SaaS & Software Subscriptions (Salesforce, Slack, Figma, Zoom) |
| PRJ-0012 | OPEX-TELECOM | Telecom & Communications (AT&T, Verizon, 8x8, RingCentral) |

---

## 5. Activity IDs (`/reference/activities`)

### 5.1 Purpose

Activity IDs are stable cross-month identifiers (e.g. `AOPEX-0000023`) that group logically related spend rows in the `spend` table. Each Activity ID record in the reference table enriches the raw identifier with department, account, and project context, making it available for filtering and reporting.

### 5.2 Table Columns

| Column | Description |
|---|---|
| Activity ID | Stable identifier from the spend table (`ACAPEX-NNNNNNN` or `AOPEX-NNNNNNN`) |
| Description | Auto-derived from account group + sub-group; editable |
| Department | Linked department (from the Departments reference table) |
| Cost Element | Cost element of the linked account (read-only, derived from account) |
| Account # | Linked account number (`ACC-XXXX`) |
| Project | Linked project (`PRJ-XXXX`) |

### 5.3 Filters

Three independent multi-select dropdowns filter the activity list:

| Filter | Options derived from |
|---|---|
| Department | Departments reference table |
| Cost Element | Cost element values present in the loaded activity list |
| Project | Project number + name pairs present in the loaded activity list |

**Clear all** appears when any filter is active.

### 5.4 Create

Click **Add Activity ID**. Only the Activity ID field is required; all other fields are optional. The department selection drives the Project dropdown — select a department first to see only projects linked to that department. The Cost Element filter narrows the Account Number dropdown to accounts of that cost element type.

### 5.5 Edit

Click **Edit**. The Activity ID is fixed and shown as read-only. All other fields can be changed.

### 5.6 Delete

Click **Delete** and confirm. Deleting a reference record does not affect the underlying spend rows — it only removes the enrichment record.

### 5.7 Activity → Project Auto-Assignment

When activity IDs are seeded or backfilled from spend data, a project is auto-assigned based on the following decision tree applied to each row's `expense_type`, `oracle_account_group`, and `oracle_account_sub_group`:

**CAPEX rows:**

| Sub-Group contains | Assigned project |
|---|---|
| `Network` | CAPEX-NET-INFRA |
| `Computer`, `Peripheral`, or `Personal Computer` | CAPEX-COMPUTE |
| `Software` | CAPEX-SOFTWARE |
| *(account group = Data Services)* | CAPEX-DC |
| *(all others)* | CAPEX-MISC |

**OPEX rows:**

| Account Group | Sub-Group | Assigned project |
|---|---|---|
| `Labor` or `Staff Related Expenses` | — | OPEX-LABOR |
| `Data Services` | `DC Power`, `DC Rent`, `DC Professional Services`, `DC Services` | OPEX-DC-OPS |
| `Data Services` | *(all others)* | OPEX-CLOUD |
| `Equipment & Software Expense` | — | OPEX-SAAS |
| `Contract & Professional Services` or `Temporary & Consulting` | — | OPEX-CONSULTING |
| `Telephone & Related` | — | OPEX-TELECOM |
| *(all others)* | — | OPEX-G-AND-A |

When an activity ID appears under multiple departments in spend, the most frequently occurring department is used.

### 5.8 Gap View

The SQL view `v_spend_activity_gaps` lists every distinct `activity_id` in the `spend` table that has no matching row in `activity_ids`. Query it to verify coverage:

```sql
SELECT * FROM v_spend_activity_gaps;
```

A zero-row result means all spend activity IDs are represented in the reference table. The backfill function `_backfill_spend_activities()` runs at every server startup and inserts any missing activity IDs automatically.

---

## 6. API Reference

Base URL: `http://localhost:8000` — Swagger UI: `http://localhost:8000/docs`

All endpoints require a valid JWT bearer token (`Authorization: Bearer <token>`).

### 6.1 Departments

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/departments` | Any | List all departments, ordered by code |
| `POST` | `/api/departments` | Write | Create a department |
| `PUT` | `/api/departments/{code}` | Write | Update department name |
| `DELETE` | `/api/departments/{code}` | Write | Delete (fails with 409 if referenced by an activity ID) |

**POST / PUT body**

| Field | Type | Required | Description |
|---|---|---|---|
| `department_code` | string | POST only | Oracle department code |
| `department_name` | string | Yes | Human-readable name |

### 6.2 Account Numbers

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/accounts` | Any | List accounts; supports `?cost_element=` filter |
| `POST` | `/api/accounts` | Write | Create account (display code auto-generated) |
| `PUT` | `/api/accounts/{id}` | Write | Update description, group, sub-group, or cost element |
| `DELETE` | `/api/accounts/{id}` | Write | Delete (fails with 409 if referenced by an activity ID) |

**GET query parameters**

| Parameter | Type | Description |
|---|---|---|
| `cost_element` | string | Filter by exact cost element value |

**POST body**

| Field | Type | Required | Description |
|---|---|---|---|
| `account_desc` | string | No | Free-text description |
| `account_group` | string | Yes | Account group |
| `account_sub_group` | string | No | Account sub-group |
| `cost_element` | string | Yes | Cost element |

**Response** includes `id` (integer PK) and `account_number` (e.g. `ACC-0042`).

### 6.3 Project IDs

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/projects` | Any | List projects; supports `?department_code=` filter |
| `POST` | `/api/projects` | Write | Create project (display code auto-generated) |
| `PUT` | `/api/projects/{id}` | Write | Update project name or department assignments |
| `DELETE` | `/api/projects/{id}` | Write | Delete (fails with 409 if referenced by an activity ID) |

**GET query parameters**

| Parameter | Type | Description |
|---|---|---|
| `department_code` | string | Return only projects linked to this department |

**POST body**

| Field | Type | Required | Description |
|---|---|---|---|
| `project_name` | string | Yes | Unique project name |
| `department_codes` | string[] | No | Department codes to link to this project |

**Response** includes `id`, `project_number` (e.g. `PRJ-0001`), `project_name`, and `departments` array.

### 6.4 Activity IDs

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/api/activities` | Any | List activity IDs; supports `?department_code=` filter |
| `POST` | `/api/activities` | Write | Create an activity ID record |
| `PUT` | `/api/activities/{activity_id}` | Write | Update description, department, account, or project |
| `DELETE` | `/api/activities/{activity_id}` | Write | Delete the reference record |

**GET query parameters**

| Parameter | Type | Description |
|---|---|---|
| `department_code` | string | Filter by department code |

**POST / PUT body**

| Field | Type | Required | Description |
|---|---|---|---|
| `activity_id` | string | POST only | The activity ID string (e.g. `AOPEX-0000023`) |
| `activity_id_desc` | string | No | Description |
| `department_code` | string | No | Linked department code |
| `account_id` | integer | No | Linked account (integer PK of `account_numbers`) |
| `project_id` | integer | No | Linked project (integer PK of `project_ids`) |

**Response** includes resolved fields: `department_name`, `account_number`, `cost_element`, `project_number`, `project_name`.

---

## 7. Data Model

### Relationships

```
departments ──< project_departments >── project_ids
                                              │
departments ──< activity_ids >─────────────────┘
account_numbers ──< activity_ids
```

### `departments` table

| Column | Type | Notes |
|---|---|---|
| `department_code` | VARCHAR(10) | Primary key |
| `department_name` | VARCHAR(255) | Not null |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | |

### `account_numbers` table

| Column | Type | Notes |
|---|---|---|
| `id` | INT | Primary key, auto-increment |
| `account_number` | VARCHAR(50) | Unique display code, e.g. `ACC-0042` |
| `account_desc` | VARCHAR(255) | Nullable |
| `account_group` | VARCHAR(100) | Not null |
| `account_sub_group` | VARCHAR(255) | Nullable |
| `cost_element` | VARCHAR(100) | Not null |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | |

### `project_ids` table

| Column | Type | Notes |
|---|---|---|
| `id` | INT | Primary key, auto-increment |
| `project_number` | VARCHAR(20) | Unique display code, e.g. `PRJ-0001` |
| `project_name` | VARCHAR(100) | Unique human-readable name |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | |

### `project_departments` table (join)

| Column | Type | Notes |
|---|---|---|
| `project_id` | INT | FK → `project_ids.id`, CASCADE DELETE |
| `department_code` | VARCHAR(10) | FK → `departments.department_code`, CASCADE DELETE |

### `activity_ids` table

| Column | Type | Notes |
|---|---|---|
| `activity_id` | VARCHAR(20) | Primary key (e.g. `AOPEX-0000023`) |
| `activity_id_desc` | VARCHAR(255) | Nullable |
| `department_code` | VARCHAR(10) | FK → `departments.department_code`, SET NULL on delete |
| `account_id` | INT | FK → `account_numbers.id`, SET NULL on delete |
| `project_id` | INT | FK → `project_ids.id`, SET NULL on delete |
| `created_at` | DATETIME | |
| `updated_at` | DATETIME | |

### Gap validation views

| View | Description |
|---|---|
| `v_spend_account_gaps` | `oracle_account_number` values in spend with no matching `account_numbers` row |
| `v_spend_department_gaps` | `oracle_department` codes in spend with no matching `departments` row |
| `v_spend_activity_gaps` | `activity_id` values in spend with no matching `activity_ids` row |
