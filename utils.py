import streamlit as st
import pandas as pd
import hashlib
import json
import os
from datetime import datetime
from typing import Tuple

# 🔐 Backend toggle
USE_FIRESTORE = os.getenv("USE_FIRESTORE", "False").lower() == "true"

# 🔥 Optional Firebase setup
if USE_FIRESTORE:
    import firebase_admin
    from firebase_admin import credentials, firestore

    if not firebase_admin._apps:
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "firebase_secrets.json")
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        else:
            st.error("Missing Firebase credentials")
            st.stop()

    db = firestore.client()

# 📌 Global Constants
REQUIRED_COLUMNS = [
    "REQ#", "ITEM", "NUMBER OF ITEM", "AMOUNT PER ITEM", "TOTAL", "VENDOR",
    "CAT #", "GRANT USED", "PO SOURCE", "PO #", "NOTES", "ORDERED BY",
    "DATE ORDERED", "DATE RECEIVED", "RECEIVED BY", "ITEM LOCATION"
]

USERS_DB = "users.json"
ORDERS_CSV = "orders.csv"

# 📥 User session auth
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def get_users():
    if os.path.exists(USERS_DB):
        with open(USERS_DB, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_DB, "w") as f:
        json.dump(users, f, indent=2)

def check_auth_status():
    return st.session_state.get("authenticated_user")

def login_form():
    st.sidebar.subheader("🔐 Login or Create Account")
    users = get_users()
    email = st.sidebar.text_input("Email (must be @buffalo.edu)", key="login_email")
    password = st.sidebar.text_input("Password", type="password", key="login_pw")

    if st.sidebar.button("Login"):
        if not email.endswith("@buffalo.edu"):
            st.sidebar.warning("Must use a @buffalo.edu email")
            return
        hashed = hash_password(password)
        if email in users and users[email]["password"] == hashed:
            st.session_state["authenticated_user"] = email
            st.experimental_rerun()
        else:
            st.sidebar.error("Invalid credentials")

    if st.sidebar.button("Create Account"):
        if not email.endswith("@buffalo.edu"):
            st.sidebar.warning("Only @buffalo.edu emails allowed")
            return
        if email in users:
            st.sidebar.info("User already exists. Try logging in.")
        else:
            lab = st.sidebar.text_input("Lab Name", key="create_lab")
            if lab:
                users[email] = {
                    "password": hash_password(password),
                    "lab": lab,
                    "role": "user"
                }
                save_users(users)
                st.sidebar.success("Account created. Please log in.")
            else:
                st.sidebar.warning("Please enter a lab name.")

    if st.sidebar.button("Forgot Password?"):
        st.session_state["show_pw_reset"] = True

def show_login_warning():
    st.warning("Login required. Use the sidebar to log in.")

# 🧪 Lab/Role
def get_user_lab(email: str) -> str:
    users = get_users()
    return users.get(email, {}).get("lab", "Unknown")

def is_admin(email: str) -> bool:
    users = get_users()
    return users.get(email, {}).get("role", "") == "admin"

# 📥 Order Management
def load_orders() -> pd.DataFrame:
    if USE_FIRESTORE:
        orders_ref = db.collection("orders")
        docs = orders_ref.stream()
        rows = []
        for doc in docs:
            rows.append(doc.to_dict())
        return pd.DataFrame(rows)
    else:
        if os.path.exists(ORDERS_CSV):
            return pd.read_csv(ORDERS_CSV)
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

def save_orders(df: pd.DataFrame):
    if USE_FIRESTORE:
        orders_ref = db.collection("orders")
        for _, row in df.iterrows():
            doc_id = str(row["REQ#"])
            orders_ref.document(doc_id).set(row.to_dict())
    else:
        df.to_csv(ORDERS_CSV, index=False)

# 🧮 Utils
def gen_req_id(df: pd.DataFrame) -> str:
    existing = df["REQ#"].astype(str).tolist() if "REQ#" in df.columns else []
    new_id = f"R{datetime.now().strftime('%Y%m%d%H%M%S')}"
    while new_id in existing:
        new_id = f"R{datetime.now().strftime('%Y%m%d%H%M%S')}"
    return new_id

def compute_total(qty: float, unit_price: float) -> float:
    return round(qty * unit_price, 2)

def validate_order(item, qty, unit_price, vendor) -> Tuple[bool, str]:
    if not item:
        return False, "Item name is required"
    if qty <= 0:
        return False, "Quantity must be > 0"
    if unit_price <= 0:
        return False, "Unit price must be > 0"
    if not vendor:
        return False, "Vendor is required"
    return True, "Valid"

def filter_unreceived_orders(df: pd.DataFrame) -> pd.DataFrame:
    if "DATE RECEIVED" not in df.columns:
        return pd.DataFrame()
    return df[df["DATE RECEIVED"].isnull() | (df["DATE RECEIVED"] == "")]

def generate_alert_column(df: pd.DataFrame) -> pd.DataFrame:
    df["ALERT"] = ""
    for idx, row in df.iterrows():
        try:
            ordered = pd.to_datetime(row.get("DATE ORDERED", ""))
            received = row.get("DATE RECEIVED", "")
            if not received and (datetime.now() - ordered).days > 10:
                df.at[idx, "ALERT"] = "⏰ Overdue"
        except Exception:
            pass
    return df
