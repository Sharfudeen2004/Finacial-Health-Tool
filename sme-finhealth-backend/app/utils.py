import pandas as pd

# Column aliases (extend anytime)
COLUMN_ALIASES = {
    "date": ["date", "txn_date", "transaction_date", "value_date", "posting_date"],
    "description": ["description", "narration", "particulars", "details", "remark", "remarks"],
    "amount": ["amount", "amt", "transaction_amount"],
    "debit": ["debit", "dr", "withdrawal", "withdrawals"],
    "credit": ["credit", "cr", "deposit", "deposits"],
    "category": ["category", "expense_category", "ledger", "account", "head"],
}

def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    cols = {str(c).strip().lower(): c for c in df.columns}
    for key in candidates:
        if key.lower() in cols:
            return cols[key.lower()]
    return None

def read_file_to_df(filename: str, content: bytes) -> pd.DataFrame:
    if filename.lower().endswith(".csv"):
        return pd.read_csv(pd.io.common.BytesIO(content))
    if filename.lower().endswith(".xlsx") or filename.lower().endswith(".xls"):
        return pd.read_excel(pd.io.common.BytesIO(content))
    raise ValueError("Only CSV/XLSX supported in MVP")

def normalize_transactions(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Normalize into schema:
    txn_date, description, amount(abs), direction(credit/debit), category
    """
    original_cols = list(df.columns)
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    date_col = _find_col(df, COLUMN_ALIASES["date"])
    desc_col = _find_col(df, COLUMN_ALIASES["description"])
    amt_col = _find_col(df, COLUMN_ALIASES["amount"])
    debit_col = _find_col(df, COLUMN_ALIASES["debit"])
    credit_col = _find_col(df, COLUMN_ALIASES["credit"])
    cat_col = _find_col(df, COLUMN_ALIASES["category"])

    detected = {
        "date_col": date_col,
        "description_col": desc_col,
        "amount_col": amt_col,
        "debit_col": debit_col,
        "credit_col": credit_col,
        "category_col": cat_col,
        "original_columns": original_cols,
    }

    if not date_col:
        raise ValueError("Could not detect a date column. Use 'date' or 'transaction_date'.")

    if not desc_col:
        df["_desc_fallback"] = ""
        desc_col = "_desc_fallback"

    # amount + direction
    if amt_col:
        s = pd.to_numeric(df[amt_col], errors="coerce").fillna(0)
        direction = s.apply(lambda x: "credit" if x >= 0 else "debit")
        amount = s.abs()
    else:
        if not (debit_col or credit_col):
            raise ValueError("Could not detect amount OR debit/credit columns.")
        debit = pd.to_numeric(df[debit_col], errors="coerce").fillna(0) if debit_col else 0
        credit = pd.to_numeric(df[credit_col], errors="coerce").fillna(0) if credit_col else 0
        direction = (credit > debit).apply(lambda x: "credit" if x else "debit")
        amount = (credit - debit).abs()

    txn_date = pd.to_datetime(df[date_col], errors="coerce").dt.date
    if txn_date.isna().any():
        raise ValueError("Some dates could not be parsed. Check your date format.")

    category = df[cat_col].astype(str) if cat_col else "uncategorized"

    out = pd.DataFrame({
        "txn_date": txn_date,
        "description": df[desc_col].astype(str).fillna(""),
        "amount": amount,
        "direction": direction,
        "category": category.fillna("uncategorized"),
    })

    out["description"] = out["description"].str.strip()
    out["category"] = out["category"].astype(str).str.strip().str.lower()

    return out, detected

# -------- KPI Helpers --------

def classify_amounts(direction: str, amount: float) -> tuple[float, float]:
    """Return (inflow, outflow). amount is ABS stored in DB."""
    if (direction or "").lower() == "credit":
        return float(amount), 0.0
    return 0.0, float(amount)

def is_revenue(category: str) -> bool:
    c = (category or "").strip().lower()
    return c in {"revenue", "sales", "income", "turnover"}

def is_cogs(category: str) -> bool:
    c = (category or "").strip().lower()
    return c in {"cogs", "cost_of_goods_sold", "inventory", "purchases", "purchase"}

def is_expense(category: str) -> bool:
    c = (category or "").strip().lower()
    return c in {
        "expense", "expenses",
        "rent", "salary", "utilities", "admin", "marketing",
        "transport", "logistics", "repair", "maintenance", "office"
    }
