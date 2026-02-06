from pydantic import BaseModel
from typing import Optional, Any
from datetime import date


# ---------- Upload ----------
class UploadPreviewResponse(BaseModel):
    columns: list[str]
    preview: list[dict[str, Any]]
    detected: dict[str, Any]


# ---------- Transactions ----------
class TransactionOut(BaseModel):
    id: int
    business_id: int
    txn_date: date
    description: Optional[str] = None
    amount: float
    direction: str
    category: Optional[str] = None

    class Config:
        from_attributes = True


# ---------- KPIs ----------
class KPISummary(BaseModel):
    business_id: int
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    total_transactions: int

    total_inflow: float
    total_outflow: float
    net_cashflow: float

    total_revenue: float
    total_expenses: float
    net_profit_simple: float

    gross_margin_simple: Optional[float] = None
    expense_ratio: Optional[float] = None


class MonthlyKPI(BaseModel):
    month: str
    inflow: float
    outflow: float
    net_cashflow: float
    revenue: float
    expenses: float
    profit_simple: float


# ---------- Auth ----------
class RegisterIn(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None

    class Config:
        from_attributes = True


# ---------- Business ----------
class BusinessCreateIn(BaseModel):
    name: str
    industry: Optional[str] = None


class BusinessOut(BaseModel):
    id: int
    name: str
    industry: Optional[str] = None
    owner_user_id: int

    class Config:
        from_attributes = True


# ---------- GST ----------
class GSTImportResult(BaseModel):
    inserted: int
    business_id: int
