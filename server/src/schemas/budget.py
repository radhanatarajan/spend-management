from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class QuarterlyAmounts(BaseModel):
    q1: Decimal = Decimal("0")
    q2: Decimal = Decimal("0")
    q3: Decimal = Decimal("0")
    q4: Decimal = Decimal("0")
    annual: Decimal = Decimal("0")


class BudgetScenarioCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    fiscal_year: int
    budget_type: str
    copy_from_scenario_id: Optional[int] = None


class BudgetScenarioUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class BudgetScenarioOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    fiscal_year: int
    budget_type: str
    is_baseline: bool
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BudgetEntryStatusUpdate(BaseModel):
    status: str


class BudgetEntryAuditOut(BaseModel):
    id: int
    scenario_id: int
    entry_id: Optional[int]
    department_name: str
    entry_type: str
    event_type: str
    changes: dict
    changed_by: str
    changed_at: datetime

    model_config = {"from_attributes": True}


class BudgetScenarioAuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scenario_id: int
    fiscal_year: int
    scenario_name: str
    event_type: str
    changes: dict
    changed_by: str
    changed_at: datetime


class BudgetNcConfigAuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fiscal_year: int
    event_type: str
    changes: dict
    changed_by: str
    changed_at: datetime


class BudgetEntryUpsert(BaseModel):
    scenario_id: int
    department_name: str
    entry_type: str
    q1_amount: Optional[Decimal] = None
    q2_amount: Optional[Decimal] = None
    q3_amount: Optional[Decimal] = None
    q4_amount: Optional[Decimal] = None
    notes: Optional[str] = None


class BudgetEntryOut(BaseModel):
    id: int
    scenario_id: int
    department_name: str
    entry_type: str
    q1_amount: Optional[Decimal]
    q2_amount: Optional[Decimal]
    q3_amount: Optional[Decimal]
    q4_amount: Optional[Decimal]
    notes: Optional[str]
    status: str = "DRAFT"
    created_by: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class BudgetNcConfigOut(BaseModel):
    fiscal_year: int
    selected_cost_elements: list[str]
    selected_account_groups: list[str] = Field(default_factory=list)
    selected_account_sub_groups: list[str] = Field(default_factory=list)
    actuals_cutoff_month_key: Optional[int] = None
    updated_by: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class BudgetNcConfigUpdate(BaseModel):
    fiscal_year: int
    selected_cost_elements: list[str]
    selected_account_groups: list[str] = Field(default_factory=list)
    selected_account_sub_groups: list[str] = Field(default_factory=list)
    actuals_cutoff_month_key: Optional[int] = None


class DepartmentBudgetRow(BaseModel):
    department_name: str
    department_code: Optional[str] = None
    account_groups: list[str] = Field(default_factory=list)
    current: QuarterlyAmounts
    current_is_forecast: dict[str, bool] = Field(
        default_factory=dict,
        description="Keys are 'q1'/'q2'/'q3'/'q4'; True means that quarter is carry-forward forecast"
    )
    approved_rec: QuarterlyAmounts
    additional_ask: QuarterlyAmounts
    approved_rec_entry_id: Optional[int] = None
    approved_rec_status: str = "DRAFT"
    additional_ask_entry_id: Optional[int] = None
    additional_ask_status: str = "DRAFT"


class NonControllablePlanOut(BaseModel):
    fiscal_year: int
    scenario_id: int
    scenarios: list[BudgetScenarioOut]
    selected_cost_elements: list[str]
    available_cost_elements: list[str]
    departments: list[DepartmentBudgetRow]
    totals: DepartmentBudgetRow


# ── Budget Audit Report ───────────────────────────────────────────────────────

class BudgetAuditReportRow(BaseModel):
    audit_id: int
    entry_id: Optional[int]
    scenario_id: int
    scenario_name: str
    fiscal_year: int
    department_name: str
    entry_type: str
    event_type: str
    changed_by: str
    changed_at: datetime
    q1_old: Optional[Decimal] = None
    q1_new: Optional[Decimal] = None
    q2_old: Optional[Decimal] = None
    q2_new: Optional[Decimal] = None
    q3_old: Optional[Decimal] = None
    q3_new: Optional[Decimal] = None
    q4_old: Optional[Decimal] = None
    q4_new: Optional[Decimal] = None
    status_old: Optional[str] = None
    status_new: Optional[str] = None
    activity_id_old: Optional[str] = None
    activity_id_new: Optional[str] = None
    current_q1: Optional[Decimal] = None
    current_q2: Optional[Decimal] = None
    current_q3: Optional[Decimal] = None
    current_q4: Optional[Decimal] = None
    current_status: Optional[str] = None

    model_config = {"from_attributes": True}


class BudgetAuditFilterOptions(BaseModel):
    scenarios: list[str]
    departments: list[str]
    entry_types: list[str]
    event_types: list[str]
    users: list[str]


class BudgetAuditReportOut(BaseModel):
    fiscal_year: int
    rows: list[BudgetAuditReportRow]
    filter_options: BudgetAuditFilterOptions


# ── Scenario Comparison ───────────────────────────────────────────────────────

class ScenarioAmounts(BaseModel):
    q1: Decimal = Decimal("0")
    q2: Decimal = Decimal("0")
    q3: Decimal = Decimal("0")
    q4: Decimal = Decimal("0")
    annual: Decimal = Decimal("0")


class DeltaAmounts(BaseModel):
    q1: Decimal = Decimal("0")
    q2: Decimal = Decimal("0")
    q3: Decimal = Decimal("0")
    q4: Decimal = Decimal("0")
    annual: Decimal = Decimal("0")
    q1_pct: float = 0.0
    q2_pct: float = 0.0
    q3_pct: float = 0.0
    q4_pct: float = 0.0
    annual_pct: float = 0.0


