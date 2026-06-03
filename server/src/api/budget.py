from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, distinct

from src.core.dependencies import get_db, require_any, require_biz_admin, require_write, get_current_user
from src.models.budget import BudgetScenario, BudgetEntry, BudgetNcConfig, BudgetEntryAudit, BudgetScenarioAudit, BudgetNcConfigAudit
from src.models.spend import Spend
from src.models.user import User
from sqlalchemy import text as sa_text
from src.schemas.budget import (
    BudgetScenarioCreate, BudgetScenarioUpdate, BudgetScenarioOut,
    BudgetScenarioAuditOut, BudgetNcConfigAuditOut,
    BudgetEntryStatusUpdate, BudgetEntryAuditOut,
    BudgetEntryUpsert, BudgetEntryOut,
    BudgetNcConfigOut, BudgetNcConfigUpdate,
    NonControllablePlanOut, DepartmentBudgetRow, QuarterlyAmounts,
    ScenarioAmounts, DeltaAmounts, DeptCompareRow, ScenarioCompareOut,
    BudgetAuditReportRow, BudgetAuditFilterOptions, BudgetAuditReportOut,
)

router = APIRouter(prefix="/api/budget", tags=["budget"])

# (current_status, new_status) → roles that may make this transition
ALLOWED_TRANSITIONS: dict[tuple[str, str], list[str]] = {
    ("DRAFT",            "READY_FOR_REVIEW"): ["SERVICE_OWNER", "BIZ_ADMIN", "ADMIN"],
    ("DRAFT",            "CANCELLED"):        ["SERVICE_OWNER", "BIZ_ADMIN", "ADMIN"],
    ("READY_FOR_REVIEW", "DRAFT"):            ["BIZ_ADMIN", "ADMIN"],
    ("READY_FOR_REVIEW", "APPROVED"):         ["BIZ_ADMIN", "ADMIN"],
    ("READY_FOR_REVIEW", "CANCELLED"):        ["BIZ_ADMIN", "ADMIN"],
    ("APPROVED",         "READY_FOR_REVIEW"): ["BIZ_ADMIN", "ADMIN"],
    ("APPROVED",         "FINAL"):            ["BIZ_ADMIN", "ADMIN"],
    ("APPROVED",         "CANCELLED"):        ["BIZ_ADMIN", "ADMIN"],
    ("FINAL",            "APPROVED"):         ["ADMIN"],
    ("CANCELLED",        "DRAFT"):            ["ADMIN"],
}

QUARTER_MONTHS = {
    "q1": [1, 2, 3],
    "q2": [4, 5, 6],
    "q3": [7, 8, 9],
    "q4": [10, 11, 12],
}


def _month_key(year: int, month: int) -> int:
    return year * 100 + month


def _build_quarterly(q1: Decimal | None, q2: Decimal | None, q3: Decimal | None, q4: Decimal | None) -> QuarterlyAmounts:
    q1 = q1 or Decimal("0")
    q2 = q2 or Decimal("0")
    q3 = q3 or Decimal("0")
    q4 = q4 or Decimal("0")
    return QuarterlyAmounts(q1=q1, q2=q2, q3=q3, q4=q4, annual=q1 + q2 + q3 + q4)


