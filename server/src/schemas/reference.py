from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DepartmentBase(BaseModel):
    department_name: str


class DepartmentCreate(DepartmentBase):
    department_code: str


class DepartmentUpdate(BaseModel):
    department_name: str | None = None


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    department_code: str
    department_name: str


# ── Account Numbers ───────────────────────────────────────────────────────────

class AccountNumberBase(BaseModel):
    account_desc: str | None = None
    account_group: str
    account_sub_group: str | None = None
    cost_element: str


class AccountNumberCreate(AccountNumberBase):
    pass  # account_number is auto-generated from id


class AccountNumberUpdate(BaseModel):
    account_desc: str | None = None
    account_group: str | None = None
    account_sub_group: str | None = None
    cost_element: str | None = None


class AccountNumberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    account_number: str
    account_desc: str | None
    account_group: str
    account_sub_group: str | None
    cost_element: str


# ── Project IDs ───────────────────────────────────────────────────────────────

class ProjectIdCreate(BaseModel):
    project_name: str
    department_codes: list[str] = []


class ProjectIdUpdate(BaseModel):
    project_name: str | None = None
    department_codes: list[str] | None = None


class ProjectIdOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_number: str
    project_name: str
    departments: list[DepartmentOut] = []


# ── Activity IDs ──────────────────────────────────────────────────────────────

class ActivityIdCreate(BaseModel):
    activity_id: str
    activity_id_desc: str | None = None
    department_code: str | None = None
    account_id: int | None = None
    project_id: int | None = None


class ActivityIdUpdate(BaseModel):
    activity_id_desc: str | None = None
    department_code: str | None = None
    account_id: int | None = None
    project_id: int | None = None


class ActivityIdOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    activity_id: str
    activity_id_desc: str | None
    department_code: str | None
    department_name: str | None = None
    account_id: int | None
    account_number: str | None = None
    account_group: str | None = None
    account_sub_group: str | None = None
    cost_element: str | None = None
    project_id: int | None
    project_number: str | None = None
    project_name: str | None = None

    @classmethod
    def from_orm_with_joins(cls, obj) -> "ActivityIdOut":
        return cls(
            activity_id=obj.activity_id,
            activity_id_desc=obj.activity_id_desc,
            department_code=obj.department_code,
            department_name=obj.department.department_name if obj.department else None,
            account_id=obj.account_id,
            account_number=obj.account.account_number if obj.account else None,
            account_group=obj.account.account_group if obj.account else None,
            account_sub_group=obj.account.account_sub_group if obj.account else None,
            cost_element=obj.account.cost_element if obj.account else None,
            project_id=obj.project_id,
            project_number=obj.project.project_number if obj.project else None,
            project_name=obj.project.project_name if obj.project else None,
        )


# ── Reference Audit ───────────────────────────────────────────────────────────

class ReferenceAuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    table_name: str
    record_id: str
    event_type: str
    changes: dict
    changed_by: str
    changed_at: datetime
