from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from .database import Base

class BusinessUser(Base):
    __tablename__ = "business_users"
    __table_args__ = (UniqueConstraint("business_id", "user_id", name="uq_business_user"),)

    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # roles: "owner" | "accountant"
    role = Column(String(32), nullable=False, default="owner")