def _compute_current(
    fiscal_year: int,
    selected_elements: list[str],
    db: Session,
    cutoff_month_key: int | None = None,
    selected_account_groups: list[str] | None = None,
    selected_account_sub_groups: list[str] | None = None,
) -> tuple[dict[str, DepartmentBudgetRow], list[str]]:
    """Compute 'Current' quarterly amounts using the prior fiscal year as the planning baseline.

    Prior year (fiscal_year - 1) months are used:
      - Months <= cutoff_month_key  → confirmed actuals from spend table
      - Months >  cutoff_month_key  → carry-forward from the last actual month at/before cutoff
    If cutoff is null, auto-detects the last available month within the prior year.
    """
    prior_year = fiscal_year - 1
    py_start = _month_key(prior_year, 1)
    py_end   = _month_key(prior_year, 12)

    # Actuals for the prior year
    if selected_elements:
        conditions = [
            Spend.month_key >= py_start,
            Spend.month_key <= py_end,
            Spend.oracle_cost_element.in_(selected_elements),
        ]
        if selected_account_groups:
            conditions.append(Spend.oracle_account_group.in_(selected_account_groups))
        if selected_account_sub_groups:
            conditions.append(Spend.oracle_account_sub_group.in_(selected_account_sub_groups))
        actuals_rows = db.execute(
            select(Spend.oracle_department_name, Spend.month_key, func.sum(Spend.amount_usd).label("total"))
            .where(*conditions)
            .group_by(Spend.oracle_department_name, Spend.month_key)
        ).all()
    else:
        actuals_rows = []

    # Build dict: dept → {month_key: amount}
    actuals: dict[str, dict[int, Decimal]] = {}
    for dept, mk, total in actuals_rows:
        actuals.setdefault(dept, {})[mk] = Decimal(str(total))

    # Carry-forward source: last available month at/before cutoff (bounded to prior year)
    if cutoff_month_key:
        last_mk = db.execute(
            select(func.max(Spend.month_key)).where(Spend.month_key <= cutoff_month_key)
        ).scalar_one_or_none()
    else:
        last_mk = db.execute(
            select(func.max(Spend.month_key)).where(Spend.month_key <= py_end)
        ).scalar_one_or_none()

    # Per-dept carry-forward amount from last_mk
    carry_forward: dict[str, Decimal] = {}
    if last_mk and selected_elements:
        cf_conditions = [
            Spend.month_key == last_mk,
            Spend.oracle_cost_element.in_(selected_elements),
        ]
        if selected_account_groups:
            cf_conditions.append(Spend.oracle_account_group.in_(selected_account_groups))
        if selected_account_sub_groups:
            cf_conditions.append(Spend.oracle_account_sub_group.in_(selected_account_sub_groups))
        cf_rows = db.execute(
            select(Spend.oracle_department_name, func.sum(Spend.amount_usd).label("total"))
            .where(*cf_conditions)
            .group_by(Spend.oracle_department_name)
        ).all()
        for dept, total in cf_rows:
            carry_forward[dept] = Decimal(str(total))

    # Get all departments with their codes from spend
    all_dept_rows = db.execute(
        select(Spend.oracle_department_name, Spend.oracle_department)
        .distinct()
        .order_by(Spend.oracle_department_name)
    ).all()
    dept_code_map: dict[str, str] = {name: code for name, code in all_dept_rows}

    for d in (set(actuals.keys()) | set(carry_forward.keys())):
        if d not in dept_code_map:
            dept_code_map[d] = ""
    all_depts = sorted(set(dept_code_map.keys()))

    result: dict[str, DepartmentBudgetRow] = {}
    for dept in all_depts:
        dept_actuals = actuals.get(dept, {})
        dept_cf = carry_forward.get(dept, Decimal("0"))

        q_amounts: dict[str, Decimal] = {}
        q_forecast: dict[str, bool] = {}

        for q_name, months in QUARTER_MONTHS.items():
            q_total = Decimal("0")
            all_forecast = True
            for m in months:
                mk = _month_key(prior_year, m)
                if cutoff_month_key:
                    if mk <= cutoff_month_key:
                        q_total += dept_actuals.get(mk, Decimal("0"))
                        all_forecast = False
                    else:
                        q_total += dept_cf
                else:
                    if mk in dept_actuals:
                        q_total += dept_actuals[mk]
                        all_forecast = False
                    else:
                        q_total += dept_cf
            q_amounts[q_name] = q_total
            q_forecast[q_name] = all_forecast

        row = DepartmentBudgetRow(
            department_name=dept,
            department_code=dept_code_map.get(dept),
            current=QuarterlyAmounts(
                q1=q_amounts["q1"],
                q2=q_amounts["q2"],
                q3=q_amounts["q3"],
                q4=q_amounts["q4"],
                annual=sum(q_amounts.values()),
            ),
            current_is_forecast=q_forecast,
            approved_rec=QuarterlyAmounts(),
            additional_ask=QuarterlyAmounts(),
        )
        result[dept] = row

    return result, all_depts


# ── Cost Elements ─────────────────────────────────────────────────────────────

