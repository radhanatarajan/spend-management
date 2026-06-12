# Functional Architecture

**Spend Management Platform — as-built**

---

## 1. System Overview

Three-tier web application: React frontend, FastAPI backend, MySQL database. Auth is JWT-based with four roles (Admin, BizAdmin, ServiceOwner, ReadOnly).

```mermaid
flowchart TD
    User(["User\n(Browser)"])

    subgraph Frontend["Frontend — React 19 · Vite · Tailwind CSS · TanStack Query v5\nlocalhost:5173"]
        direction LR
        F1["Spend Analytics\n/spend"]
        F2["Contract Database\n/contracts"]
        F3["Budget Planning\n/budget-planning"]
        F4["Reports\n/reports/*"]
        F5["Reference Data\n/reference/*"]
    end

    subgraph API["Backend — FastAPI · SQLAlchemy 2.0 · Pydantic v2\nlocalhost:8000"]
        direction LR
        A_Auth["/api/auth"]
        A_Spend["/api/spend"]
        A_Contracts["/api/contracts"]
        A_Budget["/api/budget"]
        A_Ref["/api/{departments\naccounts · projects\nactivities}"]
    end

    subgraph DB["MySQL 8 · localhost:3306 · schema: spend_management"]
        direction LR
        DB_Trans[("Transactional\ntables")]
        DB_Ref[("Reference\ntables")]
        DB_Audit[("Audit\ntables & views")]
    end

    User -- "HTTPS + JWT Bearer" --> Frontend
    Frontend -- "REST/JSON" --> API
    API -- "SQLAlchemy ORM\n+ raw SQL" --> DB
```

---

## 2. Module Map

Each frontend module, the API domain it calls, and the database tables it reads or writes.

```mermaid
flowchart LR
    subgraph Pages["Frontend Pages"]
        P1["Spend Analytics"]
        P2["Contract Database"]
        P3a["NC Budget Planning"]
        P3b["CTRL Budget Planning"]
        P3c["NC Scenario Comparison"]
        P3d["CTRL Scenario Comparison"]
        P4a["Spend Report"]
        P4b["Contract Report"]
        P4c["Contract Change Log"]
        P4d["Budget Change Log"]
        P4e["Budget Report"]
        P5["Reference Data"]
    end

    subgraph APIs["API Routers"]
        A1["/api/spend"]
        A2["/api/contracts"]
        A3["/api/budget"]
        A4["/api/{ref}"]
    end

    subgraph Tables["Database Tables / Views"]
        T_Spend[("spend")]
        T_Con[("contracts\ncontract_lines")]
        T_BNC[("budget_scenarios\nbudget_entries\nbudget_nc_config")]
        T_BCT[("controllable_budget_entries\ncontrollable_line_overrides")]
        T_Ref[("departments\naccount_numbers\nproject_ids\nactivity_ids")]
        T_Aud[("*_audit tables\n*_audit views")]
    end

    P1 --> A1
    P2 --> A2
    P3a --> A3
    P3b --> A3
    P3c --> A3
    P3d --> A3
    P4a --> A1
    P4b --> A2
    P4c --> A2
    P4d --> A3
    P4e --> A3
    P5 --> A4

    A1 --> T_Spend
    A1 --> T_Ref
    A2 --> T_Con
    A2 --> T_Ref
    A2 --> T_Aud
    A3 --> T_BNC
    A3 --> T_BCT
    A3 --> T_Spend
    A3 --> T_Con
    A3 --> T_Ref
    A3 --> T_Aud
    A4 --> T_Ref
    A4 --> T_Aud
```

---

## 3. Cross-Module Data Flows

The platform's key insight is that **reference data and spend history flow into planning and reporting**. The arrows below show where data from one domain is consumed by another.

