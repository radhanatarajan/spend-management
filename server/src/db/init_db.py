import random
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import select, func, text

from src.db.base import Base
from src.db.session import engine, SessionLocal
from src.models import spend as _spend_module     # noqa: F401 — registers Spend with Base.metadata
from src.models import user as _user_module       # noqa: F401 — registers User with Base.metadata
from src.models import contract as _contract_module  # noqa: F401 — registers Contract/ContractLine with Base.metadata


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
    _seed_db()
    _seed_users()
    _seed_contracts()


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
