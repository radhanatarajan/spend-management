import random
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import select, func, text

from src.db.base import Base
from src.db.session import engine, SessionLocal
from src.models import spend as _spend_module     # noqa: F401 — registers Spend with Base.metadata
from src.models import user as _user_module       # noqa: F401 — registers User with Base.metadata
from src.models import contract as _contract_module  # noqa: F401 — registers Contract/ContractLine with Base.metadata
from src.models import budget as _budget_module   # noqa: F401 — registers BudgetScenario/BudgetEntry/BudgetNcConfig with Base.metadata


EXPENSE_TYPES = ["Capex", "Opex", "Travel", "Professional Services", "Marketing"]
COMPANY_CODES = ["1000", "2000", "3000", "4000"]
ORACLE_ORGS = ["US01", "US02", "EMEA", "APAC", "LATAM", "CANADA"]
ORACLE_DEPTS = [
    ("1100", "Engineering"),
    ("1200", "Sales"),
    ("1300", "Finance"),
    ("1400", "Marketing"),
    ("1500", "Operations"),
    ("1600", "HR"),
    ("1700", "Legal"),
    ("1800", "IT"),
]
COST_CENTER_HIERARCHIES = [
    "Americas > US > West",
    "Americas > US > East",
    "EMEA > UK",
    "EMEA > Germany",
    "APAC > Singapore",
    "APAC > Japan",
]
ACCOUNT_GROUPS = ["COGS", "R&D", "S&M", "G&A", "Infrastructure", "Facilities"]
ACCOUNT_SUB_GROUPS = {
    "COGS": ["Direct Costs", "Indirect Costs"],
    "R&D": ["Engineering Salaries", "Software Licenses", "Cloud Infra"],
    "S&M": ["Salaries", "Advertising", "Events"],
    "G&A": ["Executive", "Finance Ops", "Legal Ops"],
    "Infrastructure": ["AWS", "GCP", "Azure"],
    "Facilities": ["Rent", "Utilities", "Office Supplies"],
}
COST_ELEMENTS = ["Salaries", "Licenses", "Consulting", "Travel", "Hardware", "Hosting", "Office"]
VENDORS = [
    "Amazon Web Services",
    "Salesforce",
    "Zoom Video Communications",
    "Slack Technologies",
    "Stripe",
    "HubSpot",
    "Notion Labs",
    "Figma",
]
JE_SOURCES = ["Manual", "Coupa", "Concur", "Workday", "Oracle", None]
LINE_DESCS = [
    "Monthly SaaS subscription",
    "Professional services - Q1",
    "Cloud infrastructure usage",
    "Software license renewal",
    "Travel reimbursement",
    "Contractor invoice",
    "Marketing campaign spend",
    "Hardware purchase",
    None,
]


def _month_label(month_key: int) -> str:
    year = month_key // 100
    month = month_key % 100
    return datetime(year, month, 1).strftime("%b %Y")


def _last_n_months(n: int) -> list[int]:
    now = datetime.utcnow()
    keys = []
    year, month = now.year, now.month
    for _ in range(n):
        keys.append(year * 100 + month)
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return keys


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_contract_lines()
    _migrate_budget_nc_config()
    _migrate_budget_scenario_status()
    _migrate_budget_audit_view()
    _migrate_spend_activity_id()
    _seed_db()
    _seed_users()
    _seed_contracts()
    _seed_budget()


def _migrate_budget_scenario_status() -> None:
    """Add status to budget_entries and event_type/changes to budget_entry_audit if missing.
    Also drops legacy wide-column audit fields if they still exist."""
    with engine.connect() as conn:
        for table, col, ddl in [
            ("budget_entries",    "status",     "ENUM('DRAFT','READY_FOR_REVIEW','APPROVED','FINAL','CANCELLED') NOT NULL DEFAULT 'DRAFT'"),
            ("budget_entry_audit","event_type", "VARCHAR(50) NOT NULL DEFAULT 'AMOUNT_CHANGED'"),
            ("budget_entry_audit","changes",    "JSON NOT NULL DEFAULT ('{}')"),
        ]:
            table_exists = conn.execute(text(
                "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t"
            ), {"t": table}).scalar()
            if not table_exists:
                continue
            existing = {
                row[0] for row in conn.execute(text(
                    "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t"
                ), {"t": table})
            }
            if col not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))

        # Drop legacy wide-column fields from original audit design
        legacy_cols = ["old_q1", "old_q2", "old_q3", "old_q4",
                       "new_q1", "new_q2", "new_q3", "new_q4",
                       "old_status", "new_status"]
        audit_cols = {
            row[0] for row in conn.execute(text(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'budget_entry_audit'"
            ))
        }
        for col in legacy_cols:
            if col in audit_cols:
                conn.execute(text(f"ALTER TABLE budget_entry_audit DROP COLUMN {col}"))

        conn.commit()


