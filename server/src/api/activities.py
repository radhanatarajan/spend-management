from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from src.core.dependencies import get_current_user, require_write
from src.db.session import get_db
from src.models.reference import ActivityId
from src.schemas.reference import ActivityIdCreate, ActivityIdOut, ActivityIdUpdate

router = APIRouter(prefix="/api/activities", tags=["activities"])


def _get_or_404(activity_id: str, db: Session) -> ActivityId:
    obj = (
        db.query(ActivityId)
        .options(joinedload(ActivityId.department), joinedload(ActivityId.account), joinedload(ActivityId.project))
        .filter(ActivityId.activity_id == activity_id)
        .first()
    )
    if not obj:
        raise HTTPException(status_code=404, detail="Activity ID not found")
    return obj


def _load_all(db: Session, department_code: str | None = None) -> list[ActivityId]:
    q = (
        db.query(ActivityId)
        .options(joinedload(ActivityId.department), joinedload(ActivityId.account), joinedload(ActivityId.project))
    )
    if department_code:
        q = q.filter(ActivityId.department_code == department_code)
    return q.order_by(ActivityId.activity_id).all()


@router.get("", response_model=list[ActivityIdOut])
def list_activities(department_code: str | None = None, db: Session = Depends(get_db), _=Depends(get_current_user)):
    rows = _load_all(db, department_code)
    return [ActivityIdOut.from_orm_with_joins(r) for r in rows]


@router.post("", response_model=ActivityIdOut, status_code=201)
def create_activity(body: ActivityIdCreate, db: Session = Depends(get_db), _=Depends(require_write)):
    if db.get(ActivityId, body.activity_id):
        raise HTTPException(status_code=409, detail="Activity ID already exists")
    obj = ActivityId(**body.model_dump())
    db.add(obj)
    db.commit()
    return ActivityIdOut.from_orm_with_joins(_get_or_404(body.activity_id, db))


@router.put("/{activity_id}", response_model=ActivityIdOut)
def update_activity(activity_id: str, body: ActivityIdUpdate, db: Session = Depends(get_db), _=Depends(require_write)):
    obj = _get_or_404(activity_id, db)
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(obj, field, val)
    db.commit()
    return ActivityIdOut.from_orm_with_joins(_get_or_404(activity_id, db))


@router.delete("/{activity_id}", status_code=204)
def delete_activity(activity_id: str, db: Session = Depends(get_db), _=Depends(require_write)):
    obj = _get_or_404(activity_id, db)
    db.delete(obj)
    db.commit()
