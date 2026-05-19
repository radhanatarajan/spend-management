import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db.base import Base
from src.db.session import get_db
from src.main import app
from src.models.spend import Spend  # registers Spend with Base.metadata

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
    # raise_server_exceptions=False lets us assert on 500 responses
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


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
