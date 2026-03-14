# app/routes_gst.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime

from .database import get_db
from .models import Transaction, Business, User
from .auth import get_current_user
from .audit import log_audit

router = APIRouter(prefix="/gst", tags=["GST"])


# =====================================
# Helper
# =====================================
def require_business_owner(db: Session, business_id: int, user_id: int):
    biz = db.query(Business).filter(Business.id == business_id).first()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")

    if getattr(biz, "owner_user_id", None) != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")

    return biz


def parse_date(d):
    return datetime.strptime(d, "%Y-%m-%d").date()


# =====================================
# 1️⃣ GST IMPORT JSON
# =====================================
@router.post("/import")
def gst_import(
    payload: dict,
    request: Request,
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    JSON format:
    {
      "invoices": [
        {
          "date": "2026-01-10",
          "description": "GST Sale - Invoice 1",
          "amount": 25000,
          "type": "sale"
        }
      ]
    }
    """

    require_business_owner(db, business_id, current_user.id)

    invoices = payload.get("invoices", [])
    if not invoices:
        raise HTTPException(400, "No invoices provided")

    inserted = 0

    for inv in invoices:
        date = parse_date(inv["date"])
        amount = float(inv["amount"])
        desc = inv.get("description", "GST Entry")

        ttype = inv.get("type", "sale").lower()

        direction = "credit" if ttype == "sale" else "debit"
        category = "revenue" if direction == "credit" else "expense"

        db.add(
            Transaction(
                business_id=business_id,
                txn_date=date,
                description=desc,
                category=category,
                direction=direction,
                amount=amount,
            )
        )

        inserted += 1

    db.commit()

    # ✅ Audit log
    log_audit(
        db,
        request,
        user_id=current_user.id,
        business_id=business_id,
        action="GST_IMPORT",
        entity="gst",
        payload={"inserted": inserted},
    )

    return {"inserted": inserted}


# =====================================
# 2️⃣ GST MONTHLY SUMMARY
# =====================================
@router.get("/summary")
def gst_summary(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns:
    [
      { month: 2026-01, gst_sales: 50000, gst_purchases: 30000 }
    ]
    """

    require_business_owner(db, business_id, current_user.id)

    txns = (
        db.query(Transaction)
        .filter(Transaction.business_id == business_id)
        .all()
    )

    if not txns:
        return []

    buckets = {}

    for t in txns:
        month = t.txn_date.strftime("%Y-%m")

        if month not in buckets:
            buckets[month] = {
                "month": month,
                "gst_sales": 0.0,
                "gst_purchases": 0.0,
            }

        desc = (t.description or "").lower()

        if "gst sale" in desc or t.category == "revenue":
            if t.direction == "credit":
                buckets[month]["gst_sales"] += float(t.amount)

        if "gst purchase" in desc or t.category == "expense":
            if t.direction == "debit":
                buckets[month]["gst_purchases"] += float(t.amount)

    out = []
    for m in sorted(buckets.keys()):
        b = buckets[m]
        out.append(
            {
                "month": m,
                "gst_sales": round(b["gst_sales"], 2),
                "gst_purchases": round(b["gst_purchases"], 2),
            }
        )

    return out
