from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.core.dependencies import get_current_user
from src.db.session import get_db
from src.models.reference import ReferenceAudit
from src.schemas.reference import ReferenceAuditOut

router = APIRouter(prefix="/api/reference", tags=["reference"])


@router.get("/audit", response_model=list[ReferenceAuditOut])
def get_reference_audit(
    table_name: str | None = Query(None, description="Filter by entity type: departments, account_numbers, project_ids, activity_ids"),
    record_id: str | None = Query(None, description="Filter by specific record identifier"),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(ReferenceAudit)
    if table_name:
        q = q.filter(ReferenceAudit.table_name == table_name)
    if record_id:
        q = q.filter(ReferenceAudit.record_id == record_id)
    return q.order_by(ReferenceAudit.changed_at.desc()).limit(500).all()
