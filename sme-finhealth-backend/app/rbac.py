from fastapi import HTTPException
from sqlalchemy.orm import Session
from .models_rbac import BusinessUser

def require_role(db: Session, business_id: int, user_id: int, allowed: set[str]):
    row = (
        db.query(BusinessUser)
        .filter(BusinessUser.business_id == business_id, BusinessUser.user_id == user_id)
        .first()
    )
    if not row:
        raise HTTPException(403, "No access to this business")
    if row.role not in allowed:
        raise HTTPException(403, "Insufficient role")
    return row.role
