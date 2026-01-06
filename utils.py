import streamlit as st
import pandas as pd
import hashlib
import json
import os
from datetime import datetime

try:
    from firebase_admin import credentials, firestore, initialize_app
    import firebase_admin
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

# Firestore/Firebase setup
FIREBASE_JSON = os.getenv("FIREBASE_JSON") or st.secrets.get("firebase", {}).get("service_account_json")
USE_FIRESTORE = bool(FIREBASE_JSON) and FIREBASE_AVAILABLE

if USE_FIRESTORE:
    try:
        if not firebase_admin._apps:
            cred_dict = json.loads(FIREBASE_JSON)
            cred = credentials.Certificate(cred_dict)
            initialize_app(cred)
        db = firestore.client()
    except Exception as e:
        st.error(f"Firebase initialization failed: {e}")
        USE_FIRESTORE = False
        db = None
else:
    db = None

# Required Fields
REQUIRED_COLUMNS = [
    "REQ#", "ITEM", "NUMBER OF ITEM", "AMOUNT PER ITEM", "TOTAL",
    "VENDOR", "CAT #", "GRANT USED", "PO SOURCE", "PO #", "NOTES",
    "ORDERED BY", "DATE ORDERED", "DATE RECEIVED", "RECEIVED BY", "ITEM LOCATION", "LAB"
]

# Password hashing
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Auth check
def check_auth_status():
    return st.session_state.get("auth_user", None)

# Admin check
def is_admin(email):
    return email == "ogunbowaleadeola@gmail.com"

# Multi-lab assignment
def get_user_lab(email):
    if is_admin(email):
        return "Admin"
    elif email.endswith("@buffalo.edu"):
        return "Adelaiye-Ogala Lab"
    else:
        return email.split("@")[0].title() + " Lab"

# Login Form - FIXED
def login_form():
    st.subheader("🔐 Login Required")
    
    # Use a form to prevent automatic reruns
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            if USE_FIRESTORE and db:
                try:
                    user_ref = db.collection("users").document(email)
                    user = user_ref.get()
                    if user.exists and user.to_dict().get("password") == hash_password(password):
                        st.session_state.auth_user = email
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error("Invalid email or password.")
                except Exception as e:
                    st.error(f"Login error: {e}")
            else:
                # Dev mode
                if email == "test@lab.com" and password == "test":
                    st.session_state.auth_user = email
                    st.success("Test login successful.")
                    st.rerun()
                else:
                    st.error("Invalid credentials (dev mode)")

# Login warning
def show_login_warning():
    st.warning("Please log in to access Requiva.")

# Load orders
ORDERS_CSV = "orders.csv"
def load_orders():
    if USE_FIRESTORE and db:
        try:
            docs = db.collection("orders").stream()
            data = [doc.to_dict() for doc in docs]
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Error loading orders: {e}")
            return pd.DataFrame(columns=REQUIRED_COLUMNS)
    elif os.path.exists(ORDERS_CSV):
        return pd.read_csv(ORDERS_CSV)
    else:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

# Save orders
def save_orders(df):
    # Ensure all required columns exist
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    
    df = df[REQUIRED_COLUMNS]
    
    if USE_FIRESTORE and db:
        try:
            # Use transaction for atomicity
            batch = db.batch()
            col_ref = db.collection("orders")
            
            # Clear old orders
            docs = col_ref.stream()
            for doc in docs:
                batch.delete(doc.reference)
            batch.commit()
            
            # Add new orders
            batch = db.batch()
            for _, row in df.iterrows():
                doc_ref = col_ref.document(str(row["REQ#"]))
                batch.set(doc_ref, row.to_dict())
            batch.commit()
        except Exception as e:
            st.error(f"Error saving orders: {e}")
    else:
        df.to_csv(ORDERS_CSV, index=False)

# Generate REQ ID
def gen_req_id(df):
    existing_ids = df["REQ#"].tolist() if "REQ#" in df.columns and not df.empty else []
    base = datetime.now().strftime("REQ-%y%m%d")
    suffix = 1
    while f"{base}-{suffix:03d}" in existing_ids:
        suffix += 1
    return f"{base}-{suffix:03d}"

# Total amount
def compute_total(qty, unit_price):
    return round(qty * unit_price, 2)

# Order validation
def validate_order(item, qty, unit_price, vendor):
    if not item or qty <= 0 or unit_price <= 0 or not vendor:
        return False, "All required fields (*) must be filled properly."
    return True, "OK"

# Alert column
def generate_alert_column(df):
    df = df.copy()
    df["ALERT"] = df.apply(
        lambda row: "✅" if pd.notna(row.get("DATE RECEIVED")) and row.get("DATE RECEIVED") != "" else "⚠️ Missing",
        axis=1,
    )
    return df

# Filter unreceived orders
def filter_unreceived_orders(df):
    df = df.copy()
    if "DATE RECEIVED" in df.columns:
        return df[df["DATE RECEIVED"].isna() | (df["DATE RECEIVED"] == "")]
    return pd.DataFrame()

# Filter orders by lab
def filter_by_lab(df, user_email):
    if is_admin(user_email):
        return df
    lab_name = get_user_lab(user_email)
    if "LAB" in df.columns:
        return df[df["LAB"] == lab_name]
    return df
    
# Create account - FIXED
def create_account(email: str, password: str, lab: str = None):
    if not email or not password:
        return False, "Email and password are required."

    hashed = hash_password(password)
    user_data = {
        "password": hashed,
        "role": "admin" if email == "ogunbowaleadeola@gmail.com" else "user",
        "lab": lab or get_user_lab(email)
    }

    try:
        if USE_FIRESTORE and db:
            user_ref = db.collection("users").document(email)
            if user_ref.get().exists:
                return False, "Account already exists."
            user_ref.set(user_data)
        else:
            users_file = "data/users.json"
            os.makedirs(os.path.dirname(users_file), exist_ok=True)
            users = {}
            if os.path.exists(users_file):
                with open(users_file, "r") as f:
                    users = json.load(f)
            if email in users:
                return False, "Account already exists."
            users[email] = user_data
            with open(users_file, "w") as f:
                json.dump(users, f, indent=2)
        return True, "Account created successfully."
    except Exception as e:
        return False, f"Error creating account: {e}"

# Password reset - FIXED
def reset_password_request(email: str):
    if not email:
        return False, "Email is required."
    
    try:
        if USE_FIRESTORE and db:
            user_ref = db.collection("users").document(email)
            if not user_ref.get().exists:
                return False, "Account not found."
            
            # Store reset request
            reset_ref = db.collection("password_resets").document(email)
            reset_ref.set({
                "email": email,
                "requested_at": datetime.now().isoformat(),
                "status": "pending"
            })
            return True, "Password reset request submitted. Admin will contact you."
        else:
            return True, "Password reset request submitted (dev mode)."
    except Exception as e:
        return False, f"Error: {e}"
