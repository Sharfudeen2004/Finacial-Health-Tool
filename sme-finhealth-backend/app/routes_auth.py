# app/routes_auth.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .models import User, Business
from .models_rbac import BusinessUser
from .auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


# -----------------------------
# Helpers
# -----------------------------
def _user_to_dict(u: User) -> dict:
    return {
        "id": u.id,
        "full_name": getattr(u, "full_name", None),
        "email": u.email,
        "created_at": u.created_at.isoformat() if getattr(u, "created_at", None) else None,
    }


def _business_to_dict(b: Business) -> dict:
    return {
        "id": b.id,
        "name": b.name,
        "industry": getattr(b, "industry", None),
        "owner_user_id": getattr(b, "owner_user_id", None),
        "created_at": b.created_at.isoformat() if getattr(b, "created_at", None) else None,
    }


# -----------------------------
# Auth APIs
# -----------------------------
@router.post("/register")
def register(payload: dict, db: Session = Depends(get_db)):
    """
    Body:
    {
      "full_name": "Sharfu",
      "email": "test@gmail.com",
      "password": "Test@123"
    }

    Returns:
    { "access_token": "...", "token_type": "bearer" }
    """
    full_name = (payload.get("full_name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        raise HTTPException(status_code=400, detail="email and password are required")

    exists = db.query(User).filter(User.email == email).first()
    if exists:
        raise HTTPException(status_code=400, detail="Email already registered")

    u = User(
        full_name=full_name,
        email=email,
        password_hash=hash_password(password),
    )
    db.add(u)
    db.commit()
    db.refresh(u)

    # Create default business for new user
    biz = Business(
        name=f"{full_name or 'My'} Business",
        owner_user_id=u.id,
    )
    db.add(biz)
    db.commit()
    db.refresh(biz)

    # RBAC link: owner
    db.add(BusinessUser(business_id=biz.id, user_id=u.id, role="owner"))
    db.commit()

    token = create_access_token({"sub": str(u.id)})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login")
def login(payload: dict, db: Session = Depends(get_db)):
    """
    Body:
    {
      "email": "test@gmail.com",
      "password": "Test@123"
    }

    Returns:
    { "access_token": "...", "token_type": "bearer" }
    """
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""

    if not email or not password:
        raise HTTPException(status_code=400, detail="email and password are required")

    u = db.query(User).filter(User.email == email).first()
    if not u:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(password, u.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": str(u.id)})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return _user_to_dict(current_user)


# -----------------------------
# Businesses
# -----------------------------
@router.get("/businesses")
def list_businesses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns businesses the user has access to (RBAC).
    """
    links = db.query(BusinessUser).filter(BusinessUser.user_id == current_user.id).all()
    if not links:
        return []

    biz_ids = [x.business_id for x in links]
    biz_rows = db.query(Business).filter(Business.id.in_(biz_ids)).all()

    # attach role
    role_by_biz = {x.business_id: x.role for x in links}
    out = []
    for b in biz_rows:
        item = _business_to_dict(b)
        item["role"] = role_by_biz.get(b.id)
        out.append(item)
    return out


@router.post("/businesses")
def create_business(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Body:
    { "name": "ABC Stores", "industry": "Retail" }

    Creates business and makes current user owner (RBAC).
    """
    name = (payload.get("name") or "").strip()
    industry = (payload.get("industry") or "").strip() if payload.get("industry") else None

    if not name:
        raise HTTPException(status_code=400, detail="name is required")

    biz = Business(name=name, industry=industry, owner_user_id=current_user.id)
    db.add(biz)
    db.commit()
    db.refresh(biz)

    # RBAC link: owner
    db.add(BusinessUser(business_id=biz.id, user_id=current_user.id, role="owner"))
    db.commit()

    return _business_to_dict(biz)
