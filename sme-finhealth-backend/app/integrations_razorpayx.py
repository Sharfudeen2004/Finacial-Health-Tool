import os
import requests

BASE = "https://api.razorpay.com/v1"

def list_transactions(count: int = 25, skip: int = 0) -> dict:
    key = os.getenv("RAZORPAYX_KEY_ID")
    secret = os.getenv("RAZORPAYX_KEY_SECRET")
    if not key or not secret:
        raise RuntimeError("Missing RazorpayX keys")

    # NOTE: Endpoint depends on your RazorpayX product access.
    # Use the RazorpayX Transaction APIs / Account Statement APIs.
    r = requests.get(
        f"{BASE}/transactions",
        params={"count": count, "skip": skip},
        auth=(key, secret),
        timeout=20,
    )
    r.raise_for_status()
    return r.json()
