import streamlit as st
import pandas as pd
import hashlib
import json
import os
from datetime import datetime
from firebase_admin import credentials, firestore, initialize_app

# 🔐 Firestore/Firebase setup
FIREBASE_JSON = os.getenv("FIREBASE_JSON")
USE_FIRESTORE = bool(FIREBASE_JSON)

if USE_FIRESTORE and not firestore._apps:
    cred_dict = json.loads(FIREBASE_JSON)
    cred = credentials.Certificate(cred_dict)
    initialize_app(cred)
    db = firestore.client()
else:
    db = None

# 📌 Required Fields
REQUIRED_COLUMNS = [
    "REQ#", "ITEM", "NUMBER OF ITEM", "AMOUNT PER ITEM", "TOTAL",
    "VENDOR", "CAT #", "GRANT USED", "PO SOURCE", "PO #", "NOTES",
    "ORDERED BY", "DATE ORDERED", "DATE RECEIVED", "RECEIVED BY", "ITEM LOCATION"
]

# 🔒 Password hashing
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ✅ Auth check
def check_auth_status():
    return st.session_state.get("auth_user", None)

# 🔑 Admin check (Ogunbowale only)
def is_admin(email):
    return email == "ogunbowaleadeola@gmail.com"

# 🧪 Multi-lab assignment
def get_user_lab(email):
    if is_admin(email):
        return "Admin"
    elif email.endswith("@buffalo.edu"):
        return "Adelaiye-Ogala Lab"
    else:
        return email.split("@")[0].title() + " Lab"

# 🧾 Account creation form
def account_creation_form():
    st.subheader("🆕 Create New Account")
    email = st.text_input("New Email")
    password = st.text_input("New Password", type="password")
    confirm = st.text_input("Confirm Password", type="password")
    if st.button("Create Account"):
        if password != confirm:
            st.error("Passwords do not match.")
        elif USE_FIRESTORE:
            user_ref = db.collection("users").document(email)
            if user_ref.get().exists:
                st.error("User already exists.")
            else:
                user_ref.set({"password": hash_password(password)})
                st.success("Account created successfully.")
        else:
            st.info("Firestore not enabled. Running in test mode.")

# 🔑 Password reset (manual request)
def reset_password_request():
    st.subheader("🔁 Password Reset Request")
    email = st.text_input("Enter your registered email")
    if st.button("Request Reset"):
        if email.endswith("@buffalo.edu"):
            st.success(f"A reset request has been sent to the admin for: {email}")
        else:
            st.warning("Password reset only supported for buffalo.edu users.")

# 🔐 Login Form
def login_form():
    st.subheader("🔐 Login Required")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if USE_FIRESTORE:
            user_ref = db.collection("users").document(email)
            user = user_ref.get()
            if user.exists and user.to_dict().get("password") == hash_password(password):
                st.session_state.auth_user = email
                st.success("Login successful.")
                st.experimental_rerun()
            else:
                st.error("Invalid email or password.")
        else:
            if email == "test@lab.com" and password == "test":
                st.session_state.auth_user = email
                st.success("Test login successful.")
                st.experimental_rerun()
            else:
                st.error("Invalid credentials (dev mode)")

# ⚠️ Login warning
def show_login_warning():
    st.warning("Please log in to access Requiva.")

# 🧾 Load orders
ORDERS_CSV = "orders.csv"
def load_orders():
    if USE_FIRESTORE:
        docs = db.collection("orders").stream()
        data = [doc.to_dict() for doc in docs]
        return pd.DataFrame(data)
    elif os.path.exists(ORDERS_CSV):
        return pd.read_csv(ORDERS_CSV)
    else:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

# 💾 Save orders
def save_orders(df):
    df = df[REQUIRED_COLUMNS]
    if USE_FIRESTORE:
        batch = db.batch()
        col_ref = db.collection("orders")
        # Delete old
        docs = col_ref.stream()
        for doc in docs:
            batch.delete(doc.reference)
        batch.commit()
        # Add new
        for _, row in df.iterrows():
            batch.set(col_ref.document(row["REQ#"]), row.to_dict())
        batch.commit()
    else:
        df.to_csv(ORDERS_CSV, index=False)

# 🆔 Generate REQ ID
def gen_req_id(df):
    existing_ids = df["REQ#"].tolist() if "REQ#" in df.columns else []
    base = datetime.now().strftime("REQ-%y%m%d")
    suffix = 1
    while f"{base}-{suffix:03d}" in existing_ids:
        suffix += 1
    return f"{base}-{suffix:03d}"

# 💰 Total amount
def compute_total(qty, unit_price):
    return round(qty * unit_price, 2)

# ✅ Order validation
def validate_order(item, qty, unit_price, vendor):
    if not item or qty <= 0 or unit_price <= 0 or not vendor:
        return False, "All required fields (*) must be filled properly."
    return True, "OK"

# 🚨 Alert column
def generate_alert_column(df):
    df = df.copy()
    df["ALERT"] = df.apply(
        lambda row: "✅" if pd.notna(row.get("DATE RECEIVED")) and row.get("DATE RECEIVED") != "" else "⚠️ Missing",
        axis=1,
    )
    return df

# 🧼 Filter unreceived orders
def filter_unreceived_orders(df):
    df = df.copy()
    if "DATE RECEIVED" in df.columns:
        return df[df["DATE RECEIVED"].isna() | (df["DATE RECEIVED"] == "")]
    return pd.DataFrame()

# 🧪 Filter orders by lab
def filter_by_lab(df, user_email):
    if is_admin(user_email):
        return df  # Admin sees all
    lab_name = get_user_lab(user_email)
    return df[df["ORDERED BY"].str.contains(lab_name, na=False)]
# 🧑‍💻 Create Account
def create_account(email: str, password: str, lab: str = None):
    if not email or not password:
        return False
    hashed = hash_password(password)
    user_data = {
        "password": hashed,
        "role": "admin" if email == "ogunbowaleadeola@gmail.com" else "user",
        "lab": lab or get_user_lab(email)
    }
    if USE_FIRESTORE:
        db.collection("users").document(email).set(user_data)
    else:
        users_file = "data/users.json"
        os.makedirs(os.path.dirname(users_file), exist_ok=True)
        users = {}
        if os.path.exists(users_file):
            with open(users_file, "r") as f:
                users = json.load(f)
        users[email] = user_data
        with open(users_file, "w") as f:
            json.dump(users, f, indent=2)
    return True
