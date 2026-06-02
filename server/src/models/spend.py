from datetime import datetime
from decimal import Decimal
from sqlalchemy import Integer, String, Text, Numeric, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from src.db.base import Base


class Spend(Base):
    __tablename__ = "spend"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    month_key: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    month_label: Mapped[str] = mapped_column(String(20), nullable=False)

    expense_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    company_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    oracle_organization: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    oracle_account_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    oracle_department: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    oracle_department_name: Mapped[str] = mapped_column(String(255), nullable=False)

    oracle_cost_center_hierarchy: Mapped[str] = mapped_column(String(255), nullable=False)

    oracle_account_group: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    oracle_account_sub_group: Mapped[str] = mapped_column(String(255), nullable=False)

    oracle_cost_element: Mapped[str] = mapped_column(String(100), nullable=False)
    line_desc: Mapped[str | None] = mapped_column(Text, nullable=True)

    vendor_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    po_recon: Mapped[str | None] = mapped_column(String(100), nullable=True)
    po_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    purchase_order_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    purchase_order_line_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invoice_line_number: Mapped[str | None] = mapped_column(String(50), nullable=True)

    je_source: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    activity_id: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)

    amount_usd: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
