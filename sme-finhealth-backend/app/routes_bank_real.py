from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime

from .database import get_db
from .auth import get_current_user
from .models import User, Transaction
from .audit import log_audit
from .rbac import require_role
from .integrations_razorpayx import list_transactions

router = APIRouter(prefix="/bank", tags=["Bank"])

@router.post("/razorpayx/sync")
def sync_razorpayx(
    business_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # allow owner + accountant
    require_role(db, business_id, current_user.id, {"owner", "accountant"})

    try:
        data = list_transactions(count=25, skip=0)
    except Exception as e:
        raise HTTPException(400, f"RazorpayX sync failed: {e}")

    inserted = 0
    items = data.get("items", []) or data.get("items", [])  # depends on response
    for it in items:
        # You MUST map fields based on your RazorpayX response
        amt = float(it.get("amount", 0)) / 100.0 if it.get("amount") else 0.0
        created = it.get("created_at")
        txn_date = datetime.fromtimestamp(created).date() if created else datetime.today().date()
        direction = "debit" if it.get("type") in ["debit"] else "credit"
        category = "expense" if direction == "debit" else "revenue"
        desc = (it.get("description") or it.get("narration") or "RazorpayX").strip()

        db.add(Transaction(
            business_id=business_id,
            txn_date=txn_date,
            description=desc[:255],
            category=category,
            direction=direction,
            amount=abs(amt),
        ))
        inserted += 1

    db.commit()

    log_audit(
        db, request,
        user_id=current_user.id,
        business_id=business_id,
        action="RAZORPAYX_SYNC",
        entity="bank",
        payload={"inserted": inserted},
    )
    return {"synced": inserted}
