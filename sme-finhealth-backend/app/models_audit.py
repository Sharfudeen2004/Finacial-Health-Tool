# app/models_audit.py
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from .database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=True)

    action = Column(String(64), nullable=False)      # e.g. "REGISTER", "UPLOAD_COMMIT"
    entity = Column(String(64), nullable=True)       # e.g. "transaction", "gst"
    entity_id = Column(Integer, nullable=True)

    ip = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)

    payload = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
