from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func, distinct

from src.core.dependencies import get_db, require_any, require_biz_admin, require_write, get_current_user
from src.models.budget import (
    BudgetScenario, BudgetEntry, BudgetNcConfig, BudgetEntryAudit, BudgetScenarioAudit, BudgetNcConfigAudit,
    ControllableBudgetEntry, ControllableLineOverride, ControllableBudgetAudit,
)
from src.models.contract import Contract, ContractLine
from src.models.reference import ActivityId, AccountNumber, Department
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
    ControllableEntryUpsert, ControllableEntryOut, ControllableEntryStatusUpdate,
    ControllableLineOverrideUpsert, ControllableLineOverrideOut,
    ControllableLineDetail, ControllablePlanRow, ControllablePlanOut,
    CtrlActivityCompareRow, CtrlDeptCompareRow, CtrlCompareOut,
    BudgetReportRow, BudgetReportOut,
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

    # Distinct account groups per dept (using same filters as actuals)
    dept_account_groups: dict[str, list[str]] = {}
    if selected_elements:
        ag_conditions = [
            Spend.month_key >= py_start,
            Spend.month_key <= py_end,
            Spend.oracle_cost_element.in_(selected_elements),
        ]
        if selected_account_groups:
            ag_conditions.append(Spend.oracle_account_group.in_(selected_account_groups))
        if selected_account_sub_groups:
            ag_conditions.append(Spend.oracle_account_sub_group.in_(selected_account_sub_groups))
        ag_rows = db.execute(
            select(Spend.oracle_department_name, Spend.oracle_account_group)
            .where(*ag_conditions)
            .distinct()
            .order_by(Spend.oracle_department_name, Spend.oracle_account_group)
        ).all()
        for dept_name, ag in ag_rows:
            if ag:
                dept_account_groups.setdefault(dept_name, []).append(ag)

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
            account_groups=dept_account_groups.get(dept, []),
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
        # Copy NC entries (NON_CONTROLLABLE scenarios)
        nc_source_entries = db.execute(
            select(BudgetEntry).where(BudgetEntry.scenario_id == body.copy_from_scenario_id)
        ).scalars().all()
        for e in nc_source_entries:
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

        # Copy CONTROLLABLE entries from source scenario (reset status to DRAFT)
        ctrl_source_entries = db.query(ControllableBudgetEntry).filter(
            ControllableBudgetEntry.scenario_id == body.copy_from_scenario_id
        ).all()
        for e in ctrl_source_entries:
            db.add(ControllableBudgetEntry(
                scenario_id=scenario.id,
                fiscal_year=scenario.fiscal_year,
                activity_id=e.activity_id,
                entry_label=e.entry_label,
                entry_category=e.entry_category,
                q1_amount=e.q1_amount,
                q2_amount=e.q2_amount,
                q3_amount=e.q3_amount,
                q4_amount=e.q4_amount,
                notes=e.notes,
                status="DRAFT",
                created_by=current_user.email,
            ))
    elif body.budget_type == "CONTROLLABLE":
        # Seed one entry per activity_id that has contracts in this fiscal year
        activity_q = _compute_controllable_quarters(db, body.fiscal_year)
        for act_id, aq in activity_q.items():
            db.add(ControllableBudgetEntry(
                scenario_id=scenario.id,
                fiscal_year=scenario.fiscal_year,
                activity_id=act_id,
                entry_category="EXISTING",
                q1_amount=aq["q1"],
                q2_amount=aq["q2"],
                q3_amount=aq["q3"],
                q4_amount=aq["q4"],
                status="DRAFT",
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
    _AUDIT_COLS = """
        audit_id, entry_id, scenario_id, scenario_name, fiscal_year,
        department_name, entry_type, event_type, changed_by, changed_at,
        q1_old, q1_new, q2_old, q2_new, q3_old, q3_new, q4_old, q4_new,
        status_old, status_new, activity_id_old, activity_id_new,
        current_q1, current_q2, current_q3, current_q4, current_status
    """
    nc_rows = db.execute(
        sa_text(f"SELECT {_AUDIT_COLS} FROM v_budget_entry_audit WHERE fiscal_year = :fy"),
        {"fy": fiscal_year},
    ).mappings().all()
    ctrl_rows = db.execute(
        sa_text(f"SELECT {_AUDIT_COLS} FROM v_controllable_budget_audit WHERE fiscal_year = :fy"),
        {"fy": fiscal_year},
    ).mappings().all()

    merged = sorted(
        [dict(r) for r in nc_rows] + [dict(r) for r in ctrl_rows],
        key=lambda r: r["changed_at"],
        reverse=True,
    )
    for i, r in enumerate(merged):
        r["audit_id"] = i + 1

    row_list = [BudgetAuditReportRow(**r) for r in merged]

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


# ── Budget Report (combined NC + Controllable) ────────────────────────────────

@router.get("/reports/budget", response_model=BudgetReportOut)
def get_budget_report(
    fiscal_year: int = Query(...),
    scenario_nc_id: int | None = Query(None),
    scenario_ctrl_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_any),
):
    def _resolve(budget_type: str, explicit_id: int | None) -> BudgetScenario:
        if explicit_id is not None:
            s = db.get(BudgetScenario, explicit_id)
            if not s or s.budget_type != budget_type:
                raise HTTPException(status_code=404, detail=f"Scenario {explicit_id} not found")
            return s
        s = db.execute(
            select(BudgetScenario).where(
                BudgetScenario.fiscal_year == fiscal_year,
                BudgetScenario.budget_type == budget_type,
                BudgetScenario.is_baseline == True,
            )
        ).scalar_one_or_none()
        if not s:
            raise HTTPException(status_code=404, detail=f"No baseline {budget_type} scenario for FY{fiscal_year}")
        return s

    scenario_nc = _resolve("NON_CONTROLLABLE", scenario_nc_id)
    scenario_ctrl = _resolve("CONTROLLABLE", scenario_ctrl_id)

    rows: list[BudgetReportRow] = []

    # NC rows — enrich from ActivityId → AccountNumber using activity_id on the entry
    nc_entries = db.execute(
        select(BudgetEntry).where(BudgetEntry.scenario_id == scenario_nc.id)
    ).scalars().all()

    nc_act_ids = {e.activity_id for e in nc_entries if e.activity_id}
    nc_activity_meta: dict[str, dict] = {}
    if nc_act_ids:
        for ai, an in (
            db.query(ActivityId, AccountNumber)
            .outerjoin(AccountNumber, ActivityId.account_id == AccountNumber.id)
            .filter(ActivityId.activity_id.in_(nc_act_ids))
            .all()
        ):
            nc_activity_meta[ai.activity_id] = {
                "cost_element":      an.cost_element      if an else None,
                "account_group":     an.account_group     if an else None,
                "account_sub_group": an.account_sub_group if an else None,
                "account_number":    an.account_number    if an else None,
            }

    for e in nc_entries:
        meta = nc_activity_meta.get(e.activity_id, {}) if e.activity_id else {}
        rows.append(BudgetReportRow(
            source="NC",
            department_name=e.department_name,
            entry_type=e.entry_type,
            expense_type=e.expense_type,
            cost_element=meta.get("cost_element"),
            account_group=meta.get("account_group"),
            account_sub_group=meta.get("account_sub_group"),
            account_number=meta.get("account_number"),
            activity_id=e.activity_id,
            q1_amount=e.q1_amount or Decimal("0"),
            q2_amount=e.q2_amount or Decimal("0"),
            q3_amount=e.q3_amount or Decimal("0"),
            q4_amount=e.q4_amount or Decimal("0"),
        ))

    # CTRL rows — enrich from ActivityId → AccountNumber → Department
    ctrl_entries = db.execute(
        select(ControllableBudgetEntry).where(ControllableBudgetEntry.scenario_id == scenario_ctrl.id)
    ).scalars().all()

    act_ids = {e.activity_id for e in ctrl_entries if e.activity_id}
    activity_meta: dict[str, dict] = {}
    if act_ids:
        for ai, an, dept in (
            db.query(ActivityId, AccountNumber, Department)
            .outerjoin(AccountNumber, ActivityId.account_id == AccountNumber.id)
            .outerjoin(Department, ActivityId.department_code == Department.department_code)
            .filter(ActivityId.activity_id.in_(act_ids))
            .all()
        ):
            activity_meta[ai.activity_id] = {
                "department_name": dept.department_name if dept else None,
                "account_group":    an.account_group    if an else None,
                "account_sub_group": an.account_sub_group if an else None,
                "cost_element":     an.cost_element     if an else None,
                "account_number":   an.account_number   if an else None,
            }

    for e in ctrl_entries:
        meta = activity_meta.get(e.activity_id, {}) if e.activity_id else {}
        rows.append(BudgetReportRow(
            source="CTRL",
            department_name=e.department_name or meta.get("department_name"),
            expense_type=e.expense_type,
            cost_element=e.cost_element or meta.get("cost_element"),
            account_group=e.account_group or meta.get("account_group"),
            account_sub_group=e.account_sub_group or meta.get("account_sub_group"),
            account_number=meta.get("account_number"),
            activity_id=e.activity_id,
            entry_type=e.entry_category,
            q1_amount=e.q1_amount or Decimal("0"),
            q2_amount=e.q2_amount or Decimal("0"),
            q3_amount=e.q3_amount or Decimal("0"),
            q4_amount=e.q4_amount or Decimal("0"),
        ))

    return BudgetReportOut(
        fiscal_year=fiscal_year,
        scenario_nc=BudgetScenarioOut.model_validate(scenario_nc),
        scenario_ctrl=BudgetScenarioOut.model_validate(scenario_ctrl),
        rows=rows,
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


@router.get("/controllable/compare", response_model=CtrlCompareOut)
def compare_controllable_scenarios(
    fiscal_year: int = Query(...),
    scenario_a_id: int = Query(...),
    scenario_b_id: int = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_any),
):
    scenario_a = db.get(BudgetScenario, scenario_a_id)
    scenario_b = db.get(BudgetScenario, scenario_b_id)
    if not scenario_a or scenario_a.budget_type != "CONTROLLABLE":
        raise HTTPException(status_code=404, detail="Scenario A not found")
    if not scenario_b or scenario_b.budget_type != "CONTROLLABLE":
        raise HTTPException(status_code=404, detail="Scenario B not found")

    entries_a = db.execute(
        select(ControllableBudgetEntry).where(ControllableBudgetEntry.scenario_id == scenario_a_id)
    ).scalars().all()
    entries_b = db.execute(
        select(ControllableBudgetEntry).where(ControllableBudgetEntry.scenario_id == scenario_b_id)
    ).scalars().all()

    # Look up activity metadata for EXISTING entries (department, account group)
    all_act_ids = {e.activity_id for e in (entries_a + entries_b) if e.activity_id}
    activity_meta: dict[str, dict] = {}
    if all_act_ids:
        for ai, an, dept in (
            db.query(ActivityId, AccountNumber, Department)
            .outerjoin(AccountNumber, ActivityId.account_id == AccountNumber.id)
            .outerjoin(Department, ActivityId.department_code == Department.department_code)
            .filter(ActivityId.activity_id.in_(all_act_ids))
            .all()
        ):
            activity_meta[ai.activity_id] = {
                "department_name": dept.department_name if dept else None,
                "account_group": an.account_group if an else None,
                "account_sub_group": an.account_sub_group if an else None,
            }

    def _entry_key(e: ControllableBudgetEntry):
        return ("EXISTING", e.activity_id) if e.entry_category == "EXISTING" else ("NEW_REQUEST", e.entry_label)

    def _dept_for(e: ControllableBudgetEntry) -> str:
        if e.activity_id:
            return activity_meta.get(e.activity_id, {}).get("department_name") or e.department_name or "—"
        return e.department_name or "—"

    def _expense_type(e: ControllableBudgetEntry) -> str:
        if e.activity_id and e.activity_id.startswith("ACAPEX-"):
            return "capex"
        return e.expense_type or "opex"

    map_a = {_entry_key(e): e for e in entries_a}
    map_b = {_entry_key(e): e for e in entries_b}
    all_keys = sorted(set(map_a) | set(map_b), key=lambda k: (k[0], k[1] or ""))

    dept_groups: dict[str, list[CtrlActivityCompareRow]] = {}
    for key in all_keys:
        ea = map_a.get(key)
        eb = map_b.get(key)
        ref = ea or eb
        dept = _dept_for(ref)
        meta = activity_meta.get(ref.activity_id, {}) if ref.activity_id else {}
        ba = _make_scenario_amounts(ea.q1_amount, ea.q2_amount, ea.q3_amount, ea.q4_amount) if ea else _zero_amounts()
        bb = _make_scenario_amounts(eb.q1_amount, eb.q2_amount, eb.q3_amount, eb.q4_amount) if eb else _zero_amounts()
        dept_groups.setdefault(dept, []).append(CtrlActivityCompareRow(
            activity_id=ref.activity_id,
            entry_label=ref.entry_label,
            entry_category=ref.entry_category,
            account_group=meta.get("account_group") or ref.account_group,
            account_sub_group=meta.get("account_sub_group") or ref.account_sub_group,
            expense_type=_expense_type(ref),
            budget_a=ba,
            budget_b=bb,
            budget_delta=_make_delta(ba, bb),
        ))

    departments: list[CtrlDeptCompareRow] = []
    for dept_name in sorted(dept_groups):
        rows = dept_groups[dept_name]
        ta = _sum_scenario_amounts([r.budget_a for r in rows])
        tb = _sum_scenario_amounts([r.budget_b for r in rows])
        departments.append(CtrlDeptCompareRow(
            department_name=dept_name,
            rows=rows,
            total_a=ta,
            total_b=tb,
            total_delta=_make_delta(ta, tb),
        ))

    totals_a = _sum_scenario_amounts([d.total_a for d in departments])
    totals_b = _sum_scenario_amounts([d.total_b for d in departments])
    return CtrlCompareOut(
        fiscal_year=fiscal_year,
        scenario_a=scenario_a,
        scenario_b=scenario_b,
        departments=departments,
        totals_a=totals_a,
        totals_b=totals_b,
        totals_delta=_make_delta(totals_a, totals_b),
    )


# ── Controllable Budget ───────────────────────────────────────────────────────

def _fy_months_in_period(fiscal_year: int, period_start, period_end) -> list[int]:
    """Return month numbers (1-12) within fiscal_year that overlap [period_start, period_end]."""
    from datetime import date as date_type
    fy_start = date_type(fiscal_year, 1, 1)
    fy_end = date_type(fiscal_year, 12, 31)

    overlap_start = max(period_start, fy_start)
    overlap_end = min(period_end, fy_end)
    if overlap_start > overlap_end:
        return []

    months = []
    year, month = overlap_start.year, overlap_start.month
    while (year, month) <= (overlap_end.year, overlap_end.month):
        if year == fiscal_year:
            months.append(month)
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def _compute_controllable_quarters(db: Session, fiscal_year: int) -> dict[str, dict[str, Decimal]]:
    """Return {activity_id: {q1, q2, q3, q4}} summed from active/pending contract lines for this FY."""
    from datetime import date as _date
    fy_start = _date(fiscal_year, 1, 1)
    fy_end   = _date(fiscal_year, 12, 31)
    lines_q = (
        db.query(ContractLine, Contract)
        .join(Contract, ContractLine.contract_id == Contract.id)
        .filter(
            ContractLine.activity_id.isnot(None),
            ContractLine.period_end >= fy_start,
            ContractLine.period_start <= fy_end,
            Contract.status.in_(["active", "pending"]),
        )
        .all()
    )
    activity_q: dict[str, dict[str, Decimal]] = {}
    for cl, _ in lines_q:
        months = _fy_months_in_period(fiscal_year, cl.period_start, cl.period_end)
        if not months:
            continue
        aq = activity_q.setdefault(cl.activity_id, {"q1": Decimal("0"), "q2": Decimal("0"), "q3": Decimal("0"), "q4": Decimal("0")})
        for m in months:
            aq[_quarter_for_month(m)] += cl.monthly_amount
    return activity_q


def _quarter_for_month(month: int) -> str:
    if month <= 3:
        return "q1"
    if month <= 6:
        return "q2"
    if month <= 9:
        return "q3"
    return "q4"


def _serialize_ctrl(val) -> str:
    if val is None:
        return "null"
    return str(Decimal(str(val)).quantize(Decimal("0.01")))


@router.get("/controllable", response_model=ControllablePlanOut)
def get_controllable_plan(
    fiscal_year: int = Query(...),
    scenario_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scenario = db.get(BudgetScenario, scenario_id)
    if not scenario or scenario.fiscal_year != fiscal_year or scenario.budget_type != "CONTROLLABLE":
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Load nc_config to get actuals_cutoff_month_key (shared with NC page)
    nc_cfg = db.query(BudgetNcConfig).filter(BudgetNcConfig.fiscal_year == fiscal_year).first()
    cutoff = nc_cfg.actuals_cutoff_month_key if nc_cfg else None

    # Load all contract lines with activity_id, whose period overlaps the fiscal year
    from datetime import date as date_type
    fy_start = date_type(fiscal_year, 1, 1)
    fy_end = date_type(fiscal_year, 12, 31)

    lines_q = (
        db.query(ContractLine, Contract)
        .join(Contract, ContractLine.contract_id == Contract.id)
        .filter(
            ContractLine.activity_id.isnot(None),
            ContractLine.period_end >= fy_start,
            ContractLine.period_start <= fy_end,
            Contract.status.in_(["active", "pending"]),
        )
        .all()
    )

    # Load overrides for this scenario
    overrides_q = db.query(ControllableLineOverride).filter(
        ControllableLineOverride.scenario_id == scenario_id
    ).all()
    override_map: dict[int, ControllableLineOverride] = {o.contract_line_id: o for o in overrides_q}

    # Build activity_id → enriched metadata from activity_ids + account_numbers + departments
    activity_ids_set = {line.activity_id for line, _ in lines_q}
    activity_rows = (
        db.query(ActivityId, AccountNumber, Department)
        .outerjoin(AccountNumber, ActivityId.account_id == AccountNumber.id)
        .outerjoin(Department, ActivityId.department_code == Department.department_code)
        .filter(ActivityId.activity_id.in_(activity_ids_set))
        .all()
    ) if activity_ids_set else []
    activity_meta: dict[str, dict] = {}
    for ai, an, dept in activity_rows:
        activity_meta[ai.activity_id] = {
            "department_name": dept.department_name if dept else None,
            "account_group": an.account_group if an else None,
            "account_sub_group": an.account_sub_group if an else None,
            "cost_element": an.cost_element if an else None,
        }

    # Group contract lines by activity_id; compute quarterly FY contributions per line
    activity_lines: dict[str, list[ControllableLineDetail]] = {}
    activity_q: dict[str, dict[str, Decimal]] = {}   # plan amounts (override-adjusted)
    activity_cf: dict[str, Decimal] = {}              # raw contracted total (never affected by overrides)

    for cl, contract in lines_q:
        fy_months = _fy_months_in_period(fiscal_year, cl.period_start, cl.period_end)
        if not fy_months:
            continue
        fy_count = len(fy_months)
        override = override_map.get(cl.id)
        action = override.action if override else "keep"

        # Aggregate contracted amounts into quarterly buckets
        contracted_q = {"q1": Decimal("0"), "q2": Decimal("0"), "q3": Decimal("0"), "q4": Decimal("0")}
        for month in fy_months:
            q = _quarter_for_month(month)
            contracted_q[q] += cl.monthly_amount

        if action == "cancel":
            line_q = {"q1": Decimal("0"), "q2": Decimal("0"), "q3": Decimal("0"), "q4": Decimal("0")}
        elif action == "extend":
            line_q = {
                "q1": override.q1_extended or Decimal("0"),
                "q2": override.q2_extended or Decimal("0"),
                "q3": override.q3_extended or Decimal("0"),
                "q4": override.q4_extended or Decimal("0"),
            }
        else:
            line_q = contracted_q

        contribution = sum(line_q.values())
        detail = ControllableLineDetail(
            contract_line_id=cl.id,
            contract_id=contract.id,
            vendor_name=contract.vendor_name,
            po_number=contract.purchase_order_number,
            po_line_number=cl.po_line_number,
            period_start=cl.period_start.isoformat(),
            period_end=cl.period_end.isoformat(),
            monthly_amount=cl.monthly_amount,
            fy_months_count=fy_count,
            fy_contribution=contribution,
            q1_contribution=line_q["q1"],
            q2_contribution=line_q["q2"],
            q3_contribution=line_q["q3"],
            q4_contribution=line_q["q4"],
            override_action=action,
            q1_extended=override.q1_extended if override else None,
            q2_extended=override.q2_extended if override else None,
            q3_extended=override.q3_extended if override else None,
            q4_extended=override.q4_extended if override else None,
        )
        activity_lines.setdefault(cl.activity_id, []).append(detail)
        aq = activity_q.setdefault(cl.activity_id, {"q1": Decimal("0"), "q2": Decimal("0"), "q3": Decimal("0"), "q4": Decimal("0")})
        for q in ("q1", "q2", "q3", "q4"):
            aq[q] += line_q[q]
        # C+F always uses raw contracted amounts regardless of override action
        activity_cf[cl.activity_id] = activity_cf.get(cl.activity_id, Decimal("0")) + sum(contracted_q.values())

    # Load controllable budget entries for this scenario
    entries_q = db.query(ControllableBudgetEntry).filter(
        ControllableBudgetEntry.scenario_id == scenario_id
    ).all()
    entry_map: dict[str | None, ControllableBudgetEntry] = {}
    new_request_entries: list[ControllableBudgetEntry] = []
    for e in entries_q:
        if e.entry_category == "NEW_REQUEST":
            new_request_entries.append(e)
        else:
            entry_map[e.activity_id] = e

    # Build plan rows for activity_ids that appear in contracts
    # Keep entries in sync when contracted amounts change (e.g. after a line override,
    # or for new contracts added after scenario creation).
    needs_commit = False
    for act_id, aq in activity_q.items():
        entry = entry_map.get(act_id)
        if entry is None:
            # Contract added after scenario was created — create entry now
            new_e = ControllableBudgetEntry(
                scenario_id=scenario_id,
                fiscal_year=fiscal_year,
                activity_id=act_id,
                entry_category="EXISTING",
                q1_amount=aq["q1"],
                q2_amount=aq["q2"],
                q3_amount=aq["q3"],
                q4_amount=aq["q4"],
                status="DRAFT",
                created_by=current_user.email,
            )
            db.add(new_e)
            entry_map[act_id] = new_e
            needs_commit = True
        elif (entry.q1_amount != aq["q1"] or entry.q2_amount != aq["q2"] or
              entry.q3_amount != aq["q3"] or entry.q4_amount != aq["q4"]):
            entry.q1_amount = aq["q1"]
            entry.q2_amount = aq["q2"]
            entry.q3_amount = aq["q3"]
            entry.q4_amount = aq["q4"]
            needs_commit = True
    if needs_commit:
        db.flush()
        db.commit()

    # Reload entry map to capture any newly created entries
    all_entries = db.query(ControllableBudgetEntry).filter(
        ControllableBudgetEntry.scenario_id == scenario_id,
        ControllableBudgetEntry.entry_category == "EXISTING",
    ).all()
    entry_map = {e.activity_id: e for e in all_entries}

    rows = []
    for act_id in sorted(activity_q.keys()):
        entry = entry_map.get(act_id)
        meta = activity_meta.get(act_id, {})
        aq = activity_q[act_id]
        rows.append(ControllablePlanRow(
            activity_id=act_id,
            entry_label=None,
            entry_category="EXISTING",
            department_name=meta.get("department_name"),
            account_group=meta.get("account_group"),
            account_sub_group=meta.get("account_sub_group"),
            cost_element=meta.get("cost_element"),
            q1_contracted=aq["q1"],
            q2_contracted=aq["q2"],
            q3_contracted=aq["q3"],
            q4_contracted=aq["q4"],
            current_and_forecast=activity_cf.get(act_id, Decimal("0")),
            q1_amount=entry.q1_amount if entry else None,
            q2_amount=entry.q2_amount if entry else None,
            q3_amount=entry.q3_amount if entry else None,
            q4_amount=entry.q4_amount if entry else None,
            total_budget=aq["q1"] + aq["q2"] + aq["q3"] + aq["q4"],
            entry_id=entry.id if entry else None,
            status=entry.status if entry else None,
            lines=activity_lines.get(act_id, []),
        ))

    # Append NEW_REQUEST entries
    for e in new_request_entries:
        q1, q2, q3, q4 = e.q1_amount, e.q2_amount, e.q3_amount, e.q4_amount
        total = (q1 or Decimal("0")) + (q2 or Decimal("0")) + (q3 or Decimal("0")) + (q4 or Decimal("0"))
        rows.append(ControllablePlanRow(
            activity_id=e.activity_id,
            entry_label=e.entry_label,
            entry_category="NEW_REQUEST",
            department_name=e.department_name,
            account_group=e.account_group,
            account_sub_group=e.account_sub_group,
            cost_element=e.cost_element,
            expense_type=e.expense_type,
            q1_contracted=Decimal("0"),
            q2_contracted=Decimal("0"),
            q3_contracted=Decimal("0"),
            q4_contracted=Decimal("0"),
            current_and_forecast=Decimal("0"),
            q1_amount=q1,
            q2_amount=q2,
            q3_amount=q3,
            q4_amount=q4,
            total_budget=total,
            entry_id=e.id,
            status=e.status,
            lines=[],
        ))

    return ControllablePlanOut(
        fiscal_year=fiscal_year,
        scenario_id=scenario_id,
        actuals_cutoff_month_key=cutoff,
        rows=rows,
    )


@router.put("/controllable/entries", response_model=ControllableEntryOut)
def upsert_controllable_entry(
    body: ControllableEntryUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write),
):
    scenario = db.get(BudgetScenario, body.scenario_id)
    if not scenario or scenario.budget_type != "CONTROLLABLE":
        raise HTTPException(status_code=404, detail="Scenario not found")

    if body.entry_id:
        existing = db.get(ControllableBudgetEntry, body.entry_id)
        if existing and existing.scenario_id != body.scenario_id:
            raise HTTPException(status_code=403, detail="Entry does not belong to this scenario")
    elif body.entry_category == "EXISTING" and body.activity_id:
        existing = db.query(ControllableBudgetEntry).filter(
            ControllableBudgetEntry.scenario_id == body.scenario_id,
            ControllableBudgetEntry.activity_id == body.activity_id,
            ControllableBudgetEntry.entry_category == "EXISTING",
        ).first()
    else:
        existing = None

    if existing:
        # Allow linking an activity_id to a FINAL entry (post-approval assignment);
        # block all other edits on FINAL entries
        if existing.status == "FINAL" and body.activity_id is None:
            raise HTTPException(status_code=403, detail="Cannot edit a FINAL entry")
        old_activity_id = existing.activity_id
        old_amounts = {
            "q1_amount": _serialize_ctrl(existing.q1_amount),
            "q2_amount": _serialize_ctrl(existing.q2_amount),
            "q3_amount": _serialize_ctrl(existing.q3_amount),
            "q4_amount": _serialize_ctrl(existing.q4_amount),
        }
        if body.activity_id is not None:
            existing.activity_id = body.activity_id
        existing.department_name = body.department_name
        existing.account_group = body.account_group
        existing.account_sub_group = body.account_sub_group
        existing.cost_element = body.cost_element
        existing.expense_type = body.expense_type
        existing.q1_amount = body.q1_amount
        existing.q2_amount = body.q2_amount
        existing.q3_amount = body.q3_amount
        existing.q4_amount = body.q4_amount
        existing.notes = body.notes
        db.flush()
        new_amounts = {
            "q1_amount": _serialize_ctrl(body.q1_amount),
            "q2_amount": _serialize_ctrl(body.q2_amount),
            "q3_amount": _serialize_ctrl(body.q3_amount),
            "q4_amount": _serialize_ctrl(body.q4_amount),
        }
        changes = {k: {"old": old_amounts[k], "new": new_amounts[k]}
                   for k in old_amounts if old_amounts[k] != new_amounts[k]}
        if body.activity_id is not None and body.activity_id != old_activity_id:
            changes["activity_id"] = {"old": old_activity_id, "new": body.activity_id}
        if changes:
            db.add(ControllableBudgetAudit(
                entry_id=existing.id,
                scenario_id=body.scenario_id,
                activity_id=existing.activity_id,
                entry_label=existing.entry_label,
                entry_category=existing.entry_category,
                event_type="UPDATED",
                changes=changes,
                changed_by=current_user.email,
            ))
        db.commit()
        db.refresh(existing)
        return existing

    entry = ControllableBudgetEntry(
        scenario_id=body.scenario_id,
        fiscal_year=body.fiscal_year,
        activity_id=body.activity_id,
        entry_label=body.entry_label,
        entry_category=body.entry_category,
        department_name=body.department_name,
        account_group=body.account_group,
        account_sub_group=body.account_sub_group,
        cost_element=body.cost_element,
        expense_type=body.expense_type,
        q1_amount=body.q1_amount,
        q2_amount=body.q2_amount,
        q3_amount=body.q3_amount,
        q4_amount=body.q4_amount,
        notes=body.notes,
        status="DRAFT",
        created_by=current_user.email,
    )
    db.add(entry)
    db.flush()
    db.add(ControllableBudgetAudit(
        entry_id=entry.id,
        scenario_id=body.scenario_id,
        activity_id=body.activity_id,
        entry_label=body.entry_label,
        entry_category=body.entry_category,
        event_type="CREATED",
        changes={},
        changed_by=current_user.email,
    ))
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/controllable/entries/{entry_id}", status_code=204)
def delete_controllable_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write),
):
    entry = db.get(ControllableBudgetEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    if entry.status == "FINAL":
        raise HTTPException(status_code=403, detail="Cannot delete a FINAL entry")
    db.add(ControllableBudgetAudit(
        entry_id=entry.id,
        scenario_id=entry.scenario_id,
        activity_id=entry.activity_id,
        entry_label=entry.entry_label,
        entry_category=entry.entry_category,
        event_type="DELETED",
        changes={},
        changed_by=current_user.email,
    ))
    db.delete(entry)
    db.commit()


@router.patch("/controllable/entries/{entry_id}/status", response_model=ControllableEntryOut)
def update_controllable_entry_status(
    entry_id: int,
    body: ControllableEntryStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write),
):
    entry = db.get(ControllableBudgetEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    key = (entry.status, body.status)
    allowed_roles = ALLOWED_TRANSITIONS.get(key, [])
    if current_user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail=f"Transition {entry.status} → {body.status} not allowed for your role")

    old_status = entry.status
    entry.status = body.status
    db.add(ControllableBudgetAudit(
        entry_id=entry.id,
        scenario_id=entry.scenario_id,
        activity_id=entry.activity_id,
        entry_label=entry.entry_label,
        entry_category=entry.entry_category,
        event_type="STATUS_CHANGED",
        changes={"status": {"old": old_status, "new": body.status}},
        changed_by=current_user.email,
    ))
    db.commit()
    db.refresh(entry)
    return entry


