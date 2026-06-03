import enum
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from src.core.dependencies import get_db, require_write, require_any
from src.models.contract import Contract, ContractLine, ContractAudit, BillingInterval, ContractStatus
from src.models.user import User
from src.schemas.contract import (
    ContractCreate, ContractUpdate, ContractOut,
    ContractLineCreate, ContractLineUpdate, ContractLineOut,
    ContractReportOut, ContractReportRow,
    ContractAuditOut,
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


def _serialize_val(v):
    """Convert date/Decimal/enum to a JSON-safe string; pass through everything else."""
    if v is None:
        return None
    if isinstance(v, date):
        return str(v)
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, enum.Enum):
        return v.value
    return v


def _group_key(contract: Contract) -> tuple:
    return (
        contract.vendor_name,
        contract.oracle_department,
        contract.oracle_account_number,
        contract.purchase_order_number,
    )


def _is_multi_year_lines(lines: list[ContractLine]) -> bool:
    """True when the lines form a consecutive chain (each line starts the month after the previous ends)."""
    sorted_lines = sorted(lines, key=lambda l: l.period_start)
    if len(sorted_lines) < 2:
        return False
    for a, b in zip(sorted_lines, sorted_lines[1:]):
        next_year  = a.period_end.year + (1 if a.period_end.month == 12 else 0)
        next_month = 1 if a.period_end.month == 12 else a.period_end.month + 1
        if b.period_start.year != next_year or b.period_start.month != next_month:
            return False
    return True


def _is_multi_year(contract: Contract) -> bool:
    return _is_multi_year_lines(list(contract.lines))


# ── Contract Report ───────────────────────────────────────────────────────────

@router.get("/report", response_model=ContractReportOut)
def get_contract_report(
    fiscal_year: int = Query(..., description="Fiscal year end (FY2027 = May-2026 → Apr-2027)"),
    db: Session = Depends(get_db),
):
    all_contracts = db.execute(
        select(Contract).options(selectinload(Contract.lines)).order_by(Contract.vendor_name)
    ).scalars().all()

    # Group contracts by (vendor, dept, account, PO) — same logic as ContractsPage
    groups: dict[tuple, list[Contract]] = {}
    for c in all_contracts:
        groups.setdefault(_group_key(c), []).append(c)

    # Build report groups — all groups, not just multi-year
    report_groups = []
    for key, contracts in groups.items():
        merged_lines = [line for c in contracts for line in c.lines]
        if not merged_lines:
            continue
        sorted_merged = sorted(merged_lines, key=lambda l: l.period_start)
        # Status from the contract that owns the last line
        last_contract_id = sorted_merged[-1].contract_id
        last_contract = next((c for c in contracts if c.id == last_contract_id), contracts[0])
        report_groups.append({
            "representative": contracts[0],
            "lines": sorted_merged,
            "status": last_contract.status,
            "is_multi_year": _is_multi_year_lines(merged_lines),
        })
    report_groups.sort(key=lambda g: g["representative"].vendor_name)

    # Build fiscal-year month list
    fy_months = fiscal_year_months(fiscal_year)  # [(year, month), ...]
    mk_str = [f"{y:04d}-{m:02d}" for y, m in fy_months]
    mk_labels = [month_label(y, m) for y, m in fy_months]

    # Available fiscal years across all group lines
    fy_set: set[int] = set()
    for g in report_groups:
        for line in g["lines"]:
            s_fy = month_to_fy(line.period_start.year, line.period_start.month)
            e_fy = month_to_fy(line.period_end.year, line.period_end.month)
            for fy in range(s_fy, e_fy + 1):
                fy_set.add(fy)
    available_fys = sorted(fy_set)

    # Build report rows
    rows: list[ContractReportRow] = []
    for g in report_groups:
        contract = g["representative"]
        sorted_lines = g["lines"]
        group_status = g["status"]
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
                # Only for active/pending contracts; expired/cancelled don't renew
                if group_status in (ContractStatus.ACTIVE, ContractStatus.PENDING):
                    monthly_amounts[key] = last_line.monthly_amount
                    monthly_assumed[key] = True
                else:
                    monthly_amounts[key] = None
                    monthly_assumed[key] = False
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
            status=group_status,
            num_lines=len(sorted_lines),
            is_multi_year=g["is_multi_year"],
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


# ── Audit log ────────────────────────────────────────────────────────────────

@router.get("/audit", response_model=list[ContractAuditOut])
def get_contract_audit(
    contract_id: int | None = Query(None, description="Filter by contract ID"),
    vendor_name: str | None = Query(None, description="Filter by vendor name"),
    db: Session = Depends(get_db),
    _=Depends(require_any),
):
    stmt = select(ContractAudit).order_by(ContractAudit.changed_at.desc())
    if contract_id is not None:
        stmt = stmt.where(ContractAudit.contract_id == contract_id)
    if vendor_name:
        stmt = stmt.where(ContractAudit.vendor_name == vendor_name)
    return db.execute(stmt.limit(500)).scalars().all()


