# app/main.py
from __future__ import annotations

import io
import re
from datetime import datetime, date, timedelta

import pandas as pd
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc

from .database import Base, engine, get_db
from .models import Transaction, Business, User
from .auth import get_current_user

# Routers you already have
from .routes_auth import router as auth_router
from .routes_gst import router as gst_router

# Audit
from .models_audit import AuditLog
from .audit import log_audit

from .routes_invoice_ocr import router as invoice_router
from .models_invoice import Invoice

from .routes_advisor import router as advisor_router

from .routes_bank_real import router as bank_real_router

from .routes_reports import router as reports_router

# =========================
# App
# =========================
app = FastAPI(title="SME Financial Health Backend (MVP)", version="1.0.0")

# CORS for Vite
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(gst_router)
app.include_router(invoice_router)
app.include_router(advisor_router)
app.include_router(bank_real_router)
app.include_router(reports_router)



# Create tables
Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {"status": "ok", "message": "Backend running"}


# =========================
# Helpers
# =========================
def require_business_owner(db: Session, business_id: int, user_id: int) -> Business:
    biz = db.query(Business).filter(Business.id == business_id).first()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")
    if getattr(biz, "owner_user_id", None) != user_id:
        raise HTTPException(status_code=403, detail="Not allowed for this business")
    return biz


def _safe_float(x) -> float:
    try:
        if pd.isna(x):
            return 0.0
        s = str(x).replace(",", "").strip()
        if s == "":
            return 0.0
        return float(s)
    except Exception:
        return 0.0


def _normalize_direction(v: str) -> str:
    s = (v or "").strip().lower()
    if s in ["credit", "cr", "c", "in", "inflow", "income"]:
        return "credit"
    if s in ["debit", "dr", "d", "out", "outflow", "expense"]:
        return "debit"
    return "debit"


def _parse_date_any(v) -> date:
    if isinstance(v, date):
        return v
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    try:
        return pd.to_datetime(s).date()
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid date: {v}")


def _add_months_ym(ym: str, add: int) -> str:
    y, m = ym.split("-")
    y = int(y)
    m = int(m)
    idx = (y * 12 + (m - 1)) + add
    ny = idx // 12
    nm = (idx % 12) + 1
    return f"{ny:04d}-{nm:02d}"


def read_file_to_df(filename: str, content: bytes) -> pd.DataFrame:
    name = (filename or "").lower()
    buf = io.BytesIO(content)

    if name.endswith(".csv"):
        return pd.read_csv(buf)
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(buf)

    raise HTTPException(status_code=400, detail="Unsupported file. Upload CSV/XLSX/PDF.")


def normalize_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Required: date, amount
    Optional: description, category, direction
    Output: txn_date, description, category, direction, amount
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["txn_date", "description", "category", "direction", "amount"])

    cols = {c.lower().strip(): c for c in df.columns}

    def pick(*names):
        for n in names:
            if n in cols:
                return cols[n]
        return None

    c_date = pick("date", "txn_date", "transaction_date", "value_date")
    c_desc = pick("description", "narration", "particulars", "details", "remark", "remarks")
    c_cat = pick("category", "cat", "type")
    c_dir = pick("direction", "drcr", "dr_cr", "credit_debit")
    c_amt = pick("amount", "amt", "value", "transaction_amount")

    if not c_date or not c_amt:
        raise HTTPException(
            status_code=400,
            detail="CSV/XLSX must contain at least: date, amount (optional description/category/direction).",
        )

    out = pd.DataFrame()
    out["txn_date"] = df[c_date].apply(_parse_date_any)
    out["description"] = df[c_desc].astype(str) if c_desc else ""
    out["category"] = df[c_cat].astype(str).str.lower().fillna("") if c_cat else ""

    if c_dir:
        out["direction"] = df[c_dir].astype(str).apply(_normalize_direction)
        out["amount"] = df[c_amt].apply(_safe_float).abs()
    else:
        amt = df[c_amt].apply(_safe_float)
        out["direction"] = amt.apply(lambda x: "credit" if x >= 0 else "debit")
        out["amount"] = amt.abs()

    out.loc[(out["category"] == "") & (out["direction"] == "credit"), "category"] = "revenue"
    out.loc[(out["category"] == "") & (out["direction"] == "debit"), "category"] = "expense"

    out["description"] = out["description"].fillna("").astype(str).str.strip().str.slice(0, 255)
    out["category"] = out["category"].fillna("").astype(str).str.strip().str.slice(0, 64)
    out["direction"] = out["direction"].fillna("debit").astype(str).str.strip().str.lower()

    return out[["txn_date", "description", "category", "direction", "amount"]]