def _migrate_budget_nc_config() -> None:
    """Add actuals_cutoff_month_key column to budget_nc_config if missing (idempotent, MySQL-compatible)."""
    with engine.connect() as conn:
        table_exists = conn.execute(text(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'budget_nc_config'"
        )).scalar()
        if not table_exists:
            return

        existing = {
            row[0] for row in conn.execute(text(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'budget_nc_config'"
            ))
        }

        if "actuals_cutoff_month_key" not in existing:
            conn.execute(text(
                "ALTER TABLE budget_nc_config ADD COLUMN actuals_cutoff_month_key INT NULL"
            ))
            conn.commit()


def _migrate_budget_audit_view() -> None:
    """Create or replace v_budget_entry_audit — joins budget_entries + budget_scenarios
    + budget_entry_audit and unpacks the changes JSON into named old/new columns."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE OR REPLACE VIEW v_budget_entry_audit AS
            SELECT
                bea.id                                                                    AS audit_id,
                be.id                                                                     AS entry_id,
                bs.id                                                                     AS scenario_id,
                bs.name                                                                   AS scenario_name,
                bs.fiscal_year,
                be.department_name,
                be.entry_type,
                bea.event_type,
                bea.changed_by,
                bea.changed_at,

                -- Amount changes (NULL when that field was not part of this event)
                CAST(JSON_UNQUOTE(JSON_EXTRACT(bea.changes, '$.q1_amount.old')) AS DECIMAL(14,2)) AS q1_old,
                CAST(JSON_UNQUOTE(JSON_EXTRACT(bea.changes, '$.q1_amount.new')) AS DECIMAL(14,2)) AS q1_new,
                CAST(JSON_UNQUOTE(JSON_EXTRACT(bea.changes, '$.q2_amount.old')) AS DECIMAL(14,2)) AS q2_old,
                CAST(JSON_UNQUOTE(JSON_EXTRACT(bea.changes, '$.q2_amount.new')) AS DECIMAL(14,2)) AS q2_new,
                CAST(JSON_UNQUOTE(JSON_EXTRACT(bea.changes, '$.q3_amount.old')) AS DECIMAL(14,2)) AS q3_old,
                CAST(JSON_UNQUOTE(JSON_EXTRACT(bea.changes, '$.q3_amount.new')) AS DECIMAL(14,2)) AS q3_new,
                CAST(JSON_UNQUOTE(JSON_EXTRACT(bea.changes, '$.q4_amount.old')) AS DECIMAL(14,2)) AS q4_old,
                CAST(JSON_UNQUOTE(JSON_EXTRACT(bea.changes, '$.q4_amount.new')) AS DECIMAL(14,2)) AS q4_new,

                -- Status change (NULL when this event did not touch status)
                JSON_UNQUOTE(JSON_EXTRACT(bea.changes, '$.status.old'))                  AS status_old,
                JSON_UNQUOTE(JSON_EXTRACT(bea.changes, '$.status.new'))                  AS status_new,

                -- Current live state of the entry for reference
                be.q1_amount                                                              AS current_q1,
                be.q2_amount                                                              AS current_q2,
                be.q3_amount                                                              AS current_q3,
                be.q4_amount                                                              AS current_q4,
                be.status                                                                 AS current_status
            FROM budget_entry_audit bea
            JOIN budget_entries be   ON be.id  = bea.entry_id
            JOIN budget_scenarios bs ON bs.id  = be.scenario_id
            ORDER BY bea.changed_at DESC
        """))
        conn.commit()


