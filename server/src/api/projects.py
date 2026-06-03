from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from src.core.dependencies import get_current_user, require_write
from src.db.session import get_db
from src.models.reference import ActivityId, Department, ProjectId, ReferenceAudit
from src.models.user import User
from src.schemas.reference import ProjectIdCreate, ProjectIdOut, ProjectIdUpdate

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _get_or_404(project_id: int, db: Session) -> ProjectId:
    obj = db.query(ProjectId).options(joinedload(ProjectId.departments)).filter(ProjectId.id == project_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Project not found")
    return obj


def _resolve_departments(codes: list[str], db: Session) -> list[Department]:
    depts = db.query(Department).filter(Department.department_code.in_(codes)).all()
    found = {d.department_code for d in depts}
    missing = set(codes) - found
    if missing:
        raise HTTPException(status_code=422, detail=f"Unknown department codes: {sorted(missing)}")
    return depts


@router.get("", response_model=list[ProjectIdOut])
def list_projects(department_code: str | None = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    q = db.query(ProjectId).options(joinedload(ProjectId.departments))
    if department_code:
        q = q.filter(ProjectId.departments.any(Department.department_code == department_code))
    return q.order_by(ProjectId.project_name).all()


@router.post("", response_model=ProjectIdOut, status_code=201)
def create_project(body: ProjectIdCreate, db: Session = Depends(get_db), current_user: User = Depends(require_write)):
    if db.query(ProjectId).filter(ProjectId.project_name == body.project_name).first():
        raise HTTPException(status_code=409, detail="Project name already exists")
    depts = _resolve_departments(body.department_codes, db)
    proj = ProjectId(project_number="__TEMP__", project_name=body.project_name, departments=depts)
    db.add(proj)
    db.flush()
    proj.project_number = f"PRJ-{proj.id:04d}"
    db.add(ReferenceAudit(
        table_name="project_ids",
        record_id=proj.project_number,
        event_type="CREATED",
        changes={},
        changed_by=current_user.email,
    ))
    db.commit()
    return db.query(ProjectId).options(joinedload(ProjectId.departments)).filter(ProjectId.id == proj.id).one()


@router.put("/{project_id}", response_model=ProjectIdOut)
def update_project(project_id: int, body: ProjectIdUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_write)):
    proj = _get_or_404(project_id, db)
    old_name = proj.project_name
    old_dept_codes = sorted(d.department_code for d in proj.departments)

    if body.project_name is not None:
        conflict = db.query(ProjectId).filter(
            ProjectId.project_name == body.project_name, ProjectId.id != project_id
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail="Project name already exists")
        proj.project_name = body.project_name
    if body.department_codes is not None:
        proj.departments = _resolve_departments(body.department_codes, db)

    changes = {}
    if body.project_name is not None and body.project_name != old_name:
        changes["project_name"] = {"old": old_name, "new": body.project_name}
    if body.department_codes is not None:
        new_dept_codes = sorted(body.department_codes)
        if old_dept_codes != new_dept_codes:
            changes["department_codes"] = {"old": old_dept_codes, "new": new_dept_codes}
    if changes:
        db.add(ReferenceAudit(
            table_name="project_ids",
            record_id=proj.project_number,
            event_type="UPDATED",
            changes=changes,
            changed_by=current_user.email,
        ))
    db.commit()
    return db.query(ProjectId).options(joinedload(ProjectId.departments)).filter(ProjectId.id == project_id).one()


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_write)):
    proj = _get_or_404(project_id, db)
    if db.query(ActivityId).filter(ActivityId.project_id == project_id).first():
        raise HTTPException(status_code=409, detail="Project is referenced by one or more activity IDs")
    db.add(ReferenceAudit(
        table_name="project_ids",
        record_id=proj.project_number,
        event_type="DELETED",
        changes={},
        changed_by=current_user.email,
    ))
    db.delete(proj)
    db.commit()
