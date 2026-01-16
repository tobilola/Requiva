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

# ==========================================
# FIREBASE SETUP - IMPROVED
# ==========================================

# Try multiple environment variable names for flexibility
FIREBASE_JSON = (
    os.getenv("FIREBASE_JSON") or 
    os.getenv("firebase-service-account.json") or  # Old name
    os.getenv("FIREBASE_CREDENTIALS") or 
    st.secrets.get("firebase", {}).get("service_account_json")
)

USE_FIRESTORE = bool(FIREBASE_JSON) and FIREBASE_AVAILABLE

if USE_FIRESTORE:
    try:
        if not firebase_admin._apps:
            cred_dict = json.loads(FIREBASE_JSON)
            cred = credentials.Certificate(cred_dict)
            initialize_app(cred)
        db = firestore.client()
        print("✅ Firebase initialized successfully")
    except json.JSONDecodeError as e:
        print(f"❌ Firebase JSON parsing error: {e}")
        USE_FIRESTORE = False
        db = None
    except Exception as e:
        print(f"❌ Firebase initialization failed: {e}")
        USE_FIRESTORE = False
        db = None
else:
    db = None
    if FIREBASE_AVAILABLE:
        print("⚠️ Firebase credentials not found. Using CSV mode.")
    else:
        print("⚠️ Firebase Admin SDK not installed. Using CSV mode.")

# ==========================================
# REQUIRED COLUMNS
# ==========================================

REQUIRED_COLUMNS = [
    "REQ#", "ITEM", "NUMBER OF ITEM", "AMOUNT PER ITEM", "TOTAL",
    "VENDOR", "CAT #", "GRANT USED", "PO SOURCE", "PO #", "NOTES",
    "ORDERED BY", "DATE ORDERED", "DATE RECEIVED", "RECEIVED BY", "ITEM LOCATION", "LAB"
]

# ==========================================
# PASSWORD HASHING
# ==========================================

def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

# ==========================================
# AUTHENTICATION FUNCTIONS
# ==========================================

def check_auth_status():
    """Check if user is authenticated"""
    return st.session_state.get("auth_user", None)

def is_admin(email):
    """Check if email belongs to admin"""
    return email == "ogunbowaleadeola@gmail.com"

def get_user_lab(email):
    """
    Assign lab based on email domain.
    Admin can see all labs.
    Buffalo.edu users belong to Adelaiye-Ogala Lab.
    Others get lab name from domain.
    """
    if is_admin(email):
        return "Admin"
    elif email.endswith("@buffalo.edu"):
        return "Adelaiye-Ogala Lab"
    else:
        # Extract lab name from email domain
        try:
            domain = email.split("@")[1].split(".")[0]
            return f"{domain.title()} Lab"
        except:
            return "Unknown Lab"

def login_form():
    """Display login form and handle authentication"""
    st.subheader("🔐 Login to Requiva")
    
    # Show connection status
    if USE_FIRESTORE:
        st.success("✅ Connected to Firestore")
    else:
        st.warning("⚠️ Running in development mode (CSV storage)")
    
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input(
            "Email", 
            placeholder="your.email@example.com",
            help="Enter your registered email address"
        )
        password = st.text_input(
            "Password", 
            type="password",
            placeholder="Enter your password",
            help="Enter your password"
        )
        
        col1, col2 = st.columns([1, 3])
        with col1:
            submitted = st.form_submit_button("🔓 Login", type="primary", use_container_width=True)
        
        if submitted:
            if not email or not password:
                st.error("❌ Please enter both email and password")
                return
            
            # Try authentication
            if USE_FIRESTORE and db:
                # Firestore authentication
                try:
                    user_ref = db.collection("users").document(email)
                    user = user_ref.get()
                    
                    if user.exists:
                        user_data = user.to_dict()
                        stored_password = user_data.get("password")
                        
                        if stored_password == hash_password(password):
                            st.session_state.auth_user = email
                            st.success("✅ Login successful!")
                            st.rerun()
                        else:
                            st.error("❌ Invalid password")
                            st.info("💡 Use 'Request Password Reset' if you forgot your password")
                    else:
                        st.error("❌ Email not found")
                        st.info("💡 Create a new account below if you don't have one")
                        
                except Exception as e:
                    st.error(f"❌ Login error: {e}")
                    st.error("Check if Firebase is properly configured on Render")
            else:
                # Development mode - hardcoded test credentials
                DEV_USERS = {
                    "test@lab.com": "test",
                    "ogunbowaleadeola@gmail.com": "admin123"  # Temporary dev access
                }
                
                if email in DEV_USERS and DEV_USERS[email] == password:
                    st.session_state.auth_user = email
                    st.success("✅ Test login successful (Development Mode)")
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials (Development Mode)")
                    st.info("💡 Development mode credentials: test@lab.com / test")
                    st.warning("⚠️ Add FIREBASE_JSON environment variable on Render to enable Firestore")