def _migrate_spend_activity_id() -> None:
    """Add activity_id column to spend table if missing (idempotent, MySQL-compatible)."""
    with engine.connect() as conn:
        table_exists = conn.execute(text(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'spend'"
        )).scalar()
        if not table_exists:
            return

        existing = {
            row[0] for row in conn.execute(text(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'spend'"
            ))
        }

        if "activity_id" not in existing:
            conn.execute(text("ALTER TABLE spend ADD COLUMN activity_id VARCHAR(20) NULL"))
            conn.execute(text("ALTER TABLE spend ADD INDEX ix_spend_activity_id (activity_id)"))
            conn.commit()


def _migrate_contract_lines() -> None:
    """Add billing_interval and entered_amount columns if missing (idempotent, MySQL-compatible)."""
    with engine.connect() as conn:
        # No-op if table doesn't exist yet — create_all will build it with all columns
        table_exists = conn.execute(text(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'contract_lines'"
        )).scalar()
        if not table_exists:
            return

        existing = {
            row[0] for row in conn.execute(text(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'contract_lines'"
            ))
        }

        if "billing_interval" not in existing:
            conn.execute(text(
                "ALTER TABLE contract_lines ADD COLUMN billing_interval "
                "ENUM('monthly','quarterly','yearly','custom') NOT NULL DEFAULT 'monthly'"
            ))
        if "entered_amount" not in existing:
            conn.execute(text(
                "ALTER TABLE contract_lines ADD COLUMN entered_amount DECIMAL(14,2)"
            ))
            conn.execute(text(
                "UPDATE contract_lines SET entered_amount = monthly_amount WHERE entered_amount IS NULL"
            ))
        conn.commit()


def _seed_users() -> None:
    from src.models.user import User, UserRole
    from src.core.security import hash_password

    db = SessionLocal()
    try:
        count = db.execute(select(func.count()).select_from(User)).scalar_one()
        if count > 0:
            return

        seed_users = [
            User(email="admin@example.com",         full_name="Admin User",         role=UserRole.ADMIN,         hashed_password=hash_password("admin123"),         is_active=True),
            User(email="bizadmin@example.com",       full_name="Biz Admin User",     role=UserRole.BIZ_ADMIN,     hashed_password=hash_password("bizadmin123"),     is_active=True),
            User(email="serviceowner@example.com",   full_name="Service Owner User", role=UserRole.SERVICE_OWNER, hashed_password=hash_password("serviceowner123"), is_active=True),
            User(email="readonly@example.com",       full_name="Read Only User",     role=UserRole.READ_ONLY,     hashed_password=hash_password("readonly123"),     is_active=True),
        ]
        db.add_all(seed_users)
        db.commit()
    finally:
        db.close()


def _seed_db() -> None:
    from src.models.spend import Spend

    db = SessionLocal()
    try:
        count = db.execute(select(func.count()).select_from(Spend)).scalar_one()
        if count > 0:
            return

        month_keys = _last_n_months(6)
        rows = []
        for i in range(150):
            dept_code, dept_name = random.choice(ORACLE_DEPTS)
            acct_group = random.choice(ACCOUNT_GROUPS)
            acct_sub_group = random.choice(ACCOUNT_SUB_GROUPS[acct_group])
            mk = random.choice(month_keys)
            po_num = f"PO-{random.randint(10000, 99999)}" if random.random() > 0.4 else None
            inv_num = f"INV-{random.randint(10000, 99999)}" if random.random() > 0.3 else None

            rows.append(
                Spend(
                    month_key=mk,
                    month_label=_month_label(mk),
                    expense_type=random.choice(EXPENSE_TYPES),
                    company_code=random.choice(COMPANY_CODES),
                    oracle_organization=random.choice(ORACLE_ORGS),
                    oracle_account_number=f"ACC-{random.randint(1000, 9999)}",
                    oracle_department=dept_code,
                    oracle_department_name=dept_name,
                    oracle_cost_center_hierarchy=random.choice(COST_CENTER_HIERARCHIES),
                    oracle_account_group=acct_group,
                    oracle_account_sub_group=acct_sub_group,
                    oracle_cost_element=random.choice(COST_ELEMENTS),
                    line_desc=random.choice(LINE_DESCS),
                    vendor_name=random.choice(VENDORS),
                    po_recon=po_num,
                    po_description=f"Purchase order for {acct_sub_group}" if po_num else None,
                    purchase_order_number=po_num,
                    purchase_order_line_number=str(random.randint(1, 5)) if po_num else None,
                    invoice_number=inv_num,
                    invoice_line_number=str(random.randint(1, 10)) if inv_num else None,
                    je_source=random.choice(JE_SOURCES),
                    amount_usd=Decimal(str(round(random.uniform(50, 100000), 2))),
                )
            )

        db.add_all(rows)
        db.commit()
    finally:
        db.close()


