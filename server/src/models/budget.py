from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import Integer, String, Text, Numeric, DateTime, Boolean, JSON, ForeignKey, UniqueConstraint, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class BudgetType(str, PyEnum):
    NON_CONTROLLABLE = "NON_CONTROLLABLE"
    CONTROLLABLE = "CONTROLLABLE"


class EntryType(str, PyEnum):
    APPROVED_REC = "APPROVED_REC"
    ADDITIONAL_ASK = "ADDITIONAL_ASK"


class ScenarioStatus(str, PyEnum):
    DRAFT = "DRAFT"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    FINAL = "FINAL"
    CANCELLED = "CANCELLED"


class BudgetScenario(Base):
    __tablename__ = "budget_scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    budget_type: Mapped[str] = mapped_column(
        Enum("NON_CONTROLLABLE", "CONTROLLABLE", name="budget_type_enum"), nullable=False
    )
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    entries: Mapped[list["BudgetEntry"]] = relationship(
        "BudgetEntry", back_populates="scenario", cascade="all, delete-orphan"
    )


class BudgetEntry(Base):
    __tablename__ = "budget_entries"
    __table_args__ = (
        UniqueConstraint("scenario_id", "department_name", "entry_type", name="uq_budget_entry"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("budget_scenarios.id", ondelete="CASCADE"), nullable=False, index=True)
    department_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(
        Enum("APPROVED_REC", "ADDITIONAL_ASK", name="entry_type_enum"), nullable=False
    )
    q1_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    q2_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    q3_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    q4_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("DRAFT", "READY_FOR_REVIEW", "APPROVED", "FINAL", "CANCELLED", name="entry_status_enum"),
        nullable=False, default="DRAFT",
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    scenario: Mapped["BudgetScenario"] = relationship("BudgetScenario", back_populates="entries")


class BudgetNcConfig(Base):
    __tablename__ = "budget_nc_config"
    __table_args__ = (
        UniqueConstraint("fiscal_year", name="uq_nc_config_fy"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    selected_cost_elements: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    actuals_cutoff_month_key: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class BudgetEntryAudit(Base):
    __tablename__ = "budget_entry_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("budget_scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entry_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    department_name: Mapped[str] = mapped_column(String(255), nullable=False)
    entry_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    changes: Mapped[dict] = mapped_column(JSON, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class BudgetScenarioAudit(Base):
    __tablename__ = "budget_scenario_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    scenario_name: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)  # CREATED, UPDATED, DELETED
    changes: Mapped[dict] = mapped_column(JSON, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class BudgetNcConfigAudit(Base):
    __tablename__ = "budget_nc_config_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)  # CREATED, UPDATED
    changes: Mapped[dict] = mapped_column(JSON, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
