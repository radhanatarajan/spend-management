from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, computed_field

from src.models.contract import ContractStatus, BillingInterval


# ── Fiscal-year helpers (calendar year: FY2027 = Jan 2027 → Dec 2027) ─────────

def month_to_fy(year: int, month: int) -> int:
    return year


def fiscal_year_months(fy: int) -> list[tuple[int, int]]:
    """Return the 12 (year, month) tuples for the given fiscal year."""
    return [(fy, m) for m in range(1, 13)]


def month_label(year: int, month: int) -> str:
    from datetime import date as _d
    return _d(year, month, 1).strftime("%b '%y")


def _months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def compute_monthly_amount(entered: Decimal, interval: BillingInterval, start: date, end: date) -> Decimal:
    if interval == BillingInterval.MONTHLY:
        return entered
    if interval == BillingInterval.QUARTERLY:
        return (entered / 3).quantize(Decimal("0.01"))
    if interval == BillingInterval.YEARLY:
        return (entered / 12).quantize(Decimal("0.01"))
    if interval == BillingInterval.CUSTOM:
        months = _months_between(start, end)
        return (entered / months).quantize(Decimal("0.01"))
    return entered


# ── ContractLine schemas ──────────────────────────────────────────────────────

class ContractLineCreate(BaseModel):
    po_line_number: int
    oracle_account_number: str
    oracle_account_sub_group: str
    activity_id: str | None = None
    period_start: date
    period_end: date
    billing_interval: BillingInterval = BillingInterval.MONTHLY
    entered_amount: Decimal
    notes: str | None = None


class ContractLineUpdate(BaseModel):
    po_line_number: int | None = None
    oracle_account_number: str | None = None
    oracle_account_sub_group: str | None = None
    activity_id: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    billing_interval: BillingInterval | None = None
    entered_amount: Decimal | None = None
    notes: str | None = None


class ContractLineOut(BaseModel):
    id: int
    contract_id: int
    po_line_number: int
    oracle_account_number: str
    oracle_account_sub_group: str
    activity_id: str | None
    period_start: date
    period_end: date
    billing_interval: BillingInterval
    entered_amount: Decimal
    monthly_amount: Decimal
    notes: str | None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def total_amount(self) -> Decimal:
        return (self.monthly_amount * _months_between(self.period_start, self.period_end)).quantize(Decimal("0.01"))

    @computed_field
    @property
    def months_in_period(self) -> int:
        return _months_between(self.period_start, self.period_end)

    model_config = {"from_attributes": True}


# ── Contract schemas ──────────────────────────────────────────────────────────

class ContractCreate(BaseModel):
    vendor_name: str
    description: str | None = None
    oracle_department: str
    oracle_department_name: str
    purchase_order_number: str
    status: ContractStatus = ContractStatus.ACTIVE
    lines: list[ContractLineCreate] = []


class ContractUpdate(BaseModel):
    vendor_name: str | None = None
    description: str | None = None
    oracle_department: str | None = None
    oracle_department_name: str | None = None
    purchase_order_number: str | None = None
    status: ContractStatus | None = None


class ContractOut(BaseModel):
    id: int
    vendor_name: str
    description: str | None
    oracle_department: str
    oracle_department_name: str
    purchase_order_number: str
    status: ContractStatus
    created_at: datetime
    updated_at: datetime
    lines: list[ContractLineOut] = []

    @computed_field
    @property
    def contract_total(self) -> Decimal:
        return sum((line.total_amount for line in self.lines), Decimal("0"))

    model_config = {"from_attributes": True}


# ── Contract Report schemas ───────────────────────────────────────────────────

class ContractReportRow(BaseModel):
    id: int
    vendor_name: str
    oracle_department_name: str
    oracle_account_number: str
    oracle_account_sub_group: str
    account_group: str
    account_sub_group: str
    cost_element: str
    purchase_order_number: str
    status: ContractStatus
    num_lines: int
    is_multi_year: bool
    # month_key → monthly_amount (None = contract not yet started or no coverage)
    monthly_amounts: dict[str, Decimal | None]
    # month_key → True when the amount is a 100% renewal assumption (not a signed PO line)
    monthly_assumed: dict[str, bool]
    fiscal_year_total: Decimal
    assumed_total: Decimal   # portion of fiscal_year_total that is assumed
    activity_id: str | None = None


class ContractReportOut(BaseModel):
    fiscal_year: int
    period_label: str           # "May 2026 – Apr 2027"
    month_keys: list[str]       # ["2026-05", …, "2027-04"]
    month_labels: list[str]     # ["May '26", …, "Apr '27"]
    rows: list[ContractReportRow]
    monthly_totals: dict[str, Decimal]
    grand_total: Decimal
    available_fiscal_years: list[int]
    filter_options: dict        # {"vendors": [...], "departments": [...], "statuses": [...]}


class ContractAuditReportRow(BaseModel):
    audit_id: str           # "c-{id}" or "l-{id}" — unique across both tables
    entity_type: str        # "Contract" or "Line"
    entity_id: int          # contract_id for Contract, contract_line_id for Line
    contract_id: int
    vendor_name: str
    purchase_order_number: str
    po_line_number: int | None
    event_type: str         # CREATED / UPDATED / DELETED
    changes: dict
    changed_by: str
    changed_at: datetime


class ContractAuditReportOut(BaseModel):
    rows: list[ContractAuditReportRow]
    filter_options: dict


class ContractAuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    vendor_name: str
    purchase_order_number: str
    event_type: str
    changes: dict
    changed_by: str
    changed_at: datetime


class ContractLineAuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_line_id: int
    contract_id: int
    vendor_name: str
    purchase_order_number: str
    po_line_number: int
    event_type: str
    changes: dict
    changed_by: str
    changed_at: datetime
