import os
import json
from datetime import datetime
from typing import Tuple

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

DATA_PATH = os.getenv("REQUIVA_DATA_PATH", "data/orders.csv")
FIREBASE_CREDENTIAL_PATH = "/etc/secrets/firebase-service-account.json"

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
# 🔐 Auth (Simple Lab Email Login + Role Check)
# ----------------------

def check_auth_status():
    return st.session_state.get("user", None)

def is_admin(user_email: str) -> bool:
    admin_email = st.secrets.get("auth", {}).get("admin_email", "")
    return user_email.lower() == admin_email.lower()

def get_user_lab(user_email: str) -> str:
    domain = user_email.split("@")[-1]
    return st.secrets.get("labs", {}).get(domain, "Unknown Lab")

def login_form():
    st.subheader("🔐 Sign In to Requiva")
    with st.form("login_form"):
        email = st.text_input("Email")
        submit = st.form_submit_button("Sign In")

    if submit:
        allowed_domains = st.secrets.get("auth", {}).get("allowed_domains", [])
        domain = email.split("@")[-1]
        if domain not in allowed_domains:
            st.error("❌ Email domain not allowed.")
        else:
            st.session_state["user"] = email
            st.session_state["lab"] = get_user_lab(email)
            st.experimental_rerun()

def show_login_warning():
    st.info("ℹ️ Please sign in with your lab email to use Requiva.")

# ----------------------
# 🚨 Alert Column Generator
# ----------------------

def generate_alert_column(df: pd.DataFrame) -> pd.Series:
    """
    Flags unreceived orders for alert display.
    Returns a new Series with alert indicators (e.g., 🚨) where needed.
    """
    alert_flags = []

    for _, row in df.iterrows():
        if pd.isna(row["DATE RECEIVED"]) or str(row["DATE RECEIVED"]).strip() == "":
            alert_flags.append("🚨 Not received")
        else:
            alert_flags.append("")  # No alert

    return pd.Series(alert_flags)

