from datetime import datetime

from sqlalchemy import Column, ForeignKey, Integer, JSON, String, Table, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


project_departments = Table(
    "project_departments",
    Base.metadata,
    Column("project_id", Integer, ForeignKey("project_ids.id", ondelete="CASCADE"), primary_key=True),
    Column("department_code", String(10), ForeignKey("departments.department_code", ondelete="CASCADE"), primary_key=True),
)


class Department(Base):
    __tablename__ = "departments"

    department_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    department_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    projects: Mapped[list["ProjectId"]] = relationship("ProjectId", secondary=project_departments, back_populates="departments")
    activity_ids: Mapped[list["ActivityId"]] = relationship("ActivityId", back_populates="department")


class AccountNumber(Base):
    __tablename__ = "account_numbers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    account_desc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_group: Mapped[str] = mapped_column(String(100), nullable=False)
    account_sub_group: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cost_element: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    activity_ids: Mapped[list["ActivityId"]] = relationship("ActivityId", back_populates="account")


class ProjectId(Base):
    __tablename__ = "project_ids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    project_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    departments: Mapped[list[Department]] = relationship("Department", secondary=project_departments, back_populates="projects")
    activity_ids: Mapped[list["ActivityId"]] = relationship("ActivityId", back_populates="project")


class ActivityId(Base):
    __tablename__ = "activity_ids"

    activity_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    activity_id_desc: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department_code: Mapped[str | None] = mapped_column(String(10), ForeignKey("departments.department_code", ondelete="SET NULL"), nullable=True, index=True)
    account_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("account_numbers.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("project_ids.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    department: Mapped[Department | None] = relationship("Department", back_populates="activity_ids")
    account: Mapped[AccountNumber | None] = relationship("AccountNumber", back_populates="activity_ids")
    project: Mapped[ProjectId | None] = relationship("ProjectId", back_populates="activity_ids")


class ReferenceAudit(Base):
    __tablename__ = "reference_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    record_id: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)  # CREATED, UPDATED, DELETED
    changes: Mapped[dict] = mapped_column(JSON, nullable=False)
    changed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