@router.get("/cost-elements", response_model=list[str])
def get_cost_elements(
    db: Session = Depends(get_db),
    _: User = Depends(require_any),
):
    rows = db.execute(
        select(distinct(Spend.oracle_cost_element)).order_by(Spend.oracle_cost_element)
    ).all()
    return [r[0] for r in rows]


@router.get("/account-groups", response_model=list[str])
def get_account_groups(
    db: Session = Depends(get_db),
    _: User = Depends(require_any),
):
    rows = db.execute(
        select(distinct(Spend.oracle_account_group)).order_by(Spend.oracle_account_group)
    ).all()
    return [r[0] for r in rows if r[0]]


@router.get("/account-sub-groups", response_model=list[str])
def get_account_sub_groups(
    db: Session = Depends(get_db),
    _: User = Depends(require_any),
):
    rows = db.execute(
        select(distinct(Spend.oracle_account_sub_group)).order_by(Spend.oracle_account_sub_group)
    ).all()
    return [r[0] for r in rows if r[0]]


# ── NC Config ─────────────────────────────────────────────────────────────────

@router.get("/config", response_model=BudgetNcConfigOut)
def get_nc_config(
    fiscal_year: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_any),
):
    cfg = db.execute(
        select(BudgetNcConfig).where(BudgetNcConfig.fiscal_year == fiscal_year)
    ).scalar_one_or_none()
    if not cfg:
        cfg = BudgetNcConfig(
            fiscal_year=fiscal_year,
            selected_cost_elements=[],
            updated_by=current_user.email,
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


@router.put("/config", response_model=BudgetNcConfigOut)
def update_nc_config(
    body: BudgetNcConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_biz_admin),
):
    cfg = db.execute(
        select(BudgetNcConfig).where(BudgetNcConfig.fiscal_year == body.fiscal_year)
    ).scalar_one_or_none()
    if not cfg:
        cfg = BudgetNcConfig(
            fiscal_year=body.fiscal_year,
            selected_cost_elements=body.selected_cost_elements,
            selected_account_groups=body.selected_account_groups,
            selected_account_sub_groups=body.selected_account_sub_groups,
            actuals_cutoff_month_key=body.actuals_cutoff_month_key,
            updated_by=current_user.email,
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
        db.add(BudgetNcConfigAudit(
            fiscal_year=body.fiscal_year,
            event_type="CREATED",
            changes={},
            changed_by=current_user.email,
        ))
    else:
        changes = {}
        if cfg.selected_cost_elements != body.selected_cost_elements:
            changes["selected_cost_elements"] = {"old": cfg.selected_cost_elements, "new": body.selected_cost_elements}
        if cfg.selected_account_groups != body.selected_account_groups:
            changes["selected_account_groups"] = {"old": cfg.selected_account_groups, "new": body.selected_account_groups}
        if cfg.selected_account_sub_groups != body.selected_account_sub_groups:
            changes["selected_account_sub_groups"] = {"old": cfg.selected_account_sub_groups, "new": body.selected_account_sub_groups}
        if cfg.actuals_cutoff_month_key != body.actuals_cutoff_month_key:
            changes["actuals_cutoff_month_key"] = {"old": cfg.actuals_cutoff_month_key, "new": body.actuals_cutoff_month_key}
        cfg.selected_cost_elements = body.selected_cost_elements
        cfg.selected_account_groups = body.selected_account_groups
        cfg.selected_account_sub_groups = body.selected_account_sub_groups
        cfg.actuals_cutoff_month_key = body.actuals_cutoff_month_key
        cfg.updated_by = current_user.email
        if changes:
            db.add(BudgetNcConfigAudit(
                fiscal_year=body.fiscal_year,
                event_type="UPDATED",
                changes=changes,
                changed_by=current_user.email,
            ))
    db.commit()
    db.refresh(cfg)
    return cfg


@router.get("/config/audit", response_model=list[BudgetNcConfigAuditOut])
def get_nc_config_audit(
    fiscal_year: int | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_any),
):
    stmt = select(BudgetNcConfigAudit).order_by(BudgetNcConfigAudit.changed_at.desc())
    if fiscal_year is not None:
        stmt = stmt.where(BudgetNcConfigAudit.fiscal_year == fiscal_year)
    return db.execute(stmt.limit(500)).scalars().all()


