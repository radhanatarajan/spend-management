from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from src.core.dependencies import get_db
from src.models.contract import Contract, ContractLine, BillingInterval
from src.schemas.contract import (
    ContractCreate, ContractUpdate, ContractOut,
    ContractLineCreate, ContractLineUpdate, ContractLineOut,
    ContractReportOut, ContractReportRow,
    compute_monthly_amount,
    month_to_fy, fiscal_year_months, month_label,
)

router = APIRouter(prefix="/api/contracts", tags=["contracts"])


def _get_contract_or_404(contract_id: int, db: Session) -> Contract:
    contract = db.execute(
        select(Contract)
        .options(selectinload(Contract.lines))
        .where(Contract.id == contract_id)
    ).scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract


def _resolve_monthly(line: ContractLine) -> None:
    """Recompute and store monthly_amount from entered_amount + billing_interval + dates."""
    line.monthly_amount = compute_monthly_amount(
        line.entered_amount, line.billing_interval, line.period_start, line.period_end
    )


def _is_multi_year(contract: Contract) -> bool:
    """
    True when all PO lines share the same vendor/dept/account/PO (enforced by the
    Contract header) AND form a consecutive chain: each line starts the month
    immediately after the previous line ends.
    """
    lines = sorted(contract.lines, key=lambda l: l.period_start)
    if len(lines) < 2:
        return False
    for a, b in zip(lines, lines[1:]):
        # Advance end-month by one
        next_year  = a.period_end.year + (1 if a.period_end.month == 12 else 0)
        next_month = 1 if a.period_end.month == 12 else a.period_end.month + 1
        if b.period_start.year != next_year or b.period_start.month != next_month:
            return False
    return True


# ── Contract Report ───────────────────────────────────────────────────────────

@router.get("/report", response_model=ContractReportOut)
def get_contract_report(
    fiscal_year: int = Query(..., description="Fiscal year end (FY2027 = May-2026 → Apr-2027)"),
    db: Session = Depends(get_db),
):
    all_contracts = db.execute(
        select(Contract).options(selectinload(Contract.lines)).order_by(Contract.vendor_name)
    ).scalars().all()

    # Multi-year = consecutive PO lines (same vendor/dept/account/PO enforced by header)
    multi_year = [c for c in all_contracts if _is_multi_year(c)]

    # Build fiscal-year month list
    fy_months = fiscal_year_months(fiscal_year)  # [(year, month), ...]
    mk_str = [f"{y:04d}-{m:02d}" for y, m in fy_months]
    mk_labels = [month_label(y, m) for y, m in fy_months]

    # Available fiscal years across all multi-year contract lines
    fy_set: set[int] = set()
    for c in multi_year:
        for line in c.lines:
            s_fy = month_to_fy(line.period_start.year, line.period_start.month)
            e_fy = month_to_fy(line.period_end.year, line.period_end.month)
            for fy in range(s_fy, e_fy + 1):
                fy_set.add(fy)
    available_fys = sorted(fy_set)

    # Build report rows
    rows: list[ContractReportRow] = []
    for contract in multi_year:
        # Sort lines chronologically so "last line" is well-defined
        sorted_lines = sorted(contract.lines, key=lambda l: l.period_start)
        last_line = sorted_lines[-1]
        last_line_end_int = last_line.period_end.year * 100 + last_line.period_end.month
        first_line_start_int = sorted_lines[0].period_start.year * 100 + sorted_lines[0].period_start.month

        monthly_amounts: dict[str, Decimal | None] = {}
        monthly_assumed: dict[str, bool] = {}

        for (y, m), key in zip(fy_months, mk_str):
            mk_int = y * 100 + m

            # Month is before the contract ever started — no data, no assumption
            if mk_int < first_line_start_int:
                monthly_amounts[key] = None
                monthly_assumed[key] = False
                continue

            # Find a PO line that covers this month
            amount = None
            for line in sorted_lines:
                s_int = line.period_start.year * 100 + line.period_start.month
                e_int = line.period_end.year * 100 + line.period_end.month
                if s_int <= mk_int <= e_int:
                    amount = line.monthly_amount
                    break

            if amount is not None:
                monthly_amounts[key] = amount
                monthly_assumed[key] = False
            elif mk_int > last_line_end_int:
                # Beyond last signed PO line → 100% renewal assumption at last line's rate
                monthly_amounts[key] = last_line.monthly_amount
                monthly_assumed[key] = True
            else:
                # Gap between lines (shouldn't happen in clean data, but handle gracefully)
                monthly_amounts[key] = None
                monthly_assumed[key] = False

        fy_total = sum(v for v in monthly_amounts.values() if v is not None)
        assumed_total = sum(
            v for k, v in monthly_amounts.items()
            if v is not None and monthly_assumed.get(k)
        )

        # Only include contracts that have any coverage (actual or assumed) in this FY
        if fy_total == 0:
            continue

        rows.append(ContractReportRow(
            id=contract.id,
            vendor_name=contract.vendor_name,
            oracle_department_name=contract.oracle_department_name,
            oracle_account_number=contract.oracle_account_number,
            oracle_account_sub_group=contract.oracle_account_sub_group,
            purchase_order_number=contract.purchase_order_number,
            status=contract.status,
            num_lines=len(contract.lines),
            monthly_amounts=monthly_amounts,
            monthly_assumed=monthly_assumed,
            fiscal_year_total=Decimal(str(fy_total)),
            assumed_total=Decimal(str(assumed_total)),
        ))

    # Monthly totals across all rows
    monthly_totals: dict[str, Decimal] = {}
    for key in mk_str:
        monthly_totals[key] = sum(
            (r.monthly_amounts[key] for r in rows if r.monthly_amounts.get(key) is not None),
            Decimal("0"),
        )

    grand_total = sum(r.fiscal_year_total for r in rows)

    # Filter options from the rows that appear in this FY
    period_label = f"{mk_labels[0]} – {mk_labels[-1]}"

    return ContractReportOut(
        fiscal_year=fiscal_year,
        period_label=period_label,
        month_keys=mk_str,
        month_labels=mk_labels,
        rows=rows,
        monthly_totals=monthly_totals,
        grand_total=grand_total,
        available_fiscal_years=available_fys,
        filter_options={
            "vendors": sorted({r.vendor_name for r in rows}),
            "departments": sorted({r.oracle_department_name for r in rows}),
            "statuses": sorted({r.status.value for r in rows}),
        },
    )


