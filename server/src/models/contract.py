from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Integer, String, Text, Numeric, Date, DateTime, ForeignKey, JSON, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from src.db.base import Base


class ContractStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PENDING = "pending"


class BillingInterval(str, enum.Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"  # entered_amount is the total for the entire line period


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    vendor_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    oracle_department: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    oracle_department_name: Mapped[str] = mapped_column(String(255), nullable=False)
    oracle_account_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    oracle_account_sub_group: Mapped[str] = mapped_column(String(255), nullable=False)

    purchase_order_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    status: Mapped[ContractStatus] = mapped_column(
        SAEnum(ContractStatus), nullable=False, default=ContractStatus.ACTIVE
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    lines: Mapped[list["ContractLine"]] = relationship(
        "ContractLine", back_populates="contract", cascade="all, delete-orphan",
        order_by="ContractLine.po_line_number"
    )


class ContractLine(Base):
    __tablename__ = "contract_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(Integer, ForeignKey("contracts.id"), nullable=False, index=True)

    po_line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    billing_interval: Mapped[BillingInterval] = mapped_column(
        SAEnum(BillingInterval, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False, default=BillingInterval.MONTHLY
    )
    # Amount as entered by the user in the billing interval's denomination.
    # monthly_amount is always derived from this on write (see api/contracts.py).
    entered_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # Canonical per-month value used for planning; computed and stored on every write.
    monthly_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    contract: Mapped["Contract"] = relationship("Contract", back_populates="lines")


class ContractAudit(Base):
    __tablename__ = "contract_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    vendor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    purchase_order_number: Mapped[str] = mapped_column(String(100), nullable=False)
    entity: Mapped[str] = mapped_column(String(20), nullable=False)   # "contract" or "line"
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)  # CREATED, UPDATED, DELETED
    changes: Mapped[dict] = mapped_column(JSON, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
