from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, distinct
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.models.spend import Spend
from src.schemas.spend import (
    PaginatedSpend,
    SpendRead,
    SpendFilterOptions,
    MonthOption,
    OracleDeptOption,
)

router = APIRouter(prefix="/api/spend", tags=["spend"])

_SORTABLE = {
    "month_key", "expense_type", "company_code", "oracle_organization",
    "oracle_account_number", "oracle_department", "oracle_department_name",
    "oracle_cost_center_hierarchy", "oracle_account_group", "oracle_account_sub_group",
    "oracle_cost_element", "vendor_name", "po_recon", "je_source", "amount_usd",
}


def _where_clauses(*, month_keys, expense_types, company_codes,
                   oracle_departments, oracle_account_groups, vendors, je_sources,
                   exclude=()):
    """Return a list of WHERE conditions, skipping fields listed in exclude."""
    clauses = []
    if month_keys and "month_keys" not in exclude:
        clauses.append(Spend.month_key.in_(month_keys))
    if expense_types and "expense_types" not in exclude:
        clauses.append(Spend.expense_type.in_(expense_types))
    if company_codes and "company_codes" not in exclude:
        clauses.append(Spend.company_code.in_(company_codes))
    if oracle_departments and "oracle_departments" not in exclude:
        clauses.append(Spend.oracle_department.in_(oracle_departments))
    if oracle_account_groups and "oracle_account_groups" not in exclude:
        clauses.append(Spend.oracle_account_group.in_(oracle_account_groups))
    if vendors and "vendors" not in exclude:
        clauses.append(Spend.vendor_name.in_(vendors))
    if je_sources and "je_sources" not in exclude:
        clauses.append(Spend.je_source.in_(je_sources))
    return clauses


@router.get("/transactions", response_model=PaginatedSpend)
def list_spend(
    month_keys: Optional[List[int]] = Query(None),
    expense_types: Optional[List[str]] = Query(None),
    company_codes: Optional[List[str]] = Query(None),
    oracle_departments: Optional[List[str]] = Query(None),
    oracle_account_groups: Optional[List[str]] = Query(None),
    vendors: Optional[List[str]] = Query(None),
    je_sources: Optional[List[str]] = Query(None),
    sort_by: str = Query("month_key"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    if sort_by not in _SORTABLE:
        sort_by = "month_key"

    fk = dict(
        month_keys=month_keys, expense_types=expense_types, company_codes=company_codes,
        oracle_departments=oracle_departments, oracle_account_groups=oracle_account_groups,
        vendors=vendors, je_sources=je_sources,
    )
    clauses = _where_clauses(**fk)

    total = db.execute(
        select(func.count(Spend.id)).where(*clauses)
    ).scalar_one()

    sort_col = getattr(Spend, sort_by)
    data_stmt = (
        select(Spend)
        .where(*clauses)
        .order_by(sort_col.asc() if sort_order == "asc" else sort_col.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = db.execute(data_stmt).scalars().all()

    return PaginatedSpend(
        items=[SpendRead.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, (total + page_size - 1) // page_size),
    )


@router.get("/filter-options", response_model=SpendFilterOptions)
def get_filter_options(
    month_keys: Optional[List[int]] = Query(None),
    expense_types: Optional[List[str]] = Query(None),
    company_codes: Optional[List[str]] = Query(None),
    oracle_departments: Optional[List[str]] = Query(None),
    oracle_account_groups: Optional[List[str]] = Query(None),
    vendors: Optional[List[str]] = Query(None),
    je_sources: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Return distinct values for each slicer, cross-filtered by all OTHER active slicers.
    Selecting 'Engineering' dept narrows the vendor list to vendors with Engineering spend,
    but the dept slicer itself still shows all dept values.
    """
    fk = dict(
        month_keys=month_keys, expense_types=expense_types, company_codes=company_codes,
        oracle_departments=oracle_departments, oracle_account_groups=oracle_account_groups,
        vendors=vendors, je_sources=je_sources,
    )

    def clauses(exclude):
        return _where_clauses(**fk, exclude=(exclude,))

    months_raw = db.execute(
        select(Spend.month_key, Spend.month_label).distinct()
        .where(*clauses("month_keys"))
        .order_by(Spend.month_key.desc())
    ).all()

    expense_type_vals = db.execute(
        select(distinct(Spend.expense_type))
        .where(*clauses("expense_types"))
        .order_by(Spend.expense_type)
    ).scalars().all()

    company_code_vals = db.execute(
        select(distinct(Spend.company_code))
        .where(*clauses("company_codes"))
        .order_by(Spend.company_code)
    ).scalars().all()

    depts_raw = db.execute(
        select(Spend.oracle_department, Spend.oracle_department_name).distinct()
        .where(*clauses("oracle_departments"))
        .order_by(Spend.oracle_department)
    ).all()

    group_vals = db.execute(
        select(distinct(Spend.oracle_account_group))
        .where(*clauses("oracle_account_groups"))
        .order_by(Spend.oracle_account_group)
    ).scalars().all()

    vendor_vals = db.execute(
        select(distinct(Spend.vendor_name))
        .where(*clauses("vendors"))
        .order_by(Spend.vendor_name)
    ).scalars().all()

    je_vals = db.execute(
        select(distinct(Spend.je_source))
        .where(Spend.je_source.is_not(None), *clauses("je_sources"))
        .order_by(Spend.je_source)
    ).scalars().all()

    return SpendFilterOptions(
        months=[MonthOption(month_key=r[0], month_label=r[1]) for r in months_raw],
        expense_types=list(expense_type_vals),
        company_codes=list(company_code_vals),
        oracle_departments=[
            OracleDeptOption(oracle_department=r[0], oracle_department_name=r[1])
            for r in depts_raw
        ],
        oracle_account_groups=list(group_vals),
        vendors=list(vendor_vals),
        je_sources=list(je_vals),
    )