def _seed_contracts() -> None:
    from src.models.contract import Contract, ContractLine, ContractStatus, BillingInterval
    from src.schemas.contract import compute_monthly_amount

    db = SessionLocal()
    try:
        count = db.execute(select(func.count()).select_from(Contract)).scalar_one()
        if count > 0:
            return

        seed_data = [
            # Monthly billing — entered_amount IS the monthly rate
            {
                "vendor_name": "Salesforce",
                "description": "Enterprise CRM platform — 3-year site license",
                "oracle_department": "1200",
                "oracle_department_name": "Sales",
                "oracle_account_number": "ACC-6385",
                "oracle_account_sub_group": "Software Licenses",
                "purchase_order_number": "PO-83353",
                "status": ContractStatus.ACTIVE,
                "lines": [
                    {"po_line_number": 4, "period_start": date(2026, 5, 1), "period_end": date(2027, 4, 30), "billing_interval": BillingInterval.MONTHLY, "entered_amount": Decimal("67888.29")},
                    {"po_line_number": 5, "period_start": date(2027, 5, 1), "period_end": date(2028, 4, 30), "billing_interval": BillingInterval.MONTHLY, "entered_amount": Decimal("68888.29")},
                    {"po_line_number": 6, "period_start": date(2028, 5, 1), "period_end": date(2029, 4, 30), "billing_interval": BillingInterval.MONTHLY, "entered_amount": Decimal("69888.29")},
                ],
            },
            # Quarterly billing — entered_amount is per-quarter; monthly = /3
            {
                "vendor_name": "GitHub",
                "description": "Enterprise source control & CI/CD — 2-year contract",
                "oracle_department": "1100",
                "oracle_department_name": "Engineering",
                "oracle_account_number": "ACC-6401",
                "oracle_account_sub_group": "Software Licenses",
                "purchase_order_number": "PO-91200",
                "status": ContractStatus.ACTIVE,
                "lines": [
                    {"po_line_number": 1, "period_start": date(2026, 1, 1), "period_end": date(2026, 12, 31), "billing_interval": BillingInterval.QUARTERLY, "entered_amount": Decimal("37500.00")},
                    {"po_line_number": 2, "period_start": date(2027, 1, 1), "period_end": date(2027, 12, 31), "billing_interval": BillingInterval.QUARTERLY, "entered_amount": Decimal("39000.00")},
                ],
            },
            # Yearly billing — entered_amount is the annual fee; monthly = /12
            {
                "vendor_name": "Workday",
                "description": "HR & Finance SaaS platform — annual renewal",
                "oracle_department": "1600",
                "oracle_department_name": "HR",
                "oracle_account_number": "ACC-5510",
                "oracle_account_sub_group": "Software Licenses",
                "purchase_order_number": "PO-77040",
                "status": ContractStatus.ACTIVE,
                "lines": [
                    {"po_line_number": 1, "period_start": date(2026, 4, 1), "period_end": date(2027, 3, 31), "billing_interval": BillingInterval.YEARLY, "entered_amount": Decimal("264000.00")},
                ],
            },
            # Custom billing — entered_amount is the total for the full period; monthly = total / months
            {
                "vendor_name": "Tableau",
                "description": "BI & analytics platform — expired 3-year deal",
                "oracle_department": "1300",
                "oracle_department_name": "Finance",
                "oracle_account_number": "ACC-6110",
                "oracle_account_sub_group": "Software Licenses",
                "purchase_order_number": "PO-60301",
                "status": ContractStatus.EXPIRED,
                "lines": [
                    {"po_line_number": 1, "period_start": date(2023, 1, 1), "period_end": date(2023, 12, 31), "billing_interval": BillingInterval.CUSTOM, "entered_amount": Decimal("100800.00")},
                    {"po_line_number": 2, "period_start": date(2024, 1, 1), "period_end": date(2024, 12, 31), "billing_interval": BillingInterval.CUSTOM, "entered_amount": Decimal("104400.00")},
                    {"po_line_number": 3, "period_start": date(2025, 1, 1), "period_end": date(2025, 12, 31), "billing_interval": BillingInterval.CUSTOM, "entered_amount": Decimal("108000.00")},
                ],
            },
        ]

        for item in seed_data:
            lines_data = item.pop("lines")
            contract = Contract(**item)
            for ld in lines_data:
                line = ContractLine(**ld)
                line.monthly_amount = compute_monthly_amount(
                    line.entered_amount, line.billing_interval, line.period_start, line.period_end
                )
                contract.lines.append(line)
            db.add(contract)

        db.commit()
    finally:
        db.close()


