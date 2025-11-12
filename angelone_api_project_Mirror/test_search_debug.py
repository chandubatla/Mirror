# place_nifty_by_token.py
"""
Place a dry-run or real order for NIFTY using known token (26000).
DRY_RUN defaults to True (1). To actually place an order set DRY_RUN=0 in your .env.

.env variables used:
    SOURCE_API_KEY
    SOURCE_CLIENT_ID
    SOURCE_MPIN
    SOURCE_TOTP_TOKEN
    DRY_RUN (optional, default "1")
    ORDER_SIDE (BUY/SELL, default BUY)
    ORDER_QTY (int, default 1)
    ORDER_PRODUCT (CNC/MIS/NRML, default MIS)
"""

import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
import pyotp
import traceback

# import SmartConnect (try common package names)
try:
    from SmartApi import SmartConnect
except Exception:
    from SmartApi import SmartConnect

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
load_dotenv(os.path.join(BASE_DIR, "..", ".env"))
load_dotenv(dotenv_path="/root/config.env", override=False)

API_KEY = os.getenv("SOURCE_API_KEY")
CLIENT_ID = os.getenv("SOURCE_CLIENT_ID")
MPIN = os.getenv("SOURCE_MPIN")
TOTP_TOKEN = os.getenv("SOURCE_TOTP_TOKEN")

DRY_RUN = os.getenv("DRY_RUN", "1") == "1"
ORDER_SIDE = os.getenv("ORDER_SIDE", "BUY").upper()
ORDER_QTY = int(os.getenv("ORDER_QTY", "1"))
ORDER_PRODUCT = os.getenv("ORDER_PRODUCT", "MIS")  # CNC / MIS / NRML
ORDER_TYPE = os.getenv("ORDER_TYPE", "MARKET").upper()  # MARKET or LIMIT
ORDER_PRICE = os.getenv("ORDER_PRICE")  # used if LIMIT
# Known NIFTY token (use token if search is failing/rate-limited)
NIFTY_TOKEN = os.getenv("NIFTY_TOKEN", "26000")
# Exchange to use (adjust if your wrapper expects token-based exchange names)
DEFAULT_EXCHANGE = os.getenv("NIFTY_EXCHANGE", "NSE")

if not all([API_KEY, CLIENT_ID, MPIN, TOTP_TOKEN]):
    raise SystemExit("Missing required env vars: SOURCE_API_KEY, SOURCE_CLIENT_ID, SOURCE_MPIN, SOURCE_TOTP_TOKEN")

def auth_client():
    totp = pyotp.TOTP(TOTP_TOKEN).now()
    print(f"[{datetime.now()}] Using TOTP:", totp)
    client = SmartConnect(api_key=API_KEY)
    try:
        sess = client.generateSession(CLIENT_ID, MPIN, totp)
    except Exception as e:
        raise SystemExit(f"generateSession failed: {e}")
    if not sess or not sess.get("status"):
        raise SystemExit(f"Authentication failed: {sess}")
    print("Authenticated. clientcode:", sess["data"].get("clientcode"))
    return client, sess

def exponential_backoff(func, *args, retries=4, base_delay=0.5, **kwargs):
    """Call func(*args, **kwargs) with simple exponential backoff on exception."""
    delay = base_delay
    for attempt in range(1, retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # If server indicated rate-limit, bubble that message and wait longer
            msg = str(e)
            print(f"Attempt {attempt} failed: {msg}")
            if attempt == retries:
                raise
            time.sleep(delay)
            delay *= 2
    # unreachable
    raise RuntimeError("unhandled backoff exit")

def prepare_payload_from_token(token=NIFTY_TOKEN, exchange=DEFAULT_EXCHANGE):
    """Prepare an order payload using token (many wrappers accept token and exchange)."""
    payload = {
        "exchange": exchange,
        "token": str(token),
        "transactiontype": ORDER_SIDE,  # BUY / SELL
        "order_type": ORDER_TYPE,       # MARKET / LIMIT
        "product": ORDER_PRODUCT,       # CNC / MIS / NRML
        "quantity": ORDER_QTY,
    }
    if ORDER_TYPE == "LIMIT":
        if not ORDER_PRICE:
            raise SystemExit("ORDER_PRICE required for LIMIT orders")
        payload["price"] = float(ORDER_PRICE)
    return payload

def try_place_order(client, payload):
    """Try the common variants of placeOrder call for different wrappers."""
    print("Attempting to place order with payload (or dry-run):")
    print(json.dumps(payload, indent=2))
    if DRY_RUN:
        print("DRY_RUN is enabled — not sending to API.")
        return {"status": "DRY_RUN", "payload": payload}

    # Try direct single-argument dict call
    try:
        print("Calling client.placeOrder(payload)...")
        resp = client.placeOrder(payload)
        print("placeOrder response:", resp)
        return resp
    except TypeError as te:
        print("client.placeOrder(payload) raised TypeError:", te)
    except Exception as e:
        print("placeOrder failed:", e)
        traceback.print_exc()

    # Try expanded keyword args fallback
    try:
        print("Calling placeOrder with expanded kwargs...")
        resp = client.placeOrder(
            exchange=payload.get("exchange"),
            token=payload.get("token"),
            tradingsymbol=payload.get("tradingsymbol"),
            transactiontype=payload.get("transactiontype"),
            order_type=payload.get("order_type"),
            product=payload.get("product"),
            quantity=payload.get("quantity"),
            price=payload.get("price", 0)
        )
        print("placeOrder response (expanded):", resp)
        return resp
    except Exception as e:
        print("Expanded placeOrder also failed:", e)
        traceback.print_exc()
        raise

def main():
    client, sess = auth_client()

    # Prepare payload (using token, avoids searchScrip)
    payload = prepare_payload_from_token()

    # Print session-exchanges for your awareness (don't spam)
    print("Session exchanges sample:", sess["data"].get("exchanges"))

    # As extra safety: confirm DRY_RUN before attempting
    if DRY_RUN:
        print("DRY_RUN is ON. Set DRY_RUN=0 in your .env to actually place the order.")
    else:
        print("DRY_RUN is OFF; this *will* place an order. Proceeding...")

    # Place order with exponential backoff to handle transient errors
    try:
        resp = exponential_backoff(try_place_order, client, payload, retries=3, base_delay=1.0)
        print("Final response:", resp)
    except Exception as e:
        print("Order attempt failed after retries:", e)

if __name__ == "__main__":
    main()
