import io
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from PIL import Image

from .database import get_db
from .models import Transaction, Business, User
from .models_invoice import Invoice
from .auth import get_current_user
from .audit import log_audit

router = APIRouter(prefix="/invoice", tags=["Invoice OCR"])


def require_business_owner(db: Session, business_id: int, user_id: int):
    biz = db.query(Business).filter(Business.id == business_id).first()
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")
    if getattr(biz, "owner_user_id", None) != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")
    return biz


def _parse_date_from_text(text: str) -> Optional[datetime.date]:
    # common invoice date patterns
    patterns = [
        r"(\d{4}-\d{2}-\d{2})",
        r"(\d{2}/\d{2}/\d{4})",
        r"(\d{2}-\d{2}-\d{4})",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            s = m.group(1)
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    return datetime.strptime(s, fmt).date()
                except Exception:
                    pass
    return None


def _parse_total_amount(text: str) -> Optional[float]:
    # try to detect "Total" or "Grand Total"
    # fallback: biggest amount number
    t = text.replace(",", " ")
    m = re.search(r"(grand\s*total|total\s*amount|total)\s*[:\-]?\s*₹?\s*([0-9]+(\.[0-9]{1,2})?)", t, re.IGNORECASE)
    if m:
        return float(m.group(2))

    nums = re.findall(r"\b[0-9]{3,}(?:\.[0-9]{1,2})?\b", t)
    if not nums:
        return None
    try:
        return float(max(nums, key=lambda x: float(x)))
    except Exception:
        return None


def _parse_invoice_number(text: str) -> Optional[str]:
    m = re.search(r"(invoice\s*no\.?|inv\s*no\.?|invoice\s*#)\s*[:\-]?\s*([A-Za-z0-9\-\/]+)", text, re.IGNORECASE)
    if m:
        return m.group(2)[:64]
    return None


def _parse_gstin(text: str) -> Optional[str]:
    # GSTIN = 15 chars
    m = re.search(r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[A-Z0-9]{3})\b", text.upper())
    return m.group(1) if m else None


def _parse_vendor_name(text: str) -> Optional[str]:
    # MVP heuristic: first non-empty line
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None
    return lines[0][:255]


def ocr_from_image(img: Image.Image) -> str:
    try:
        import pytesseract
    except Exception:
        raise HTTPException(400, detail="pytesseract not installed. Run: pip install pytesseract")

    # If tesseract exe not in PATH, set it like:
    # pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    return pytesseract.image_to_string(img)


def ocr_pdf_bytes(pdf_bytes: bytes) -> str:
    try:
        from pdf2image import convert_from_bytes
    except Exception:
        raise HTTPException(400, detail="pdf2image not installed. Run: pip install pdf2image")

    images = convert_from_bytes(pdf_bytes, dpi=300)
    texts = []
    for im in images[:5]:  # MVP: first 5 pages only
        texts.append(ocr_from_image(im))
    return "\n".join(texts)


@router.post("/ocr/preview")
async def invoice_ocr_preview(
    business_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_business_owner(db, business_id, current_user.id)
    raw = await file.read()
    name = (file.filename or "").lower()

    if name.endswith(".pdf"):
        text = ocr_pdf_bytes(raw)
    elif name.endswith(".png") or name.endswith(".jpg") or name.endswith(".jpeg"):
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        text = ocr_from_image(img)
    else:
        raise HTTPException(400, detail="Upload PDF/PNG/JPG only for OCR")

    parsed = {
        "vendor_name": _parse_vendor_name(text),
        "vendor_gstin": _parse_gstin(text),
        "invoice_number": _parse_invoice_number(text),
        "invoice_date": str(_parse_date_from_text(text)) if _parse_date_from_text(text) else None,
        "total_amount": _parse_total_amount(text),
        "raw_text_preview": text[:1200],
    }
    return parsed


@router.post("/ocr/commit")
async def invoice_ocr_commit(
    business_id: int,
    request: Request,
    create_transaction: bool = True,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_business_owner(db, business_id, current_user.id)
    raw = await file.read()
    name = (file.filename or "").lower()

    if name.endswith(".pdf"):
        text = ocr_pdf_bytes(raw)
    elif name.endswith(".png") or name.endswith(".jpg") or name.endswith(".jpeg"):
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        text = ocr_from_image(img)
    else:
        raise HTTPException(400, detail="Upload PDF/PNG/JPG only for OCR")

    inv_date = _parse_date_from_text(text)
    total = _parse_total_amount(text)
    inv_no = _parse_invoice_number(text)
    gstin = _parse_gstin(text)
    vendor = _parse_vendor_name(text)

    inv = Invoice(
        business_id=business_id,
        vendor_name=vendor,
        vendor_gstin=gstin,
        invoice_number=inv_no,
        invoice_date=inv_date,
        total_amount=total,
        raw_text=text,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)

    # Optional: create transaction as expense (default)
    if create_transaction and total:
        txn_date = inv_date or datetime.today().date()
        db.add(
            Transaction(
                business_id=business_id,
                txn_date=txn_date,
                description=f"Invoice OCR {inv_no or ''} {vendor or ''}".strip(),
                category="expense",
                direction="debit",
                amount=float(total),
            )
        )
        db.commit()

    log_audit(
        db,
        request,
        user_id=current_user.id,
        business_id=business_id,
        action="INVOICE_OCR_COMMIT",
        entity="invoice",
        entity_id=inv.id,
        payload={"filename": file.filename, "total_amount": total, "invoice_number": inv_no},
    )

    return {"invoice_id": inv.id, "parsed_total": total, "created_transaction": bool(create_transaction and total)}
