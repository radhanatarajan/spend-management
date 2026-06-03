import pytest
from decimal import Decimal
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.base import Base
from src.db.session import get_db
from src.core.dependencies import get_current_user
from src.main import app
from src.models.spend import Spend  # registers Spend with Base.metadata
from src.models.contract import Contract, ContractLine, ContractAudit, ContractStatus, BillingInterval  # noqa: F401
from src.models.budget import BudgetScenario, BudgetEntry, BudgetNcConfig, BudgetEntryAudit, BudgetScenarioAudit, BudgetNcConfigAudit  # noqa: F401
from src.models.reference import Department, AccountNumber, ProjectId, ActivityId, ReferenceAudit  # noqa: F401
from src.models.user import User, UserRole

# StaticPool forces all sessions to share a single in-memory connection
# so tables created in reset_db are visible to the TestClient.
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = override_get_db
    # Suppress init_db() so tests run against SQLite without needing MySQL.
    with patch("src.main.init_db"), TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def make_contract(db, vendor="Acme", po="PO-001", lines=None, **kwargs):
    """Create and persist a Contract with optional lines."""
    from datetime import date
    from decimal import Decimal
    from src.schemas.contract import compute_monthly_amount

    defaults = dict(
        vendor_name=vendor,
        oracle_department="1100",
        oracle_department_name="Engineering",
        oracle_account_number="ACC-0001",
        oracle_account_sub_group="Software Licenses",
        purchase_order_number=po,
        status=ContractStatus.ACTIVE,
    )
    defaults.update(kwargs)
    contract = Contract(**defaults)

    for ld in (lines or []):
        line = ContractLine(**ld)
        line.monthly_amount = compute_monthly_amount(
            line.entered_amount, line.billing_interval, line.period_start, line.period_end
        )
        contract.lines.append(line)

    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


def _mock_user(role: UserRole = UserRole.ADMIN) -> User:
    """Return an unsaved User object suitable for dependency override."""
    return User(
        id=999,
        email=f"{role.value.lower()}@test.com",
        full_name=f"Test {role.value}",
        role=role,
        is_active=True,
        hashed_password="x",
    )


@pytest.fixture
def admin_client(client):
    app.dependency_overrides[get_current_user] = lambda: _mock_user(UserRole.ADMIN)
    return client


@pytest.fixture
def bizadmin_client(client):
    app.dependency_overrides[get_current_user] = lambda: _mock_user(UserRole.BIZ_ADMIN)
    return client


@pytest.fixture
def serviceowner_client(client):
    app.dependency_overrides[get_current_user] = lambda: _mock_user(UserRole.SERVICE_OWNER)
    return client


@pytest.fixture
def readonly_client(client):
    app.dependency_overrides[get_current_user] = lambda: _mock_user(UserRole.READ_ONLY)
    return client


def make_scenario(db, fiscal_year=2027, name="Baseline", is_baseline=True, budget_type="NON_CONTROLLABLE"):
    s = BudgetScenario(
        name=name,
        fiscal_year=fiscal_year,
        budget_type=budget_type,
        is_baseline=is_baseline,
        created_by="admin@test.com",
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def make_entry(db, scenario_id, department_name="Engineering", entry_type="APPROVED_REC",
               q1=None, q2=None, q3=None, q4=None, status="DRAFT"):
    e = BudgetEntry(
        scenario_id=scenario_id,
        department_name=department_name,
        entry_type=entry_type,
        q1_amount=q1,
        q2_amount=q2,
        q3_amount=q3,
        q4_amount=q4,
        status=status,
        created_by="admin@test.com",
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def make_spend(**kwargs) -> Spend:
    defaults = dict(
        month_key=202601,
        month_label="Jan 2026",
        expense_type="Opex",
        company_code="1000",
        oracle_organization="US01",
        oracle_account_number="ACC-1001",
        oracle_department="1100",
        oracle_department_name="Engineering",
        oracle_cost_center_hierarchy="Americas > US > West",
        oracle_account_group="R&D",
        oracle_account_sub_group="Engineering Salaries",
        oracle_cost_element="Salaries",
        line_desc="Monthly SaaS subscription",
        vendor_name="AWS",
        po_recon=None,
        po_description=None,
        purchase_order_number=None,
        purchase_order_line_number=None,
        invoice_number=None,
        invoice_line_number=None,
        je_source="Coupa",
        amount_usd=Decimal("1000.00"),
    )
    defaults.update(kwargs)
    return Spend(**defaults)