```mermaid
flowchart TD
    subgraph Ingestion["Spend Ingestion (source of truth)"]
        SP[("spend\noracle actuals")]
    end

    subgraph Contracts["Contract Database"]
        CON[("contracts\ncontract_lines\nactivity_id linkage")]
    end

    subgraph Ref["Reference Data (master data)"]
        DEP[("departments\ndept_code → dept_name")]
        ACT[("activity_ids\nNC-* · AOPEX-* · ACAPEX-*")]
        ACC[("account_numbers\ncost_element · account_group\nsub_group · account_number")]
        PRJ[("project_ids")]
    end

    subgraph Budget["Budget Planning"]
        NCFG["NC Config\ncost elements · account groups\nactuals cutoff"]
        NCPL["NC Budget Entries\nper department · per entry_type\nexpense_type=Opex\nactivity_id=NC-{dept}-ACC-0301"]
        CTPL["CTRL Budget Entries\nper activity_id\nEXISTING or NEW_REQUEST"]
        OVR["Line Overrides\nkeep · cancel · extend"]
    end

    subgraph Reports["Reporting"]
        BR["Budget Report\nNC + CTRL combined\ndynamic group-by"]
        BA["Budget Change Log\nNC + CTRL audit events"]
        CA["Contract Change Log\ncontract audit events"]
        SR["Spend Report\nfiltered actuals"]
        CR["Contract Report\nGL-enriched breakout"]
    end

    SP -- "prior-year actuals\ncarry-forward baseline" --> NCPL
    SP -- "filter config drives\nwhat spend rows appear" --> NCFG
    CON -- "active contracts\nauto-seed scenario" --> CTPL
    CON -- "quarterly amounts\nper line" --> OVR

    DEP -- "dept_code lookup\nNC-{code}-ACC-0301" --> NCPL
    ACT -- "enriches\nspend rows" --> SP
    ACT -- "links contracts\nto budget" --> CON
    ACT -- "enriches CTRL\nreport rows" --> BR
    ACC -- "GL enrichment\ncost_element · account_group" --> CR
    ACC -- "enriches NC\nreport rows via activity_id" --> BR

    NCPL --> BR
    CTPL --> BR
    NCPL --> BA
    CTPL --> BA
    CON --> CA
    SP --> SR
    CON --> CR
    ACC --> CR
```

---

## 4. Database Domain Map

Tables and views organized by domain, with primary relationships shown.

```mermaid
erDiagram
    %% Spend domain
    spend {
        int id PK
        string oracle_department
        string oracle_account_number
        string oracle_cost_element
        string activity_id FK
        int month_key
        decimal amount
    }

    %% Contract domain
    contracts {
        int id PK
        string vendor_name
        string department FK
        string activity_id FK
        string status
    }
    contract_lines {
        int id PK
        int contract_id FK
        date start_month
        date end_month
        decimal monthly_amount
        string billing_interval
        string activity_id FK
    }
    contracts ||--o{ contract_lines : "has lines"

    %% Budget — NC
    budget_scenarios {
        int id PK
        string name
        int fiscal_year
        string budget_type
        bool is_baseline
    }
    budget_entries {
        int id PK
        int scenario_id FK
        string department_name
        string entry_type
        string expense_type
        string activity_id FK
        string status
        decimal q1_amount
        decimal q2_amount
        decimal q3_amount
        decimal q4_amount
    }
    budget_scenarios ||--o{ budget_entries : "NC entries"

    %% Budget — CTRL
    controllable_budget_entries {
        int id PK
        int scenario_id FK
        string activity_id FK
        string entry_category
        string expense_type
        string status
        decimal q1_amount
        decimal q4_amount
    }
    controllable_line_overrides {
        int id PK
        int scenario_id FK
        int contract_line_id FK
        string action
        decimal q1_extended
        decimal q4_extended
    }
    budget_scenarios ||--o{ controllable_budget_entries : "CTRL entries"
    budget_scenarios ||--o{ controllable_line_overrides : "overrides"
    contract_lines ||--o{ controllable_line_overrides : "overridden by"

    %% Reference
    departments {
        int id PK
        string department_code
        string department_name
    }
    account_numbers {
        int id PK
        string account_number
        string cost_element
        string account_group
        string account_sub_group
    }
    activity_ids {
        int id PK
        string activity_id
        string department_code FK
        int account_id FK
    }
    project_ids {
        int id PK
        string project_id
    }

    activity_ids }o--|| account_numbers : "account_id"
    activity_ids }o--|| departments : "department_code"
```