# ── Contract CRUD ─────────────────────────────────────────────────────────────

@router.get("", response_model=list[ContractOut])
def list_contracts(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Contract).options(selectinload(Contract.lines)).order_by(Contract.vendor_name)
    ).scalars().all()
    return rows


@router.post("", response_model=ContractOut, status_code=status.HTTP_201_CREATED)
def create_contract(body: ContractCreate, db: Session = Depends(get_db)):
    contract = Contract(
        vendor_name=body.vendor_name,
        description=body.description,
        oracle_department=body.oracle_department,
        oracle_department_name=body.oracle_department_name,
        oracle_account_number=body.oracle_account_number,
        oracle_account_sub_group=body.oracle_account_sub_group,
        purchase_order_number=body.purchase_order_number,
        status=body.status,
    )
    for line_data in body.lines:
        line = ContractLine(**line_data.model_dump())
        _resolve_monthly(line)
        contract.lines.append(line)
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return _get_contract_or_404(contract.id, db)


@router.get("/{contract_id}", response_model=ContractOut)
def get_contract(contract_id: int, db: Session = Depends(get_db)):
    return _get_contract_or_404(contract_id, db)


@router.put("/{contract_id}", response_model=ContractOut)
def update_contract(contract_id: int, body: ContractUpdate, db: Session = Depends(get_db)):
    contract = _get_contract_or_404(contract_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(contract, field, value)
    db.commit()
    return _get_contract_or_404(contract_id, db)


@router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contract(contract_id: int, db: Session = Depends(get_db)):
    contract = _get_contract_or_404(contract_id, db)
    db.delete(contract)
    db.commit()


# ── ContractLine CRUD ─────────────────────────────────────────────────────────

@router.post("/{contract_id}/lines", response_model=ContractLineOut, status_code=status.HTTP_201_CREATED)
def add_line(contract_id: int, body: ContractLineCreate, db: Session = Depends(get_db)):
    _get_contract_or_404(contract_id, db)
    line = ContractLine(contract_id=contract_id, **body.model_dump())
    _resolve_monthly(line)
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


@router.put("/{contract_id}/lines/{line_id}", response_model=ContractLineOut)
def update_line(contract_id: int, line_id: int, body: ContractLineUpdate, db: Session = Depends(get_db)):
    line = db.execute(
        select(ContractLine).where(ContractLine.id == line_id, ContractLine.contract_id == contract_id)
    ).scalar_one_or_none()
    if not line:
        raise HTTPException(status_code=404, detail="Contract line not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(line, field, value)
    _resolve_monthly(line)
    db.commit()
    db.refresh(line)
    return line


@router.delete("/{contract_id}/lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_line(contract_id: int, line_id: int, db: Session = Depends(get_db)):
    line = db.execute(
        select(ContractLine).where(ContractLine.id == line_id, ContractLine.contract_id == contract_id)
    ).scalar_one_or_none()
    if not line:
        raise HTTPException(status_code=404, detail="Contract line not found")
    db.delete(line)
    db.commit()
