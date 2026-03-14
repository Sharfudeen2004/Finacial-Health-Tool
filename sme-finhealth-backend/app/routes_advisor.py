from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .database import get_db
from .auth import get_current_user
from .models import User, Business, Transaction
from .audit import log_audit
from .llm_openai import advisor_reply

router = APIRouter(prefix="/advisor", tags=["Advisor"])

def require_business_owner(db: Session, business_id: int, user_id: int):
    biz = db.query(Business).filter(Business.id == business_id).first()
    if not biz:
        raise HTTPException(404, "Business not found")
    if getattr(biz, "owner_user_id", None) != user_id:
        raise HTTPException(403, "Not allowed")
    return biz

@router.post("/chat")
def chat(
    payload: dict,
    request: Request,
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_business_owner(db, business_id, current_user.id)

    question = (payload.get("message") or "").strip()
    if not question:
        raise HTTPException(400, "message is required")

    # lightweight context from DB (MVP)
    txns = (
        db.query(Transaction)
        .filter(Transaction.business_id == business_id)
        .order_by(Transaction.txn_date.desc())
        .limit(200)
        .all()
    )
    inflow = sum(float(t.amount) for t in txns if (t.direction or "").lower() == "credit")
    outflow = sum(float(t.amount) for t in txns if (t.direction or "").lower() == "debit")
    net = inflow - outflow

    system = (
        "You are a financial advisor for Indian SMEs. "
        "Give actionable, simple steps in bullet points. "
        "Do not invent data; only use provided numbers."
    )
    context = f"Recent totals (last 200 txns): inflow={inflow:.2f}, outflow={outflow:.2f}, net_cashflow={net:.2f}."

    answer = advisor_reply(system, f"{context}\n\nUser question: {question}")

    log_audit(
        db, request,
        user_id=current_user.id,
        business_id=business_id,
        action="ADVISOR_CHAT",
        entity="ai",
        payload={"question": question[:500]},
    )
    return {"reply": answer}
