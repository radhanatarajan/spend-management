import enum
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select

from src.core.dependencies import get_db, require_write, require_any
from src.models.contract import Contract, ContractLine, ContractAudit, ContractLineAudit, BillingInterval, ContractStatus
from src.models.reference import AccountNumber, ActivityId
from src.models.user import User
from src.schemas.contract import (
    ContractCreate, ContractUpdate, ContractOut,
    ContractLineCreate, ContractLineUpdate, ContractLineOut,
    ContractReportOut, ContractReportRow,
    ContractAuditOut, ContractLineAuditOut,
    ContractAuditReportRow, ContractAuditReportOut,
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

    # Build account_number → AccountNumber lookup for deriving GL dimensions
    acct_ref: dict[str, AccountNumber] = {
        a.account_number: a
        for a in db.execute(select(AccountNumber)).scalars().all()
    }

    # Build (dept_code, account_number) → activity_id lookup
    activity_lookup: dict[tuple[str, str], str] = {}
    for act in db.execute(
        select(ActivityId).options(selectinload(ActivityId.account))
    ).scalars().all():
        if act.department_code and act.account and act.account.account_number:
            activity_lookup[(act.department_code, act.account.account_number)] = act.activity_id

    # Build fiscal-year month list
    fy_months = fiscal_year_months(fiscal_year)  # [(year, month), ...]
    mk_str = [f"{y:04d}-{m:02d}" for y, m in fy_months]
    mk_labels = [month_label(y, m) for y, m in fy_months]

    # Available fiscal years across all contract lines
    fy_set: set[int] = set()
    for c in all_contracts:
        for line in c.lines:
            for fy in range(
                month_to_fy(line.period_start.year, line.period_start.month),
                month_to_fy(line.period_end.year, line.period_end.month) + 1,
            ):
                fy_set.add(fy)
    available_fys = sorted(fy_set)

    # Build report rows — one row per (contract, oracle_account_number) pair
    rows: list[ContractReportRow] = []
    for contract in all_contracts:
        if not contract.lines:
            continue

        # Group this contract's lines by account number
        account_lines: dict[str, list[ContractLine]] = {}
        for line in contract.lines:
            account_lines.setdefault(line.oracle_account_number, []).append(line)

        for acct_num, acct_line_list in sorted(account_lines.items()):
            sorted_lines = sorted(acct_line_list, key=lambda l: l.period_start)
            last_line = sorted_lines[-1]
            last_line_end_int = last_line.period_end.year * 100 + last_line.period_end.month
            first_line_start_int = sorted_lines[0].period_start.year * 100 + sorted_lines[0].period_start.month

            monthly_amounts: dict[str, Decimal | None] = {}
            monthly_assumed: dict[str, bool] = {}

            for (y, m), key in zip(fy_months, mk_str):
                mk_int = y * 100 + m

                if mk_int < first_line_start_int:
                    monthly_amounts[key] = None
                    monthly_assumed[key] = False
                    continue

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
                    if contract.status in (ContractStatus.ACTIVE, ContractStatus.PENDING):
                        monthly_amounts[key] = last_line.monthly_amount
                        monthly_assumed[key] = True
                    else:
                        monthly_amounts[key] = None
                        monthly_assumed[key] = False
                else:
                    monthly_amounts[key] = None
                    monthly_assumed[key] = False

            fy_total = sum(v for v in monthly_amounts.values() if v is not None)
            assumed_total = sum(
                v for k, v in monthly_amounts.items()
                if v is not None and monthly_assumed.get(k)
            )

            if fy_total == 0:
                continue

            acct = acct_ref.get(acct_num)
            first_line_sub_group = sorted_lines[0].oracle_account_sub_group
            rows.append(ContractReportRow(
                id=contract.id,
                vendor_name=contract.vendor_name,
                oracle_department_name=contract.oracle_department_name,
                oracle_account_number=acct_num,
                oracle_account_sub_group=first_line_sub_group,
                account_group=acct.account_group if acct else "",
                account_sub_group=acct.account_sub_group or first_line_sub_group if acct else first_line_sub_group,
                cost_element=acct.cost_element if acct else "",
                activity_id=next((l.activity_id for l in sorted_lines if l.activity_id), None) or activity_lookup.get((contract.oracle_department, acct_num)),
                purchase_order_number=contract.purchase_order_number,
                status=contract.status,
                num_lines=len(sorted_lines),
                is_multi_year=_is_multi_year_lines(sorted_lines),
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
            "account_groups": sorted({r.account_group for r in rows if r.account_group}),
            "account_sub_groups": sorted({r.account_sub_group for r in rows if r.account_sub_group}),
            "cost_elements": sorted({r.cost_element for r in rows if r.cost_element}),
        },
    )


# ── Contract Change Log ───────────────────────────────────────────────────────

@router.get("/reports/audit", response_model=ContractAuditReportOut)
def get_contract_audit_report(
    db: Session = Depends(get_db),
    _=Depends(require_any),
):
    contract_rows = db.execute(
        select(ContractAudit).order_by(ContractAudit.changed_at.desc()).limit(2000)
    ).scalars().all()

    line_rows = db.execute(
        select(ContractLineAudit).order_by(ContractLineAudit.changed_at.desc()).limit(2000)
    ).scalars().all()

    rows: list[ContractAuditReportRow] = []
    for r in contract_rows:
        rows.append(ContractAuditReportRow(
            audit_id=f"c-{r.id}",
            entity_type="Contract",
            entity_id=r.contract_id,
            contract_id=r.contract_id,
            vendor_name=r.vendor_name,
            purchase_order_number=r.purchase_order_number,
            po_line_number=None,
            event_type=r.event_type,
            changes=r.changes,
            changed_by=r.changed_by,
            changed_at=r.changed_at,
        ))
    for r in line_rows:
        rows.append(ContractAuditReportRow(
            audit_id=f"l-{r.id}",
            entity_type="Line",
            entity_id=r.contract_line_id,
            contract_id=r.contract_id,
            vendor_name=r.vendor_name,
            purchase_order_number=r.purchase_order_number,
            po_line_number=r.po_line_number,
            event_type=r.event_type,
            changes=r.changes,
            changed_by=r.changed_by,
            changed_at=r.changed_at,
        ))

    rows.sort(key=lambda r: r.changed_at, reverse=True)

    return ContractAuditReportOut(
        rows=rows,
        filter_options={
            "vendors":      sorted({r.vendor_name for r in rows}),
            "event_types":  sorted({r.event_type for r in rows}),
            "entity_types": sorted({r.entity_type for r in rows}),
            "users":        sorted({r.changed_by for r in rows}),
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


@router.get("/lines/audit", response_model=list[ContractLineAuditOut])
def get_contract_lines_audit(
    contract_id: int | None = Query(None, description="Filter by contract ID"),
    contract_line_id: int | None = Query(None, description="Filter by line ID"),
    db: Session = Depends(get_db),
    _=Depends(require_any),
):
    stmt = select(ContractLineAudit).order_by(ContractLineAudit.changed_at.desc())
    if contract_id is not None:
        stmt = stmt.where(ContractLineAudit.contract_id == contract_id)
    if contract_line_id is not None:
        stmt = stmt.where(ContractLineAudit.contract_line_id == contract_line_id)
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
    db.add(ContractLineAudit(
        contract_line_id=line.id,
        contract_id=contract.id,
        vendor_name=contract.vendor_name,
        purchase_order_number=contract.purchase_order_number,
        po_line_number=line.po_line_number,
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
        db.add(ContractLineAudit(
            contract_line_id=line.id,
            contract_id=contract_id,
            vendor_name=contract.vendor_name,
            purchase_order_number=contract.purchase_order_number,
            po_line_number=line.po_line_number,
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
    db.add(ContractLineAudit(
        contract_line_id=line.id,
        contract_id=contract_id,
        vendor_name=contract.vendor_name,
        purchase_order_number=contract.purchase_order_number,
        po_line_number=line.po_line_number,
        event_type="DELETED",
        changes={},
        changed_by=current_user.email,
    ))
    db.delete(line)
    db.commit()