def show_login_warning():
    """Show warning to login"""
    st.warning("🔒 Please log in to access Requiva Lab Management System")

# ==========================================
# ORDER MANAGEMENT
# ==========================================

ORDERS_CSV = "orders.csv"

def load_orders():
    """Load orders from Firestore or CSV"""
    if USE_FIRESTORE and db:
        try:
            docs = db.collection("orders").stream()
            data = [doc.to_dict() for doc in docs]
            df = pd.DataFrame(data)
            
            # Ensure all required columns exist
            for col in REQUIRED_COLUMNS:
                if col not in df.columns:
                    df[col] = ""
            
            return df
            
        except Exception as e:
            st.error(f"Error loading orders from Firestore: {e}")
            return pd.DataFrame(columns=REQUIRED_COLUMNS)
    
    elif os.path.exists(ORDERS_CSV):
        try:
            df = pd.read_csv(ORDERS_CSV)
            
            # Ensure all required columns exist
            for col in REQUIRED_COLUMNS:
                if col not in df.columns:
                    df[col] = ""
            
            return df
            
        except Exception as e:
            st.error(f"Error loading orders from CSV: {e}")
            return pd.DataFrame(columns=REQUIRED_COLUMNS)
    else:
        # No data exists yet
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

def save_orders(df):
    """Save orders to Firestore or CSV"""
    # Ensure all required columns exist
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    
    # Keep only required columns
    df = df[REQUIRED_COLUMNS]
    
    if USE_FIRESTORE and db:
        try:
            # Clear existing orders
            batch = db.batch()
            col_ref = db.collection("orders")
            
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
            
            print(f"✅ Saved {len(df)} orders to Firestore")
            
        except Exception as e:
            st.error(f"Error saving orders to Firestore: {e}")
            # Fallback to CSV
            df.to_csv(ORDERS_CSV, index=False)
    else:
        # Save to CSV
        try:
            df.to_csv(ORDERS_CSV, index=False)
            print(f"✅ Saved {len(df)} orders to CSV")
        except Exception as e:
            st.error(f"Error saving orders to CSV: {e}")

def gen_req_id(df):
    """Generate unique REQ ID"""
    existing_ids = df["REQ#"].tolist() if "REQ#" in df.columns and not df.empty else []
    base = datetime.now().strftime("REQ-%y%m%d")
    suffix = 1
    
    while f"{base}-{suffix:03d}" in existing_ids:
        suffix += 1
    
    return f"{base}-{suffix:03d}"

def compute_total(qty, unit_price):
    """Calculate total amount"""
    return round(qty * unit_price, 2)

def validate_order(item, qty, unit_price, vendor):
    """Validate order inputs"""
    if not item or not item.strip():
        return False, "Item name is required"
    
    if qty <= 0:
        return False, "Quantity must be greater than 0"
    
    if unit_price <= 0:
        return False, "Price must be greater than 0"
    
    if not vendor or not vendor.strip():
        return False, "Vendor name is required"
    
    return True, "OK"

