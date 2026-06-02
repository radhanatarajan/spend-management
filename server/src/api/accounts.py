from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.core.dependencies import get_current_user, require_write
from src.db.session import get_db
from src.models.reference import AccountNumber, ActivityId
from src.schemas.reference import AccountNumberCreate, AccountNumberOut, AccountNumberUpdate

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def _get_or_404(id: int, db: Session) -> AccountNumber:
    obj = db.get(AccountNumber, id)
    if not obj:
        raise HTTPException(status_code=404, detail="Account number not found")
    return obj


@router.get("", response_model=list[AccountNumberOut])
def list_accounts(
    account_group: str | None = None,
    account_sub_group: str | None = None,
    cost_element: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(AccountNumber)
    if account_group:
        q = q.filter(AccountNumber.account_group == account_group)
    if account_sub_group:
        q = q.filter(AccountNumber.account_sub_group == account_sub_group)
    if cost_element:
        q = q.filter(AccountNumber.cost_element == cost_element)
    return q.order_by(AccountNumber.account_number).all()


@router.post("", response_model=AccountNumberOut, status_code=201)
def create_account(body: AccountNumberCreate, db: Session = Depends(get_db), _=Depends(require_write)):
    acct = AccountNumber(
        account_number="__PENDING__",
        account_desc=body.account_desc,
        account_group=body.account_group,
        account_sub_group=body.account_sub_group,
        cost_element=body.cost_element,
    )
    db.add(acct)
    db.flush()
    acct.account_number = f"ACC-{acct.id:04d}"
    db.commit()
    db.refresh(acct)
    return acct


@router.put("/{id}", response_model=AccountNumberOut)
def update_account(id: int, body: AccountNumberUpdate, db: Session = Depends(get_db), _=Depends(require_write)):
    acct = _get_or_404(id, db)
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(acct, field, val)
    db.commit()
    db.refresh(acct)
    return acct


@router.delete("/{id}", status_code=204)
def delete_account(id: int, db: Session = Depends(get_db), _=Depends(require_write)):
    acct = _get_or_404(id, db)
    ref = db.query(ActivityId).filter(ActivityId.account_id == id).first()
    if ref:
        raise HTTPException(status_code=409, detail="Account number is referenced by one or more activity IDs")
    db.delete(acct)
    db.commit()
