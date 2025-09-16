# 🚀 Full `utils.py` (with Forgot Password email support)

```python
# utils.py
import os
import json
import hashlib
import smtplib
import secrets
import string
from datetime import datetime
from typing import Tuple
from email.message import EmailMessage

import pandas as pd
import streamlit as st

# ----------------------
# 📌 Constants
# ----------------------

REQUIRED_COLUMNS = [
    "REQ#", "ITEM", "NUMBER OF ITEM", "AMOUNT PER ITEM", "TOTAL",
    "VENDOR", "CAT #", "GRANT USED", "PO SOURCE", "PO #",
    "NOTES", "ORDERED BY", "DATE ORDERED", "DATE RECEIVED",
    "RECEIVED BY", "LOCATION KEPT", "REQUESTED BY", "TIME RECEIVED"
]

USERS_FILE = "data/users.json"
DATA_PATH = os.getenv("REQUIVA_DATA_PATH", "data/orders.csv")
FIREBASE_CREDENTIAL_PATH = "/etc/secrets/firebase-service-account.json"
RESET_TOKEN_FILE = "data/reset_tokens.json"

EMAIL_USER = st.secrets["email_user"]
EMAIL_PASS = st.secrets["email_pass"]
SMTP_SERVER = st.secrets["smtp_server"]
SMTP_PORT = int(st.secrets["smtp_port"])

# ----------------------
# 🔐 Firebase Setup
# ----------------------

def _init_firestore_from_file():
    if not os.path.exists(FIREBASE_CREDENTIAL_PATH):
        st.warning("⚠️ Firebase service account file not found. Using local CSV.")
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        with open(FIREBASE_CREDENTIAL_PATH, "r") as f:
            sa_info = json.load(f)
        cred = credentials.Certificate(sa_info)

        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)

        return firestore.client()
    except Exception as e:
        st.warning(f"⚠️ Firebase init failed. Using CSV.\n\nDetails: {e}")
        return None

db = _init_firestore_from_file()
USE_FIRESTORE = db is not None

# ----------------------
# 📦 Data Functions
# ----------------------

def ensure_data_file():
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    if not os.path.exists(DATA_PATH):
        pd.DataFrame(columns=REQUIRED_COLUMNS).to_csv(DATA_PATH, index=False)

def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = None
    return df[REQUIRED_COLUMNS]

def load_orders() -> pd.DataFrame:
    if USE_FIRESTORE and db:
        docs = db.collection("requiva_orders").stream()
        rows = [d.to_dict() for d in docs]
        df = pd.DataFrame(rows)
        return _ensure_columns(df) if not df.empty else pd.DataFrame(columns=REQUIRED_COLUMNS)
    else:
        ensure_data_file()
        df = pd.read_csv(DATA_PATH)
        return _ensure_columns(df)

def save_orders(df: pd.DataFrame):
    df = _ensure_columns(df.copy())
    if USE_FIRESTORE and db:
        from google.cloud import firestore as _fs
        batch = db.batch()
        col_ref = db.collection("requiva_orders")
        for _, row in df.iterrows():
            req_id = str(row["REQ#"])
            if not req_id or req_id.lower() == "nan":
                continue
            doc = {k: (None if pd.isna(v) else v) for k, v in row.to_dict().items()}
            batch.set(col_ref.document(req_id), doc, merge=True)
        batch.commit()
    else:
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        df.to_csv(DATA_PATH, index=False)

# ----------------------
# 🧮 Utility Functions
# ----------------------

def gen_req_id(df: pd.DataFrame) -> str:
    year = datetime.now().strftime("%Y")
    prefix = f"REQ-{year}-"
    existing = df["REQ#"].dropna().astype(str).tolist()
    nums = [int(x.split("-")[-1]) for x in existing if x.startswith(prefix) and x.split("-")[-1].isdigit()]
    next_num = (max(nums) + 1) if nums else 1
    return f"{prefix}{next_num:04d}"

def compute_total(qty: float, unit_price: float) -> float:
    try:
        return round(float(qty) * float(unit_price), 2)
    except Exception:
        return 0.0

def validate_order(item: str, qty, price, vendor: str) -> Tuple[bool, str]:
    if not item or str(item).strip() == "":
        return False, "ITEM is required."
    try:
        q = float(qty)
        if q < 0:
            return False, "NUMBER OF ITEM must be >= 0."
    except Exception:
        return False, "NUMBER OF ITEM must be a number."
    try:
        p = float(price)
        if p < 0:
            return False, "AMOUNT PER ITEM must be >= 0."
    except Exception:
        return False, "AMOUNT PER ITEM must be a number."
    if not vendor or str(vendor).strip() == "":
        return False, "VENDOR is required."
    return True, ""

# ----------------------
# 🔐 Auth (Email/Password with Role)
# ----------------------

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def is_admin(email: str) -> bool:
    return email.lower() == "ogunbowaleadeola@gmail.com"

def generate_token(length=32):
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(length))

def load_reset_tokens():
    if not os.path.exists(RESET_TOKEN_FILE):
        return {}
    with open(RESET_TOKEN_FILE, "r") as f:
        return json.load(f)

def save_reset_tokens(tokens):
    os.makedirs(os.path.dirname(RESET_TOKEN_FILE), exist_ok=True)
    with open(RESET_TOKEN_FILE, "w") as f:
        json.dump(tokens, f, indent=2)

def send_password_reset_email(recipient_email: str, reset_token: str):
    try:
        msg = EmailMessage()
        msg["Subject"] = "🔐 Requiva Password Reset"
        msg["From"] = EMAIL_USER
        msg["To"] = recipient_email

        reset_link = f"https://requiva.app/reset?token={reset_token}"
        msg.set_content(
            f"Hi there,\n\nWe received a request to reset your Requiva password.\n"
            f"Use the following token: {reset_token}\n\n"
            f"Or click this link: {reset_link}\n\n"
            f"This token is valid for 30 minutes.\n\nIf you didn't request this, you can ignore this message."
        )

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
    except Exception as e:
        st.error(f"🚨 Email failed: {e}")

# ----------------------
# 🔍 Unreceived Orders
# ----------------------

def filter_unreceived_orders(df: pd.DataFrame) -> pd.DataFrame:
    return df[df["DATE RECEIVED"].isna() | (df["DATE RECEIVED"].astype(str).str.strip() == "")]

# ----------------------
# 🚨 Alert Column
# ----------------------

def generate_alert_column(df: pd.DataFrame) -> pd.Series:
    alert_flags = []
    for _, row in df.iterrows():
        if pd.isna(row["DATE RECEIVED"]) or str(row["DATE RECEIVED"]).strip() == "":
            alert_flags.append("🚨 Not received")
        else:
            alert_flags.append("")
    return pd.Series(alert_flags)

# ----------------------
# 🧪 Get Lab Name
# ----------------------

def get_user_lab(email: str) -> str:
    if email.lower() == "ogunbowaleadeola@gmail.com":
        return "Adelaiye-Ogala Lab"
    return "General Lab"

# ----------------------
# 🔒 Login Status Check
# ----------------------

def check_auth_status():
    return st.session_state.get("user", None)

def show_login_warning():
    st.warning("🔒 Please log in to access this app.")
```

---