@router.put("/controllable/line-overrides", response_model=ControllableLineOverrideOut)
def upsert_line_override(
    body: ControllableLineOverrideUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write),
):
    if body.action not in ("keep", "cancel", "extend"):
        raise HTTPException(status_code=422, detail="action must be keep, cancel, or extend")

    contract_line = db.get(ContractLine, body.contract_line_id)
    if not contract_line:
        raise HTTPException(status_code=404, detail="Contract line not found")

    existing = db.query(ControllableLineOverride).filter(
        ControllableLineOverride.scenario_id == body.scenario_id,
        ControllableLineOverride.contract_line_id == body.contract_line_id,
    ).first()

    old_q = {
        "q1_amount": _serialize_ctrl(existing.q1_extended if existing else None),
        "q2_amount": _serialize_ctrl(existing.q2_extended if existing else None),
        "q3_amount": _serialize_ctrl(existing.q3_extended if existing else None),
        "q4_amount": _serialize_ctrl(existing.q4_extended if existing else None),
    }

    if existing:
        existing.action = body.action
        existing.q1_extended = body.q1_extended
        existing.q2_extended = body.q2_extended
        existing.q3_extended = body.q3_extended
        existing.q4_extended = body.q4_extended
        db.flush()
    else:
        override = ControllableLineOverride(
            scenario_id=body.scenario_id,
            contract_line_id=body.contract_line_id,
            action=body.action,
            q1_extended=body.q1_extended,
            q2_extended=body.q2_extended,
            q3_extended=body.q3_extended,
            q4_extended=body.q4_extended,
            created_by=current_user.email,
        )
        db.add(override)
        db.flush()
        existing = override

    new_q = {
        "q1_amount": _serialize_ctrl(body.q1_extended),
        "q2_amount": _serialize_ctrl(body.q2_extended),
        "q3_amount": _serialize_ctrl(body.q3_extended),
        "q4_amount": _serialize_ctrl(body.q4_extended),
    }
    changes = {k: {"old": old_q[k], "new": new_q[k]} for k in old_q if old_q[k] != new_q[k]}
    if changes:
        entry = db.query(ControllableBudgetEntry).filter(
            ControllableBudgetEntry.scenario_id == body.scenario_id,
            ControllableBudgetEntry.activity_id == contract_line.activity_id,
            ControllableBudgetEntry.entry_category == "EXISTING",
        ).first()
        db.add(ControllableBudgetAudit(
            entry_id=entry.id if entry else None,
            scenario_id=body.scenario_id,
            activity_id=contract_line.activity_id,
            entry_label=None,
            entry_category="EXISTING",
            event_type="AMOUNT_CHANGED",
            changes=changes,
            changed_by=current_user.email,
        ))

    db.commit()
    db.refresh(existing)
    return existing