# ==========================================
# DATA FILTERING & DISPLAY
# ==========================================

def generate_alert_column(df):
    """Add ALERT column showing order status"""
    df = df.copy()
    df["ALERT"] = df.apply(
        lambda row: "✅ Received" if pd.notna(row.get("DATE RECEIVED")) and row.get("DATE RECEIVED") != "" else "⏳ Pending",
        axis=1,
    )
    return df

def filter_unreceived_orders(df):
    """Filter orders that haven't been received yet"""
    df = df.copy()
    if "DATE RECEIVED" in df.columns:
        return df[df["DATE RECEIVED"].isna() | (df["DATE RECEIVED"] == "")]
    return pd.DataFrame()

def filter_by_lab(df, user_email):
    """
    Filter orders by lab.
    Admin sees all orders.
    Regular users only see their lab's orders.
    """
    if df.empty:
        return df
    
    if is_admin(user_email):
        return df  # Admin sees everything
    
    lab_name = get_user_lab(user_email)
    
    if "LAB" in df.columns:
        return df[df["LAB"] == lab_name]
    
    return df

# ==========================================
# ACCOUNT MANAGEMENT
# ==========================================

def create_account(email: str, password: str, lab: str = None):
    """Create new user account"""
    if not email or not email.strip():
        return False, "Email is required"
    
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters"
    
    # Validate email format
    if "@" not in email or "." not in email.split("@")[1]:
        return False, "Invalid email format"
    
    hashed = hash_password(password)
    user_data = {
        "password": hashed,
        "role": "admin" if is_admin(email) else "user",
        "lab": lab or get_user_lab(email),
        "created_at": datetime.now().isoformat()
    }

    try:
        if USE_FIRESTORE and db:
            # Check if user already exists
            user_ref = db.collection("users").document(email)
            if user_ref.get().exists:
                return False, "Account already exists. Try logging in or reset your password."
            
            # Create new user
            user_ref.set(user_data)
            return True, "Account created successfully! You can now login."
            
        else:
            # Save to local JSON file
            users_file = "data/users.json"
            os.makedirs(os.path.dirname(users_file), exist_ok=True)
            
            users = {}
            if os.path.exists(users_file):
                with open(users_file, "r") as f:
                    users = json.load(f)
            
            if email in users:
                return False, "Account already exists"
            
            users[email] = user_data
            
            with open(users_file, "w") as f:
                json.dump(users, f, indent=2)
            
            return True, "Account created successfully (Development Mode)"
            
    except Exception as e:
        return False, f"Error creating account: {e}"

def reset_password_request(email: str):
    """Request password reset"""
    if not email or not email.strip():
        return False, "Email is required"
    
    try:
        if USE_FIRESTORE and db:
            # Check if user exists
            user_ref = db.collection("users").document(email)
            if not user_ref.get().exists:
                return False, "Email not found. Please check your email or create a new account."
            
            # Create password reset request
            reset_ref = db.collection("password_resets").document(email)
            reset_ref.set({
                "email": email,
                "requested_at": datetime.now().isoformat(),
                "status": "pending"
            })
            
            return True, f"✅ Password reset request submitted for {email}. Admin will contact you via email."
        else:
            return True, "Password reset request submitted (Development Mode). Contact admin at ogunbowaleadeola@gmail.com"
            
    except Exception as e:
        return False, f"Error requesting password reset: {e}"

# ==========================================
# UTILITY FUNCTIONS
# ==========================================

def get_firebase_status():
    """Get detailed Firebase connection status"""
    status = {
        "firebase_available": FIREBASE_AVAILABLE,
        "use_firestore": USE_FIRESTORE,
        "firebase_json_exists": bool(FIREBASE_JSON),
        "db_connected": db is not None
    }
    return status
