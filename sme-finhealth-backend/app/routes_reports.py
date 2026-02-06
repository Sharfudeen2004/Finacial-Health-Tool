from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO

from .database import get_db
from .auth import get_current_user
from .models import User, Transaction, Business
from .rbac import require_role

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get("/pdf")
def report_pdf(
    business_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(db, business_id, current_user.id, {"owner", "accountant"})

    biz = db.query(Business).filter(Business.id == business_id).first()
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

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    y = h - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "SME Financial Health Report")
    y -= 20

    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Business: {biz.name if biz else business_id}")
    y -= 16
    c.drawString(50, y, f"Total inflow: {inflow:.2f}")
    y -= 16
    c.drawString(50, y, f"Total outflow: {outflow:.2f}")
    y -= 16
    c.drawString(50, y, f"Net cashflow: {net:.2f}")
    y -= 24

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Recent Transactions (last 20)")
    y -= 16
    c.setFont("Helvetica", 10)

    for t in txns[:20]:
        line = f"{t.txn_date} | {t.direction} | {t.category} | {t.amount:.2f} | {t.description}"
        c.drawString(50, y, line[:110])
        y -= 14
        if y < 60:
            c.showPage()
            y = h - 50
            c.setFont("Helvetica", 10)

    c.showPage()
    c.save()

    pdf = buf.getvalue()
    buf.close()

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report_business_{business_id}.pdf"'},
    )
