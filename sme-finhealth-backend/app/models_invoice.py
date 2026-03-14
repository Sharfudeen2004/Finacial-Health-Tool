from sqlalchemy import Column, Integer, String, Date, Float, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from .database import Base

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)

    vendor_name = Column(String(255), nullable=True)
    vendor_gstin = Column(String(32), nullable=True)

    invoice_number = Column(String(64), nullable=True)
    invoice_date = Column(Date, nullable=True)

    total_amount = Column(Float, nullable=True)
    currency = Column(String(8), nullable=True, default="INR")

    raw_text = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
