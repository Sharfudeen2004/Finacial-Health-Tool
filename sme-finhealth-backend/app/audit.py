# app/audit.py
from fastapi import Request
from sqlalchemy.orm import Session
from .models_audit import AuditLog

def log_audit(
    db: Session,
    request: Request,
    user_id: int | None,
    business_id: int | None,
    action: str,
    entity: str | None = None,
    entity_id: int | None = None,
    payload: dict | None = None,
):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    db.add(
        AuditLog(
            user_id=user_id,
            business_id=business_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            ip=ip,
            user_agent=ua[:255] if ua else None,
            payload=payload,
        )
    )
    db.commit()