---

## 5. Audit Architecture

Two audit patterns are used depending on data velocity.

```mermaid
flowchart LR
    subgraph PatternA["Pattern A — Shared reference_audit table\n(slow-changing master data)"]
        direction TB
        RA_T[("reference_audit\ntable_name · record_id\nevent_type · changes JSON\nchanged_by · changed_at")]
        RA_V1["v_reference_audit_departments"]
        RA_V2["v_reference_audit_accounts"]
        RA_V3["v_reference_audit_activities"]
        RA_V4["v_reference_audit_projects"]
        RA_T --> RA_V1 & RA_V2 & RA_V3 & RA_V4
    end

    subgraph PatternB["Pattern B — Domain-specific audit tables\n(high-velocity transactional data)"]
        direction TB
        B1[("contract_audit\ncontract_lines_audit")]
        B2[("budget_entry_audit\nbudget_scenario_audit\nbudget_nc_config_audit")]
        B3[("controllable_budget_audit")]
        BV1["v_contract_audit\nv_contract_lines_audit"]
        BV2["v_budget_entry_audit\nv_budget_scenario_audit\nv_budget_nc_config_audit"]
        BV3["v_controllable_budget_audit"]
        B1 --> BV1
        B2 --> BV2
        B3 --> BV3
    end

    subgraph Consumers["Report Consumers"]
        RC1["Contract Change Log\n/reports/contract-audit"]
        RC2["Budget Change Log\n/reports/budget-audit"]
        RC3["Scenario Audit Panel\n(inline in Budget Planning)"]
    end

    BV1 --> RC1
    BV2 & BV3 --> RC2
    BV2 --> RC3
```

---

## 6. Role-Based Access Control

```mermaid
flowchart LR
    subgraph Roles
        RO["Read Only"]
        SO["Service Owner"]
        BA["Biz Admin"]
        AD["Admin"]
    end

    subgraph Guards["FastAPI Dependencies"]
        G1["require_any\n(any authenticated user)"]
        G2["require_write\n(SO · BizAdmin · Admin)"]
        G3["require_biz_admin\n(BizAdmin · Admin)"]
    end

    subgraph Endpoints["What each guard protects"]
        E1["All GET endpoints\nReports · Planning views\nReference data reads"]
        E2["PUT/DELETE entry amounts\nStatus transitions\nLine overrides"]
        E3["Create/update scenarios\nUpdate NC config\nDelete scenarios"]
        E4["Unlock FINAL entries\nRestore CANCELLED → DRAFT\n(Admin only, no guard — inline check)"]
    end

    RO & SO & BA & AD --> G1 --> E1
    SO & BA & AD --> G2 --> E2
    BA & AD --> G3 --> E3
    AD --> E4
```

---

## 7. Budget Planning Scenario Model

```mermaid
flowchart TD
    subgraph NC["Non-Controllable (per FY)"]
        NC_S1["Scenario: NC Baseline\nis_baseline = true"]
        NC_S2["Scenario: NC What-If\nis_baseline = false"]
        NC_E["budget_entries\n(scenario, dept, entry_type)\nAPPROVED_REC · ADDITIONAL_ASK"]
        NC_CFG["budget_nc_config\nselected_cost_elements\nselected_account_groups\nactuals_cutoff_month_key"]
        NC_S1 & NC_S2 --> NC_E
        NC_CFG -. "filters actuals\nbaseline view" .-> NC_E
    end

    subgraph CTRL["Controllable (per FY)"]
        CT_S1["Scenario: C Baseline\nis_baseline = true"]
        CT_S2["Scenario: C Conservative\nis_baseline = false"]
        CT_E_EX["controllable_budget_entries\nEXISTING (seeded from contracts)"]
        CT_E_NR["controllable_budget_entries\nNEW_REQUEST (manual)"]
        CT_OVR["controllable_line_overrides\nkeep · cancel · extend"]
        CT_S1 & CT_S2 --> CT_E_EX & CT_E_NR
        CT_S1 & CT_S2 --> CT_OVR
    end

    subgraph Compare["Scenario Comparison"]
        CMP_NC["NC Compare\nA vs B delta by dept"]
        CMP_CT["CTRL Compare\nA vs B delta by activity"]
    end

    subgraph BReport["Budget Report"]
        BR["Combined NC + CTRL\ndynamic group-by dimensions\n(Department · Entry Type\nExpense Type · Cost Element\nAccount Group · Sub Group\nAccount Number · Activity ID)"]
    end

    NC_S1 --> CMP_NC
    NC_S2 --> CMP_NC
    CT_S1 --> CMP_CT
    CT_S2 --> CMP_CT

    NC_S1 --> BR
    CT_S1 --> BR
```