# ── Contract CRUD ─────────────────────────────────────────────────────────────

@router.get("", response_model=list[ContractOut])
def list_contracts(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Contract).options(selectinload(Contract.lines)).order_by(Contract.vendor_name)
    ).scalars().all()
    return rows


@router.post("", response_model=ContractOut, status_code=status.HTTP_201_CREATED)
def create_contract(
    body: ContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write),
):
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
    db.add(ContractAudit(
        contract_id=contract.id,
        vendor_name=contract.vendor_name,
        purchase_order_number=contract.purchase_order_number,
        entity="contract",
        entity_id=contract.id,
        event_type="CREATED",
        changes={},
        changed_by=current_user.email,
    ))
    db.commit()
    return _get_contract_or_404(contract.id, db)


@router.get("/{contract_id}", response_model=ContractOut)
def get_contract(contract_id: int, db: Session = Depends(get_db)):
    return _get_contract_or_404(contract_id, db)


@router.put("/{contract_id}", response_model=ContractOut)
def update_contract(
    contract_id: int,
    body: ContractUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write),
):
    contract = _get_contract_or_404(contract_id, db)
    updates = body.model_dump(exclude_unset=True)
    changes = {
        f: {"old": _serialize_val(getattr(contract, f)), "new": _serialize_val(v)}
        for f, v in updates.items()
        if _serialize_val(getattr(contract, f)) != _serialize_val(v)
    }
    for field, value in updates.items():
        setattr(contract, field, value)
    if changes:
        db.add(ContractAudit(
            contract_id=contract.id,
            vendor_name=contract.vendor_name,
            purchase_order_number=contract.purchase_order_number,
            entity="contract",
            entity_id=contract.id,
            event_type="UPDATED",
            changes=changes,
            changed_by=current_user.email,
        ))
    db.commit()
    return _get_contract_or_404(contract_id, db)


@router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write),
):
    contract = _get_contract_or_404(contract_id, db)
    db.add(ContractAudit(
        contract_id=contract.id,
        vendor_name=contract.vendor_name,
        purchase_order_number=contract.purchase_order_number,
        entity="contract",
        entity_id=contract.id,
        event_type="DELETED",
        changes={},
        changed_by=current_user.email,
    ))
    db.delete(contract)
    db.commit()


# ── ContractLine CRUD ─────────────────────────────────────────────────────────

@router.post("/{contract_id}/lines", response_model=ContractLineOut, status_code=status.HTTP_201_CREATED)
def add_line(
    contract_id: int,
    body: ContractLineCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write),
):
    contract = _get_contract_or_404(contract_id, db)
    line = ContractLine(contract_id=contract_id, **body.model_dump())
    _resolve_monthly(line)
    db.add(line)
    db.commit()
    db.refresh(line)
    db.add(ContractAudit(
        contract_id=contract.id,
        vendor_name=contract.vendor_name,
        purchase_order_number=contract.purchase_order_number,
        entity="line",
        entity_id=line.id,
        event_type="CREATED",
        changes={},
        changed_by=current_user.email,
    ))
    db.commit()
    return line


@router.put("/{contract_id}/lines/{line_id}", response_model=ContractLineOut)
def update_line(
    contract_id: int,
    line_id: int,
    body: ContractLineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write),
):
    line = db.execute(
        select(ContractLine).where(ContractLine.id == line_id, ContractLine.contract_id == contract_id)
    ).scalar_one_or_none()
    if not line:
        raise HTTPException(status_code=404, detail="Contract line not found")
    contract = _get_contract_or_404(contract_id, db)
    updates = body.model_dump(exclude_unset=True)
    changes = {
        f: {"old": _serialize_val(getattr(line, f)), "new": _serialize_val(v)}
        for f, v in updates.items()
        if _serialize_val(getattr(line, f)) != _serialize_val(v)
    }
    for field, value in updates.items():
        setattr(line, field, value)
    _resolve_monthly(line)
    if changes:
        db.add(ContractAudit(
            contract_id=contract_id,
            vendor_name=contract.vendor_name,
            purchase_order_number=contract.purchase_order_number,
            entity="line",
            entity_id=line.id,
            event_type="UPDATED",
            changes=changes,
            changed_by=current_user.email,
        ))
    db.commit()
    db.refresh(line)
    return line


@router.delete("/{contract_id}/lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_line(
    contract_id: int,
    line_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write),
):
    line = db.execute(
        select(ContractLine).where(ContractLine.id == line_id, ContractLine.contract_id == contract_id)
    ).scalar_one_or_none()
    if not line:
        raise HTTPException(status_code=404, detail="Contract line not found")
    contract = _get_contract_or_404(contract_id, db)
    db.add(ContractAudit(
        contract_id=contract_id,
        vendor_name=contract.vendor_name,
        purchase_order_number=contract.purchase_order_number,
        entity="line",
        entity_id=line.id,
        event_type="DELETED",
        changes={},
        changed_by=current_user.email,
    ))
    db.delete(line)
    db.commit()