def _seed_budget() -> None:
    from src.models.budget import BudgetScenario, BudgetEntry, BudgetNcConfig

    db = SessionLocal()
    try:
        count = db.execute(select(func.count()).select_from(BudgetScenario)).scalar_one()
        if count > 0:
            return

        fiscal_year = 2027

        cfg = BudgetNcConfig(
            fiscal_year=fiscal_year,
            selected_cost_elements=["Salaries", "Travel"],
            updated_by="admin@example.com",
        )
        db.add(cfg)

        baseline = BudgetScenario(
            name="Baseline FY2027",
            description="Default baseline budget plan for FY2027",
            fiscal_year=fiscal_year,
            budget_type="NON_CONTROLLABLE",
            is_baseline=True,
            created_by="admin@example.com",
        )
        db.add(baseline)

        db.flush()

        dept_approved_recs = {
            "Engineering":   (Decimal("185000"), Decimal("185000"), Decimal("190000"), Decimal("195000")),
            "Sales":         (Decimal("120000"), Decimal("125000"), Decimal("125000"), Decimal("130000")),
            "Finance":       (Decimal("75000"),  Decimal("75000"),  Decimal("78000"),  Decimal("78000")),
            "Marketing":     (Decimal("90000"),  Decimal("95000"),  Decimal("95000"),  Decimal("100000")),
            "Operations":    (Decimal("60000"),  Decimal("60000"),  Decimal("62000"),  Decimal("62000")),
            "HR":            (Decimal("45000"),  Decimal("45000"),  Decimal("47000"),  Decimal("47000")),
            "Legal":         (Decimal("38000"),  Decimal("38000"),  Decimal("40000"),  Decimal("40000")),
            "IT":            (Decimal("55000"),  Decimal("55000"),  Decimal("57000"),  Decimal("57000")),
        }
        dept_additional_asks = {
            "Engineering":   (Decimal("15000"), Decimal("15000"), Decimal("20000"), Decimal("20000")),
            "Sales":         (Decimal("10000"), Decimal("10000"), Decimal("12000"), Decimal("12000")),
            "Finance":       (Decimal("5000"),  Decimal("5000"),  Decimal("5000"),  Decimal("5000")),
            "Marketing":     (Decimal("8000"),  Decimal("8000"),  Decimal("10000"), Decimal("10000")),
            "Operations":    (None,             None,             None,             None),
            "HR":            (Decimal("3000"),  Decimal("3000"),  Decimal("3000"),  Decimal("3000")),
            "Legal":         (None,             None,             None,             None),
            "IT":            (Decimal("4000"),  Decimal("4000"),  Decimal("5000"),  Decimal("5000")),
        }

        for dept, (q1, q2, q3, q4) in dept_approved_recs.items():
            db.add(BudgetEntry(
                scenario_id=baseline.id,
                department_name=dept,
                entry_type="APPROVED_REC",
                q1_amount=q1, q2_amount=q2, q3_amount=q3, q4_amount=q4,
                created_by="admin@example.com",
            ))

        for dept, (q1, q2, q3, q4) in dept_additional_asks.items():
            if any(x is not None for x in (q1, q2, q3, q4)):
                db.add(BudgetEntry(
                    scenario_id=baseline.id,
                    department_name=dept,
                    entry_type="ADDITIONAL_ASK",
                    q1_amount=q1, q2_amount=q2, q3_amount=q3, q4_amount=q4,
                    created_by="admin@example.com",
                ))

        db.commit()
    finally:
        db.close()