# ── Scenarios ─────────────────────────────────────────────────────────────────

@router.get("/scenarios", response_model=list[BudgetScenarioOut])
def list_scenarios(
    fiscal_year: int = Query(...),
    budget_type: str = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_any),
):
    rows = db.execute(
        select(BudgetScenario)
        .where(
            BudgetScenario.fiscal_year == fiscal_year,
            BudgetScenario.budget_type == budget_type,
        )
        .order_by(BudgetScenario.is_baseline.desc(), BudgetScenario.created_at)
    ).scalars().all()
    return rows


@router.post("/scenarios", response_model=BudgetScenarioOut, status_code=status.HTTP_201_CREATED)
def create_scenario(
    body: BudgetScenarioCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_biz_admin),
):
    scenario = BudgetScenario(
        name=body.name,
        description=body.description,
        fiscal_year=body.fiscal_year,
        budget_type=body.budget_type,
        is_baseline=False,
        created_by=current_user.email,
    )
    db.add(scenario)
    db.flush()  # get scenario.id before copying entries

    if body.copy_from_scenario_id:
        source_entries = db.execute(
            select(BudgetEntry).where(BudgetEntry.scenario_id == body.copy_from_scenario_id)
        ).scalars().all()
        for e in source_entries:
            db.add(BudgetEntry(
                scenario_id=scenario.id,
                department_name=e.department_name,
                entry_type=e.entry_type,
                q1_amount=e.q1_amount,
                q2_amount=e.q2_amount,
                q3_amount=e.q3_amount,
                q4_amount=e.q4_amount,
                notes=e.notes,
                created_by=current_user.email,
            ))

    db.add(BudgetScenarioAudit(
        scenario_id=scenario.id,
        fiscal_year=scenario.fiscal_year,
        scenario_name=scenario.name,
        event_type="CREATED",
        changes={},
        changed_by=current_user.email,
    ))
    db.commit()
    db.refresh(scenario)
    return scenario


@router.get("/scenario-audit", response_model=list[BudgetScenarioAuditOut])
def get_scenario_audit(
    scenario_id: int | None = Query(None),
    fiscal_year: int | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_any),
):
    stmt = select(BudgetScenarioAudit).order_by(BudgetScenarioAudit.changed_at.desc())
    if scenario_id is not None:
        stmt = stmt.where(BudgetScenarioAudit.scenario_id == scenario_id)
    if fiscal_year is not None:
        stmt = stmt.where(BudgetScenarioAudit.fiscal_year == fiscal_year)
    return db.execute(stmt.limit(500)).scalars().all()


