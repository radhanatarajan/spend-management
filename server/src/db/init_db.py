import random
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, func

from src.db.base import Base
from src.db.session import engine, SessionLocal
from src.models import spend as _spend_module  # noqa: F401 — registers Spend with Base.metadata


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
    _seed_db()


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
