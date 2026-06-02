from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.core.dependencies import get_current_user, require_write
from src.db.session import get_db
from src.models.reference import ActivityId, Department, ProjectId
from src.schemas.reference import DepartmentCreate, DepartmentOut, DepartmentUpdate

router = APIRouter(prefix="/api/departments", tags=["departments"])


def _get_or_404(code: str, db: Session) -> Department:
    obj = db.get(Department, code)
    if not obj:
        raise HTTPException(status_code=404, detail="Department not found")
    return obj


@router.get("", response_model=list[DepartmentOut])
def list_departments(db: Session = Depends(get_db), _=Depends(get_current_user)):
    return db.query(Department).order_by(Department.department_code).all()


@router.post("", response_model=DepartmentOut, status_code=201)
def create_department(body: DepartmentCreate, db: Session = Depends(get_db), _=Depends(require_write)):
    if db.get(Department, body.department_code):
        raise HTTPException(status_code=409, detail="Department code already exists")
    dept = Department(department_code=body.department_code, department_name=body.department_name)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


@router.put("/{code}", response_model=DepartmentOut)
def update_department(code: str, body: DepartmentUpdate, db: Session = Depends(get_db), _=Depends(require_write)):
    dept = _get_or_404(code, db)
    if body.department_name is not None:
        dept.department_name = body.department_name
    db.commit()
    db.refresh(dept)
    return dept


@router.delete("/{code}", status_code=204)
def delete_department(code: str, db: Session = Depends(get_db), _=Depends(require_write)):
    dept = _get_or_404(code, db)
    in_activity = db.query(ActivityId).filter(ActivityId.department_code == code).first()
    if in_activity:
        raise HTTPException(status_code=409, detail="Department is referenced by one or more activity IDs")
    # project_departments cascade handles M2M rows; just check if any project's *only* dept is this one
    dept.projects.clear()
    db.delete(dept)
    db.commit()
