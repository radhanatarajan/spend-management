from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class SpendRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    month_key: int
    month_label: str
    expense_type: str
    company_code: str
    oracle_organization: str
    oracle_account_number: str
    oracle_department: str
    oracle_department_name: str
    oracle_cost_center_hierarchy: str
    oracle_account_group: str
    oracle_account_sub_group: str
    oracle_cost_element: str
    line_desc: Optional[str] = None
    vendor_name: str
    po_recon: Optional[str] = None
    po_description: Optional[str] = None
    purchase_order_number: Optional[str] = None
    purchase_order_line_number: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_line_number: Optional[str] = None
    je_source: Optional[str] = None
    amount_usd: Decimal
    created_at: datetime
    updated_at: datetime


class PaginatedSpend(BaseModel):
    items: List[SpendRead]
    total: int
    page: int
    page_size: int
    total_pages: int


class MonthOption(BaseModel):
    month_key: int
    month_label: str


class OracleDeptOption(BaseModel):
    oracle_department: str
    oracle_department_name: str


class SpendFilterOptions(BaseModel):
    months: List[MonthOption]
    expense_types: List[str]
    company_codes: List[str]
    oracle_departments: List[OracleDeptOption]
    oracle_account_groups: List[str]
    vendors: List[str]
    je_sources: List[str]


class AmountByLabel(BaseModel):
    label: str
    amount: Decimal
    pct: float


class MonthTrend(BaseModel):
    month_key: int
    month_label: str
    amount: Decimal


class SpendSummary(BaseModel):
    total_amount: Decimal
    total_transactions: int
    by_account_group: List[AmountByLabel]
    by_vendor: List[AmountByLabel]
    by_department: List[AmountByLabel]
    by_month: List[MonthTrend]