# =========================
# Audit logs viewer
# =========================
@app.get("/audit/logs")
def get_audit_logs(
    business_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_business_owner(db, business_id, current_user.id)

    rows = (
        db.query(AuditLog)
        .filter(AuditLog.business_id == business_id)
        .order_by(AuditLog.id.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": r.id,
            "action": r.action,
            "entity": r.entity,
            "entity_id": r.entity_id,
            "user_id": r.user_id,
            "business_id": r.business_id,
            "ip": r.ip,
            "user_agent": r.user_agent,
            "payload": r.payload,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


# =========================
# Upload (CSV/XLSX)
# =========================
@app.post("/upload/preview")
async def upload_preview(
    business_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_business_owner(db, business_id, current_user.id)

    content = await file.read()
    df = read_file_to_df(file.filename, content)
    norm = normalize_transactions(df)

    prev = norm.head(10).copy()
    prev["txn_date"] = prev["txn_date"].astype(str)

    return {"columns": list(prev.columns), "preview": prev.to_dict(orient="records"), "detected": {"rows": int(norm.shape[0])}}


@app.post("/upload/commit")
async def upload_commit(
    business_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_business_owner(db, business_id, current_user.id)

    content = await file.read()
    df = read_file_to_df(file.filename, content)
    norm = normalize_transactions(df)

    rows = norm.to_dict(orient="records")
    for r in rows:
        db.add(
            Transaction(
                business_id=business_id,
                txn_date=r["txn_date"],
                description=r["description"],
                category=r["category"],
                direction=r["direction"],
                amount=float(r["amount"]),
            )
        )

    db.commit()

    log_audit(
        db,
        request,
        user_id=current_user.id,
        business_id=business_id,
        action="UPLOAD_COMMIT",
        entity="transaction",
        payload={"filename": file.filename, "inserted": len(rows)},
    )

    return {"inserted": len(rows)}


# =========================
# PDF Import (text-based)
# =========================
def parse_pdf_transactions_text(pdf_bytes: bytes) -> pd.DataFrame:
    try:
        import pdfplumber
    except Exception:
        raise HTTPException(status_code=400, detail="pdfplumber not installed. Run: pip install pdfplumber")

    lines: list[str] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            for line in txt.split("\n"):
                line = line.strip()
                if line:
                    lines.append(line)

    date_patterns = [r"^\d{4}-\d{2}-\d{2}", r"^\d{2}/\d{2}/\d{4}", r"^\d{2}-\d{2}-\d{4}"]
    date_re = re.compile("|".join(date_patterns))

    rows = []
    for line in lines:
        if not date_re.search(line):
            continue

        parts = line.split()
        raw_date = parts[0]
        try:
            txn_date = _parse_date_any(raw_date)
        except Exception:
            continue

        nums = re.findall(r"[-]?\d[\d,]*\.?\d*", line)
        if not nums:
            continue

        raw_amt = nums[-1].replace(",", "")
        try:
            amt = float(raw_amt)
        except Exception:
            continue

        u = line.upper()
        direction = "debit" if (" DR" in u or "DEBIT" in u) else "credit"
        category = "revenue" if direction == "credit" else "expense"
        desc = line.replace(parts[0], "").strip()

        rows.append(
            {
                "txn_date": txn_date,
                "description": desc[:255],
                "category": category,
                "direction": direction,
                "amount": abs(amt),
            }
        )

    return pd.DataFrame(rows)


@app.post("/upload/pdf/preview")
async def pdf_preview(
    business_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_business_owner(db, business_id, current_user.id)

    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload a PDF file")

    pdf_bytes = await file.read()
    df = parse_pdf_transactions_text(pdf_bytes)

    if df.empty:
        return {"columns": [], "preview": [], "detected": {"rows": 0, "message": "No rows detected (is this a text PDF?)"}}

    prev = df.head(10).copy()
    prev["txn_date"] = prev["txn_date"].astype(str)
    return {"columns": list(prev.columns), "preview": prev.to_dict(orient="records"), "detected": {"rows": int(df.shape[0])}}


@app.post("/upload/pdf/commit")
async def pdf_commit(
    business_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_business_owner(db, business_id, current_user.id)

    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload a PDF file")

    pdf_bytes = await file.read()
    df = parse_pdf_transactions_text(pdf_bytes)
    if df.empty:
        raise HTTPException(status_code=400, detail="No transactions detected. PDF might be scanned image (needs OCR).")

    rows = df.to_dict(orient="records")
    for r in rows:
        db.add(
            Transaction(
                business_id=business_id,
                txn_date=r["txn_date"],
                description=r["description"],
                category=r["category"],
                direction=r["direction"],
                amount=float(r["amount"]),
            )
        )

    db.commit()

    log_audit(
        db,
        request,
        user_id=current_user.id,
        business_id=business_id,
        action="PDF_COMMIT",
        entity="transaction",
        payload={"filename": file.filename, "inserted": len(rows)},
    )

    return {"inserted": len(rows)}


# =========================
# KPIs
# =========================
@app.get("/kpis")
def kpis(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_business_owner(db, business_id, current_user.id)
    txns = db.query(Transaction).filter(Transaction.business_id == business_id).all()

    inflow = sum(float(t.amount) for t in txns if (t.direction or "").lower() == "credit")
    outflow = sum(float(t.amount) for t in txns if (t.direction or "").lower() == "debit")
    revenue = sum(float(t.amount) for t in txns if (t.category or "").lower() == "revenue" and (t.direction or "").lower() == "credit")
    expenses = sum(float(t.amount) for t in txns if (t.direction or "").lower() == "debit")

    net_cashflow = inflow - outflow
    profit_simple = revenue - expenses
    expense_ratio = (expenses / revenue * 100.0) if revenue > 0 else None

    return {
        "business_id": business_id,
        "total_transactions": len(txns),
        "total_inflow": round(inflow, 2),
        "total_outflow": round(outflow, 2),
        "net_cashflow": round(net_cashflow, 2),
        "total_revenue": round(revenue, 2),
        "total_expenses": round(expenses, 2),
        "net_profit_simple": round(profit_simple, 2),
        "expense_ratio": round(expense_ratio, 2) if expense_ratio is not None else None,
    }


@app.get("/kpis/monthly")
def kpis_monthly(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_business_owner(db, business_id, current_user.id)
    txns = db.query(Transaction).filter(Transaction.business_id == business_id).all()
    if not txns:
        return []

    buckets = {}
    for t in txns:
        m = t.txn_date.strftime("%Y-%m")
        if m not in buckets:
            buckets[m] = {"month": m, "revenue": 0.0, "expenses": 0.0, "profit_simple": 0.0}

        if (t.direction or "").lower() == "credit" and (t.category or "").lower() == "revenue":
            buckets[m]["revenue"] += float(t.amount)
        if (t.direction or "").lower() == "debit":
            buckets[m]["expenses"] += float(t.amount)

    out = []
    for m in sorted(buckets.keys()):
        b = buckets[m]
        b["profit_simple"] = b["revenue"] - b["expenses"]
        out.append({k: (round(v, 2) if isinstance(v, float) else v) for k, v in b.items()})
    return out


@app.get("/score")
def score(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_business_owner(db, business_id, current_user.id)
    txns = db.query(Transaction).filter(Transaction.business_id == business_id).all()
    if not txns:
        return {"health_score": 0, "rating": "No Data"}

    inflow = sum(float(t.amount) for t in txns if (t.direction or "").lower() == "credit")
    outflow = sum(float(t.amount) for t in txns if (t.direction or "").lower() == "debit")
    revenue = sum(float(t.amount) for t in txns if (t.category or "").lower() == "revenue" and (t.direction or "").lower() == "credit")
    expenses = sum(float(t.amount) for t in txns if (t.direction or "").lower() == "debit")

    net_cf = inflow - outflow
    profit = revenue - expenses

    s = 0
    s += 30 if net_cf > 0 else 10
    s += 30 if profit > 0 else 10
    s += 20 if len(txns) >= 20 else 10
    s += 20 if revenue > 0 else 5

    rating = "Excellent" if s >= 80 else "Good" if s >= 60 else "Average" if s >= 40 else "Poor"
    return {"health_score": int(s), "rating": rating}


@app.get("/risks")
def risks(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_business_owner(db, business_id, current_user.id)
    txns = db.query(Transaction).filter(Transaction.business_id == business_id).all()
    if not txns:
        return [{"type": "no_data", "severity": "high", "message": "No transactions uploaded"}]

    inflow = sum(float(t.amount) for t in txns if (t.direction or "").lower() == "credit")
    outflow = sum(float(t.amount) for t in txns if (t.direction or "").lower() == "debit")
    revenue = sum(float(t.amount) for t in txns if (t.category or "").lower() == "revenue" and (t.direction or "").lower() == "credit")
    expenses = sum(float(t.amount) for t in txns if (t.direction or "").lower() == "debit")

    net_cf = inflow - outflow
    out_list = []

    if net_cf < 0:
        out_list.append({"type": "cashflow_risk", "severity": "high", "message": "Negative cashflow detected"})
    if revenue > 0 and expenses / revenue > 0.8:
        out_list.append({"type": "high_expense", "severity": "medium", "message": "Expenses are > 80% of revenue"})
    if len(txns) < 10:
        out_list.append({"type": "low_data", "severity": "low", "message": "Few transactions; insights may be weak"})

    if not out_list:
        out_list.append({"type": "no_major_risks", "severity": "info", "message": "No major risks detected"})
    return out_list


@app.get("/recommendations")
def recommendations(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_business_owner(db, business_id, current_user.id)
    txns = db.query(Transaction).filter(Transaction.business_id == business_id).all()
    if not txns:
        return ["Upload transactions to get recommendations"]

    inflow = sum(float(t.amount) for t in txns if (t.direction or "").lower() == "credit")
    outflow = sum(float(t.amount) for t in txns if (t.direction or "").lower() == "debit")
    revenue = sum(float(t.amount) for t in txns if (t.category or "").lower() == "revenue" and (t.direction or "").lower() == "credit")
    expenses = sum(float(t.amount) for t in txns if (t.direction or "").lower() == "debit")

    recs = []
    if inflow < outflow:
        recs.append("Reduce expenses or improve collections to fix negative cashflow")
    if revenue > 0 and (expenses / revenue) > 0.7:
        recs.append("Control operating expenses (rent, salary, utilities, marketing)")
    if revenue > 0 and inflow < revenue:
        recs.append("Speed up customer payments (reminders, shorter credit terms)")
    if not recs:
        recs.append("Business looks stable. Track KPIs monthly and keep emergency cash reserves")
    return recs


@app.get("/forecast")
def forecast(
    business_id: int,
    months: int = 3,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_business_owner(db, business_id, current_user.id)

    monthly = kpis_monthly(business_id, db, current_user)
    if not monthly:
        return {"business_id": business_id, "forecast": [], "message": "No data to forecast"}

    last_n = monthly[-3:] if len(monthly) >= 3 else monthly
    avg_rev = sum(x["revenue"] for x in last_n) / len(last_n)
    avg_profit = sum(x["profit_simple"] for x in last_n) / len(last_n)

    last_month = monthly[-1]["month"]
    out = []
    for i in range(1, months + 1):
        m = _add_months_ym(last_month, i)
        out.append({"month": m, "forecast_revenue": round(avg_rev, 2), "forecast_net_cashflow": round(avg_profit, 2)})

    return {"business_id": business_id, "forecast": out, "based_on_months": [x["month"] for x in last_n]}


@app.get("/ai/summary")
def ai_summary(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_business_owner(db, business_id, current_user.id)

    txns = db.query(Transaction).filter(Transaction.business_id == business_id).all()
    revenue = sum(float(t.amount) for t in txns if (t.category or "").lower() == "revenue" and (t.direction or "").lower() == "credit")
    expenses = sum(float(t.amount) for t in txns if (t.direction or "").lower() == "debit")
    profit = revenue - expenses

    return {
        "summary": f"Revenue {revenue:.2f}, Expenses {expenses:.2f}, Profit {profit:.2f}. Maintain positive cashflow.",
        "model": "fallback",
    }


@app.post("/bank/sync")
def bank_sync(
    business_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    import random

    require_business_owner(db, business_id, current_user.id)

    inserted = 0
    for _ in range(5):
        amt = random.randint(1000, 15000)
        direction = random.choice(["credit", "debit"])
        category = "revenue" if direction == "credit" else "expense"

        db.add(
            Transaction(
                business_id=business_id,
                txn_date=date.today() - timedelta(days=random.randint(0, 5)),
                description="Bank Auto Sync",
                category=category,
                direction=direction,
                amount=float(amt),
            )
        )
        inserted += 1

    db.commit()

    log_audit(
        db,
        request,
        user_id=current_user.id,
        business_id=business_id,
        action="BANK_SYNC",
        entity="transaction",
        payload={"inserted": inserted},
    )

    return {"synced": inserted}