@router.put("/scenarios/{scenario_id}", response_model=BudgetScenarioOut)
def update_scenario(
    scenario_id: int,
    body: BudgetScenarioUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_biz_admin),
):
    scenario = db.get(BudgetScenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    updates = body.model_dump(exclude_unset=True)
    changes = {
        f: {"old": getattr(scenario, f), "new": v}
        for f, v in updates.items()
        if getattr(scenario, f) != v
    }
    for f, v in updates.items():
        setattr(scenario, f, v)
    if changes:
        db.add(BudgetScenarioAudit(
            scenario_id=scenario.id,
            fiscal_year=scenario.fiscal_year,
            scenario_name=scenario.name,
            event_type="UPDATED",
            changes=changes,
            changed_by=current_user.email,
        ))
    db.commit()
    db.refresh(scenario)
    return scenario


@router.delete("/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_biz_admin),
):
    scenario = db.get(BudgetScenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    if scenario.is_baseline:
        raise HTTPException(status_code=400, detail="Cannot delete the baseline scenario")
    db.add(BudgetScenarioAudit(
        scenario_id=scenario.id,
        fiscal_year=scenario.fiscal_year,
        scenario_name=scenario.name,
        event_type="DELETED",
        changes={},
        changed_by=current_user.email,
    ))
    db.delete(scenario)
    db.commit()


@router.patch("/entries/{entry_id}/status", response_model=BudgetEntryOut)
def update_entry_status(
    entry_id: int,
    body: BudgetEntryStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write),
):
    entry = db.get(BudgetEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    role = str(current_user.role).split(".")[-1]
    allowed = ALLOWED_TRANSITIONS.get((entry.status, body.status))
    if allowed is None:
        raise HTTPException(status_code=400, detail=f"Transition {entry.status} → {body.status} is not permitted")
    if role not in allowed:
        raise HTTPException(status_code=403, detail=f"Your role ({role}) cannot make this transition")

    old_status = entry.status
    entry.status = body.status

    db.add(BudgetEntryAudit(
        scenario_id=entry.scenario_id,
        entry_id=entry.id,
        department_name=entry.department_name,
        entry_type=entry.entry_type,
        event_type="STATUS_CHANGED",
        changes={"status": {"old": old_status, "new": body.status}},
        changed_by=current_user.email,
    ))

    db.commit()
    db.refresh(entry)
    return entry


@router.get("/scenarios/{scenario_id}/audit", response_model=list[BudgetEntryAuditOut])
def get_scenario_audit(
    scenario_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_any),
):
    rows = db.execute(
        select(BudgetEntryAudit)
        .where(BudgetEntryAudit.scenario_id == scenario_id)
        .order_by(BudgetEntryAudit.changed_at.desc())
    ).scalars().all()
    return rows


# ── Audit Report ─────────────────────────────────────────────────────────────

@router.get("/reports/audit", response_model=BudgetAuditReportOut)
def get_audit_report(
    fiscal_year: int = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_any),
):
    rows = db.execute(
        sa_text("""
            SELECT audit_id, entry_id, scenario_id, scenario_name, fiscal_year,
                   department_name, entry_type, event_type, changed_by, changed_at,
                   q1_old, q1_new, q2_old, q2_new, q3_old, q3_new, q4_old, q4_new,
                   status_old, status_new,
                   current_q1, current_q2, current_q3, current_q4, current_status
            FROM v_budget_entry_audit
            WHERE fiscal_year = :fy
            ORDER BY changed_at DESC
        """),
        {"fy": fiscal_year},
    ).mappings().all()

    row_list = [BudgetAuditReportRow(**dict(r)) for r in rows]

    filter_options = BudgetAuditFilterOptions(
        scenarios=sorted({r.scenario_name for r in row_list}),
        departments=sorted({r.department_name for r in row_list}),
        entry_types=sorted({r.entry_type for r in row_list}),
        event_types=sorted({r.event_type for r in row_list}),
        users=sorted({r.changed_by for r in row_list}),
    )

    return BudgetAuditReportOut(
        fiscal_year=fiscal_year,
        rows=row_list,
        filter_options=filter_options,
    )


# ── Non-Controllable Plan ─────────────────────────────────────────────────────