class DeptCompareRow(BaseModel):
    department_name: str
    department_code: Optional[str] = None
    approved_rec_a: ScenarioAmounts
    approved_rec_b: ScenarioAmounts
    approved_rec_delta: DeltaAmounts
    additional_ask_a: ScenarioAmounts
    additional_ask_b: ScenarioAmounts
    additional_ask_delta: DeltaAmounts
    total_a: ScenarioAmounts
    total_b: ScenarioAmounts
    total_delta: DeltaAmounts


class ScenarioCompareOut(BaseModel):
    fiscal_year: int
    scenario_a: BudgetScenarioOut
    scenario_b: BudgetScenarioOut
    all_scenarios: list[BudgetScenarioOut]
    departments: list[DeptCompareRow]
    totals: DeptCompareRow


# ── Controllable Comparison ───────────────────────────────────────────────────

class CtrlActivityCompareRow(BaseModel):
    activity_id: Optional[str] = None
    entry_label: Optional[str] = None
    entry_category: str
    account_group: Optional[str] = None
    account_sub_group: Optional[str] = None
    expense_type: Optional[str] = None
    budget_a: ScenarioAmounts
    budget_b: ScenarioAmounts
    budget_delta: DeltaAmounts


class CtrlDeptCompareRow(BaseModel):
    department_name: str
    rows: list[CtrlActivityCompareRow]
    total_a: ScenarioAmounts
    total_b: ScenarioAmounts
    total_delta: DeltaAmounts


class CtrlCompareOut(BaseModel):
    fiscal_year: int
    scenario_a: BudgetScenarioOut
    scenario_b: BudgetScenarioOut
    departments: list[CtrlDeptCompareRow]
    totals_a: ScenarioAmounts
    totals_b: ScenarioAmounts
    totals_delta: DeltaAmounts


# ── Controllable Budget ───────────────────────────────────────────────────────

class ControllableEntryUpsert(BaseModel):
    entry_id: Optional[int] = None
    scenario_id: int
    fiscal_year: int
    activity_id: Optional[str] = None
    entry_label: Optional[str] = None
    entry_category: str = "EXISTING"
    department_name: Optional[str] = None
    account_group: Optional[str] = None
    account_sub_group: Optional[str] = None
    cost_element: Optional[str] = None
    expense_type: Optional[str] = None
    q1_amount: Optional[Decimal] = None
    q2_amount: Optional[Decimal] = None
    q3_amount: Optional[Decimal] = None
    q4_amount: Optional[Decimal] = None
    notes: Optional[str] = None


class ControllableEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scenario_id: int
    fiscal_year: int
    activity_id: Optional[str]
    entry_label: Optional[str]
    entry_category: str
    department_name: Optional[str]
    account_group: Optional[str]
    account_sub_group: Optional[str]
    cost_element: Optional[str]
    expense_type: Optional[str]
    q1_amount: Optional[Decimal]
    q2_amount: Optional[Decimal]
    q3_amount: Optional[Decimal]
    q4_amount: Optional[Decimal]
    notes: Optional[str]
    status: str
    created_by: str
    updated_at: datetime


class ControllableEntryStatusUpdate(BaseModel):
    status: str


class ControllableLineOverrideUpsert(BaseModel):
    scenario_id: int
    contract_line_id: int
    action: str
    q1_extended: Optional[Decimal] = None
    q2_extended: Optional[Decimal] = None
    q3_extended: Optional[Decimal] = None
    q4_extended: Optional[Decimal] = None


class ControllableLineOverrideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scenario_id: int
    contract_line_id: int
    action: str
    q1_extended: Optional[Decimal]
    q2_extended: Optional[Decimal]
    q3_extended: Optional[Decimal]
    q4_extended: Optional[Decimal]


class ControllableLineDetail(BaseModel):
    contract_line_id: int
    contract_id: int
    vendor_name: str
    po_number: str
    po_line_number: int
    period_start: str
    period_end: str
    monthly_amount: Decimal
    fy_months_count: int
    fy_contribution: Decimal
    q1_contribution: Decimal
    q2_contribution: Decimal
    q3_contribution: Decimal
    q4_contribution: Decimal
    override_action: str
    q1_extended: Optional[Decimal]
    q2_extended: Optional[Decimal]
    q3_extended: Optional[Decimal]
    q4_extended: Optional[Decimal]


class ControllablePlanRow(BaseModel):
    activity_id: Optional[str]
    entry_label: Optional[str]
    entry_category: str
    department_name: Optional[str]
    account_group: Optional[str]
    account_sub_group: Optional[str]
    cost_element: Optional[str]
    expense_type: Optional[str] = None
    # Quarterly contracted amounts (from contracts, read-only)
    q1_contracted: Decimal
    q2_contracted: Decimal
    q3_contracted: Decimal
    q4_contracted: Decimal
    current_and_forecast: Decimal  # annual total = sum of quarterly contracted
    # User-entered budget amounts
    q1_amount: Optional[Decimal]
    q2_amount: Optional[Decimal]
    q3_amount: Optional[Decimal]
    q4_amount: Optional[Decimal]
    total_budget: Decimal
    entry_id: Optional[int]
    status: Optional[str]
    lines: list[ControllableLineDetail]


class ControllablePlanOut(BaseModel):
    fiscal_year: int
    scenario_id: int
    actuals_cutoff_month_key: Optional[int]
    rows: list[ControllablePlanRow]