---

## 8. Activity ID Lineage

Activity IDs are the join key that links spend history, contracts, and budget planning into a unified view.

```mermaid
flowchart LR
    subgraph Generation["ID Generation"]
        G_NC["NC rule (startup)\nNC-{dept_code}-{account_number}\ne.g. NC-1100-ACC-0301"]
        G_CT["CTRL (manual / API)\nAOPEX-NNNNNNN (Opex)\nACAPEX-NNNNNNN (Capex)"]
    end

    subgraph Registry["activity_ids table\n(reference)"]
        REG[("activity_id\ndepartment_code\naccount_id → account_numbers")]
    end

    subgraph Consumers["Assigned to / used by"]
        S["spend rows\noracle_cost_element =\n'Employee Related'"]
        CL["contract_lines\nlinking vendor spend\nto GL"]
        BE["budget_entries\nNC entries\n(expense_type=Opex)"]
        CBE["controllable_budget_entries\nCTRL entries"]
    end

    subgraph Reports["Enriches Reports"]
        BR["Budget Report\ngroup-by Activity ID"]
        SR["Spend Analytics\nActivity ID filter"]
        CR["Contract Report\nActivity ID column"]
    end

    G_NC --> REG
    G_CT --> REG
    REG --> S & CL & BE & CBE
    S --> SR
    CL --> CR
    BE & CBE --> BR
```

---

## 9. Implemented Features Summary

| Module | Status | Pages | API Domain | Key Tables |
|---|---|---|---|---|
| Spend Analytics | ✅ Done | `/spend` | `/api/spend` | `spend` |
| Contract Database | ✅ Done | `/contracts` | `/api/contracts` | `contracts`, `contract_lines` |
| Contract Report | ✅ Done | `/reports/contracts` | `/api/contracts` | `v_contracts_enriched` |
| Contract Change Log | ✅ Done | `/reports/contract-audit` | `/api/contracts` | `v_contract_audit`, `v_contract_lines_audit` |
| NC Budget Planning | ✅ Done | `/budget-planning` (NC tab) | `/api/budget` | `budget_scenarios`, `budget_entries`, `budget_nc_config` |
| NC Scenario Comparison | ✅ Done | `/budget-planning` (NC Compare tab) | `/api/budget` | `budget_scenarios`, `budget_entries` |
| CTRL Budget Planning | ✅ Done | `/budget-planning` (CTRL tab) | `/api/budget` | `controllable_budget_entries`, `controllable_line_overrides` |
| CTRL Scenario Comparison | ✅ Done | `/budget-planning` (CTRL Compare tab) | `/api/budget` | `controllable_budget_entries` |
| Budget Report | ✅ Done | `/reports/budget` | `/api/budget` | `budget_entries`, `controllable_budget_entries`, `activity_ids`, `account_numbers` |
| Budget Change Log | ✅ Done | `/reports/budget-audit` | `/api/budget` | `v_budget_entry_audit`, `v_controllable_budget_audit` |
| Spend Report | ✅ Done | `/reports/spend` | `/api/spend` | `spend`, `account_numbers` |
| Reference Data | ✅ Done | `/reference/*` | `/api/{domains}` | `departments`, `account_numbers`, `project_ids`, `activity_ids` |
| Forecasting | 🔜 Planned | `/forecasting` | — | — |
| Forecast Report | 🔜 Planned | `/reports/forecast` | — | — |
| Budget Report (tabular) | 🔜 Planned | `/reports/budget` | — | — |