@router.get("/non-controllable", response_model=NonControllablePlanOut)
def get_non_controllable_plan(
    fiscal_year: int = Query(...),
    scenario_id: int = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_any),
):
    scenario = db.get(BudgetScenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Config
    cfg = db.execute(
        select(BudgetNcConfig).where(BudgetNcConfig.fiscal_year == fiscal_year)
    ).scalar_one_or_none()
    selected_elements = cfg.selected_cost_elements if cfg else []

    # Available cost elements
    available_rows = db.execute(
        select(distinct(Spend.oracle_cost_element)).order_by(Spend.oracle_cost_element)
    ).all()
    available_elements = [r[0] for r in available_rows]

    # All scenarios for this FY/type
    scenarios = db.execute(
        select(BudgetScenario)
        .where(
            BudgetScenario.fiscal_year == fiscal_year,
            BudgetScenario.budget_type == "NON_CONTROLLABLE",
        )
        .order_by(BudgetScenario.is_baseline.desc(), BudgetScenario.created_at)
    ).scalars().all()

    # Compute current from actuals + carry-forward
    dept_rows, all_depts = _compute_current(
        fiscal_year, selected_elements, db,
        cfg.actuals_cutoff_month_key if cfg else None,
        cfg.selected_account_groups if cfg else None,
        cfg.selected_account_sub_groups if cfg else None,
    )

    # Load entries for the scenario
    entries = db.execute(
        select(BudgetEntry).where(BudgetEntry.scenario_id == scenario_id)
    ).scalars().all()

    entry_map: dict[tuple[str, str], BudgetEntry] = {
        (e.department_name, e.entry_type): e for e in entries
    }

    # Include departments that have entries but no prior-year spend data
    for dept_name in {e.department_name for e in entries}:
        if dept_name not in dept_rows:
            dept_rows[dept_name] = DepartmentBudgetRow(
                department_name=dept_name,
                department_code=None,
                current=QuarterlyAmounts(),
                current_is_forecast={"q1": False, "q2": False, "q3": False, "q4": False},
                approved_rec=QuarterlyAmounts(),
                additional_ask=QuarterlyAmounts(),
            )
    all_depts = sorted(dept_rows.keys())

    for dept in all_depts:
        row = dept_rows.get(dept)
        if not row:
            continue

        approved = entry_map.get((dept, "APPROVED_REC"))
        if approved:
            row.approved_rec = _build_quarterly(
                approved.q1_amount, approved.q2_amount,
                approved.q3_amount, approved.q4_amount
            )
            row.approved_rec_entry_id = approved.id
            row.approved_rec_status = approved.status

        additional = entry_map.get((dept, "ADDITIONAL_ASK"))
        if additional:
            row.additional_ask = _build_quarterly(
                additional.q1_amount, additional.q2_amount,
                additional.q3_amount, additional.q4_amount
            )
            row.additional_ask_entry_id = additional.id
            row.additional_ask_status = additional.status

    # Build totals
    def _sum_q(rows: list[DepartmentBudgetRow], field: str) -> QuarterlyAmounts:
        q1 = sum(getattr(r, field).q1 for r in rows)
        q2 = sum(getattr(r, field).q2 for r in rows)
        q3 = sum(getattr(r, field).q3 for r in rows)
        q4 = sum(getattr(r, field).q4 for r in rows)
        return QuarterlyAmounts(q1=q1, q2=q2, q3=q3, q4=q4, annual=q1+q2+q3+q4)

    dept_list = list(dept_rows.values())
    totals = DepartmentBudgetRow(
        department_name="__totals__",
        current=_sum_q(dept_list, "current"),
        current_is_forecast={},
        approved_rec=_sum_q(dept_list, "approved_rec"),
        additional_ask=_sum_q(dept_list, "additional_ask"),
    )

    return NonControllablePlanOut(
        fiscal_year=fiscal_year,
        scenario_id=scenario_id,
        scenarios=scenarios,
        selected_cost_elements=selected_elements,
        available_cost_elements=available_elements,
        departments=dept_list,
        totals=totals,
    )


# ── Entries ───────────────────────────────────────────────────────────────────

@router.put("/entries", response_model=BudgetEntryOut)
def upsert_entry(
    body: BudgetEntryUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write),
):
    scenario = db.get(BudgetScenario, body.scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    existing = db.execute(
        select(BudgetEntry).where(
            BudgetEntry.scenario_id == body.scenario_id,
            BudgetEntry.department_name == body.department_name,
            BudgetEntry.entry_type == body.entry_type,
        )
    ).scalar_one_or_none()

    if existing and existing.status == "FINAL":
        raise HTTPException(status_code=403, detail="Cannot edit a FINAL entry")

    # Capture old values for audit before any change
    old_q1 = existing.q1_amount if existing else None
    old_q2 = existing.q2_amount if existing else None
    old_q3 = existing.q3_amount if existing else None
    old_q4 = existing.q4_amount if existing else None

    if existing:
        existing.q1_amount = body.q1_amount
        existing.q2_amount = body.q2_amount
        existing.q3_amount = body.q3_amount
        existing.q4_amount = body.q4_amount
        existing.notes = body.notes
        entry = existing
    else:
        entry = BudgetEntry(
            scenario_id=body.scenario_id,
            department_name=body.department_name,
            entry_type=body.entry_type,
            q1_amount=body.q1_amount,
            q2_amount=body.q2_amount,
            q3_amount=body.q3_amount,
            q4_amount=body.q4_amount,
            notes=body.notes,
            created_by=current_user.email,
        )
        db.add(entry)

    db.flush()

    def _dec_str(v) -> str | None:
        return str(v) if v is not None else None

    def _amounts_differ(a, b) -> bool:
        if (a is None) != (b is None):
            return True
        if a is None:
            return False
        return Decimal(str(a)) != Decimal(str(b))

    changes = {}
    for field, old_val, new_val in [
        ("q1_amount", old_q1, body.q1_amount),
        ("q2_amount", old_q2, body.q2_amount),
        ("q3_amount", old_q3, body.q3_amount),
        ("q4_amount", old_q4, body.q4_amount),
    ]:
        if _amounts_differ(old_val, new_val):
            changes[field] = {"old": _dec_str(old_val), "new": _dec_str(new_val)}

    if changes:
        db.add(BudgetEntryAudit(
            scenario_id=body.scenario_id,
            entry_id=entry.id,
            department_name=body.department_name,
            entry_type=body.entry_type,
            event_type="AMOUNT_CHANGED",
            changes=changes,
            changed_by=current_user.email,
        ))

    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_write),
):
    entry = db.get(BudgetEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()


# ── Scenario Comparison ───────────────────────────────────────────────────────

def _make_scenario_amounts(q1=None, q2=None, q3=None, q4=None) -> ScenarioAmounts:
    q1 = Decimal(str(q1 or 0))
    q2 = Decimal(str(q2 or 0))
    q3 = Decimal(str(q3 or 0))
    q4 = Decimal(str(q4 or 0))
    return ScenarioAmounts(q1=q1, q2=q2, q3=q3, q4=q4, annual=q1+q2+q3+q4)


def _make_delta(a: ScenarioAmounts, b: ScenarioAmounts) -> DeltaAmounts:
    def pct(av, bv):
        av = float(av)
        return round((float(bv) - av) / av * 100, 2) if av != 0 else 0.0

    return DeltaAmounts(
        q1=b.q1 - a.q1, q2=b.q2 - a.q2, q3=b.q3 - a.q3, q4=b.q4 - a.q4,
        annual=b.annual - a.annual,
        q1_pct=pct(a.q1, b.q1), q2_pct=pct(a.q2, b.q2),
        q3_pct=pct(a.q3, b.q3), q4_pct=pct(a.q4, b.q4),
        annual_pct=pct(a.annual, b.annual),
    )


def _zero_amounts() -> ScenarioAmounts:
    return ScenarioAmounts()


def _sum_scenario_amounts(rows: list[ScenarioAmounts]) -> ScenarioAmounts:
    q1 = sum(r.q1 for r in rows)
    q2 = sum(r.q2 for r in rows)
    q3 = sum(r.q3 for r in rows)
    q4 = sum(r.q4 for r in rows)
    return ScenarioAmounts(q1=q1, q2=q2, q3=q3, q4=q4, annual=q1+q2+q3+q4)


@router.get("/compare", response_model=ScenarioCompareOut)
def compare_scenarios(
    fiscal_year: int = Query(...),
    scenario_a_id: int = Query(...),
    scenario_b_id: int = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_any),
):
    scenario_a = db.get(BudgetScenario, scenario_a_id)
    scenario_b = db.get(BudgetScenario, scenario_b_id)
    if not scenario_a:
        raise HTTPException(status_code=404, detail="Scenario A not found")
    if not scenario_b:
        raise HTTPException(status_code=404, detail="Scenario B not found")

    # All scenarios for selector population
    all_scenarios = db.execute(
        select(BudgetScenario)
        .where(BudgetScenario.fiscal_year == fiscal_year, BudgetScenario.budget_type == "NON_CONTROLLABLE")
        .order_by(BudgetScenario.is_baseline.desc(), BudgetScenario.created_at)
    ).scalars().all()

    # Load entries for both scenarios
    entries_a = db.execute(select(BudgetEntry).where(BudgetEntry.scenario_id == scenario_a_id)).scalars().all()
    entries_b = db.execute(select(BudgetEntry).where(BudgetEntry.scenario_id == scenario_b_id)).scalars().all()

    map_a: dict[tuple[str, str], BudgetEntry] = {(e.department_name, e.entry_type): e for e in entries_a}
    map_b: dict[tuple[str, str], BudgetEntry] = {(e.department_name, e.entry_type): e for e in entries_b}

    # Get all departments with codes
    dept_rows = db.execute(
        select(Spend.oracle_department_name, Spend.oracle_department).distinct()
        .order_by(Spend.oracle_department_name)
    ).all()
    dept_code_map = {name: code for name, code in dept_rows}

    # Also include depts that appear in entries but not in spend
    for e in (entries_a + entries_b):
        if e.department_name not in dept_code_map:
            dept_code_map[e.department_name] = None
    all_depts = sorted(dept_code_map.keys())

    departments: list[DeptCompareRow] = []
    for dept in all_depts:
        ea_rec  = map_a.get((dept, "APPROVED_REC"))
        ea_ask  = map_a.get((dept, "ADDITIONAL_ASK"))
        eb_rec  = map_b.get((dept, "APPROVED_REC"))
        eb_ask  = map_b.get((dept, "ADDITIONAL_ASK"))

        rec_a   = _make_scenario_amounts(ea_rec.q1_amount,  ea_rec.q2_amount,  ea_rec.q3_amount,  ea_rec.q4_amount)  if ea_rec  else _zero_amounts()
        rec_b   = _make_scenario_amounts(eb_rec.q1_amount,  eb_rec.q2_amount,  eb_rec.q3_amount,  eb_rec.q4_amount)  if eb_rec  else _zero_amounts()
        ask_a   = _make_scenario_amounts(ea_ask.q1_amount,  ea_ask.q2_amount,  ea_ask.q3_amount,  ea_ask.q4_amount)  if ea_ask  else _zero_amounts()
        ask_b   = _make_scenario_amounts(eb_ask.q1_amount,  eb_ask.q2_amount,  eb_ask.q3_amount,  eb_ask.q4_amount)  if eb_ask  else _zero_amounts()

        total_a = ScenarioAmounts(q1=rec_a.q1+ask_a.q1, q2=rec_a.q2+ask_a.q2, q3=rec_a.q3+ask_a.q3, q4=rec_a.q4+ask_a.q4, annual=rec_a.annual+ask_a.annual)
        total_b = ScenarioAmounts(q1=rec_b.q1+ask_b.q1, q2=rec_b.q2+ask_b.q2, q3=rec_b.q3+ask_b.q3, q4=rec_b.q4+ask_b.q4, annual=rec_b.annual+ask_b.annual)

        departments.append(DeptCompareRow(
            department_name=dept,
            department_code=dept_code_map.get(dept),
            approved_rec_a=rec_a,   approved_rec_b=rec_b,   approved_rec_delta=_make_delta(rec_a, rec_b),
            additional_ask_a=ask_a, additional_ask_b=ask_b, additional_ask_delta=_make_delta(ask_a, ask_b),
            total_a=total_a,        total_b=total_b,         total_delta=_make_delta(total_a, total_b),
        ))

    # Grand totals
    totals = DeptCompareRow(
        department_name="__totals__",
        approved_rec_a=_sum_scenario_amounts([d.approved_rec_a for d in departments]),
        approved_rec_b=_sum_scenario_amounts([d.approved_rec_b for d in departments]),
        approved_rec_delta=_make_delta(
            _sum_scenario_amounts([d.approved_rec_a for d in departments]),
            _sum_scenario_amounts([d.approved_rec_b for d in departments]),
        ),
        additional_ask_a=_sum_scenario_amounts([d.additional_ask_a for d in departments]),
        additional_ask_b=_sum_scenario_amounts([d.additional_ask_b for d in departments]),
        additional_ask_delta=_make_delta(
            _sum_scenario_amounts([d.additional_ask_a for d in departments]),
            _sum_scenario_amounts([d.additional_ask_b for d in departments]),
        ),
        total_a=_sum_scenario_amounts([d.total_a for d in departments]),
        total_b=_sum_scenario_amounts([d.total_b for d in departments]),
        total_delta=_make_delta(
            _sum_scenario_amounts([d.total_a for d in departments]),
            _sum_scenario_amounts([d.total_b for d in departments]),
        ),
    )

    return ScenarioCompareOut(
        fiscal_year=fiscal_year,
        scenario_a=scenario_a,
        scenario_b=scenario_b,
        all_scenarios=all_scenarios,
        departments=departments,
        totals=totals,
    )
