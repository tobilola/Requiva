import streamlit as st
import pandas as pd
import hashlib
import json
import os
import smtplib
import secrets
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

try:
    from firebase_admin import credentials, firestore, initialize_app
    import firebase_admin
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

# Firebase Configuration
FIREBASE_JSON = (
    os.getenv("FIREBASE_JSON") or 
    os.getenv("firebase-service-account.json") or
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

# Email Configuration
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")  # Your Gmail address
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Gmail App Password
EMAIL_ENABLED = bool(EMAIL_ADDRESS and EMAIL_PASSWORD)

if EMAIL_ENABLED:
    print("✅ Email sending enabled")
else:
    print("⚠️ Email not configured. Set EMAIL_ADDRESS and EMAIL_PASSWORD env variables.")

# Admin Configuration
ADMIN_EMAIL = "ogunbowaleadeola@gmail.com"
ALLOWED_DOMAIN = "buffalo.edu"
DEFAULT_LAB = "Adelaiye-Ogala Lab"

REQUIRED_COLUMNS = [
    "REQ#", "ITEM", "NUMBER OF ITEM", "AMOUNT PER ITEM", "TOTAL",
    "VENDOR", "CAT #", "GRANT USED", "PO SOURCE", "PO #", "NOTES",
    "ORDERED BY", "DATE ORDERED", "DATE RECEIVED", "RECEIVED BY", "ITEM LOCATION", "LAB"
]

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_temp_password(length=12):
    """Generate a secure temporary password"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def check_auth_status():
    return st.session_state.get("auth_user", None)

def is_admin(email):
    return email == ADMIN_EMAIL

def is_allowed_email(email):
    """Check if email is allowed (admin or @buffalo.edu)"""
    if not email:
        return False
    if email == ADMIN_EMAIL:
        return True
    if email.endswith(f"@{ALLOWED_DOMAIN}"):
        return True
    return False

def get_user_lab(email):
    if is_admin(email):
        return "Admin"
    elif email.endswith(f"@{ALLOWED_DOMAIN}"):
        return DEFAULT_LAB
    else:
        try:
            domain = email.split("@")[1].split(".")[0]
            return f"{domain.title()} Lab"
        except:
            return "Unknown Lab"

def send_email(to_email, subject, body_html, body_text=None):
    """Send an email using Gmail SMTP"""
    if not EMAIL_ENABLED:
        return False, "Email not configured. Contact admin."
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"Requiva Lab System <{EMAIL_ADDRESS}>"
        msg['To'] = to_email
        
        # Plain text version
        if body_text:
            part1 = MIMEText(body_text, 'plain')
            msg.attach(part1)
        
        # HTML version
        part2 = MIMEText(body_html, 'html')
        msg.attach(part2)
        
        # Connect to Gmail SMTP
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        
        return True, "Email sent successfully"
    
    except smtplib.SMTPAuthenticationError:
        return False, "Email authentication failed. Check EMAIL_PASSWORD (use App Password)."
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"

def send_password_reset_email(to_email, temp_password):
    """Send password reset email with temporary password"""
    subject = "🔬 Requiva - Password Reset"
    
    body_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background-color: #1e3a5f; color: white; padding: 20px; text-align: center;">
            <h1>🔬 Requiva Lab System</h1>
        </div>
        <div style="padding: 30px; background-color: #f9f9f9;">
            <h2>Password Reset Request</h2>
            <p>Hello,</p>
            <p>We received a request to reset your password for the Requiva Lab Management System.</p>
            <p>Your temporary password is:</p>
            <div style="background-color: #e8f4f8; padding: 15px; border-radius: 5px; text-align: center; margin: 20px 0;">
                <code style="font-size: 24px; font-weight: bold; color: #1e3a5f;">{temp_password}</code>
            </div>
            <p><strong>Important:</strong></p>
            <ul>
                <li>Use this temporary password to log in</li>
                <li>We recommend changing your password after logging in</li>
                <li>If you didn't request this reset, please contact the admin</li>
            </ul>
            <p>Best regards,<br>Requiva Lab System</p>
        </div>
        <div style="background-color: #eee; padding: 15px; text-align: center; font-size: 12px; color: #666;">
            <p>Adelaiye-Ogala Lab | University at Buffalo</p>
            <p>This is an automated message. Please do not reply.</p>
        </div>
    </body>
    </html>
    """
    
    body_text = f"""
    Requiva Lab System - Password Reset
    
    Hello,
    
    We received a request to reset your password.
    
    Your temporary password is: {temp_password}
    
    Use this temporary password to log in. We recommend changing your password after logging in.
    
    If you didn't request this reset, please contact the admin.
    
    Best regards,
    Requiva Lab System
    Adelaiye-Ogala Lab | University at Buffalo
    """
    
    return send_email(to_email, subject, body_html, body_text)

def send_welcome_email(to_email, lab_name):
    """Send welcome email to new users"""
    subject = "🔬 Welcome to Requiva Lab System!"
    
    body_html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background-color: #1e3a5f; color: white; padding: 20px; text-align: center;">
            <h1>🔬 Welcome to Requiva!</h1>
        </div>
        <div style="padding: 30px; background-color: #f9f9f9;">
            <h2>Account Created Successfully</h2>
            <p>Hello,</p>
            <p>Your account has been created for the Requiva Lab Management System.</p>
            <div style="background-color: #e8f4f8; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Email:</strong> {to_email}</p>
                <p><strong>Lab:</strong> {lab_name}</p>
            </div>
            <p>You can now:</p>
            <ul>
                <li>📝 Create and track lab orders</li>
                <li>📊 View analytics and spending reports</li>
                <li>🤖 Get ML-powered insights and predictions</li>
                <li>💾 Export data for reporting</li>
            </ul>
            <p>Best regards,<br>Requiva Lab System</p>
        </div>
        <div style="background-color: #eee; padding: 15px; text-align: center; font-size: 12px; color: #666;">
            <p>Adelaiye-Ogala Lab | University at Buffalo</p>
        </div>
    </body>
    </html>
    """
    
    return send_email(to_email, subject, body_html)

def login_form():
    st.subheader("🔐 Login to Requiva")
    
    if USE_FIRESTORE:
        st.success("✅ Connected to Firestore")
    else:
        st.warning("⚠️ Running in development mode (CSV storage)")
    
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input(
            "Email", 
            placeholder="your.email@buffalo.edu",
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
            
            email = email.strip().lower()
            
            if USE_FIRESTORE and db:
                try:
                    user_ref = db.collection("users").document(email)
                    user = user_ref.get(timeout=10)  # 10 second timeout
                    
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
                    st.error(f"❌ Login error: Connection timed out or failed")
                    st.info("🔄 Please try again. If the problem persists, check your internet connection.")
                    print(f"Login error details: {e}")
            else:
                # Development mode
                DEV_USERS = {
                    "test@buffalo.edu": "test123",
                    "ogunbowaleadeola@gmail.com": "admin123"
                }
                
                if email in DEV_USERS and DEV_USERS[email] == password:
                    st.session_state.auth_user = email
                    st.success("✅ Test login successful (Development Mode)")
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials (Development Mode)")
                    st.info("💡 Development credentials: test@buffalo.edu / test123")
                    st.warning("⚠️ Add FIREBASE_JSON environment variable on Render to enable Firestore")

def show_login_warning():
    st.warning("🔒 Please log in to access Requiva Lab Management System")

ORDERS_CSV = "orders.csv"

def load_orders():
    if USE_FIRESTORE and db:
        try:
            docs = db.collection("orders").stream()
            data = [doc.to_dict() for doc in docs]
            df = pd.DataFrame(data)
            
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
            
            for col in REQUIRED_COLUMNS:
                if col not in df.columns:
                    df[col] = ""
            
            return df
            
        except Exception as e:
            st.error(f"Error loading orders from CSV: {e}")
            return pd.DataFrame(columns=REQUIRED_COLUMNS)
    else:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

def save_orders(df):
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    
    df = df[REQUIRED_COLUMNS]
    
    if USE_FIRESTORE and db:
        try:
            batch = db.batch()
            col_ref = db.collection("orders")
            
            docs = col_ref.stream()
            for doc in docs:
                batch.delete(doc.reference)
            batch.commit()
            
            batch = db.batch()
            for _, row in df.iterrows():
                doc_ref = col_ref.document(str(row["REQ#"]))
                batch.set(doc_ref, row.to_dict())
            batch.commit()
            
            print(f"✅ Saved {len(df)} orders to Firestore")
            
        except Exception as e:
            st.error(f"Error saving orders to Firestore: {e}")
            df.to_csv(ORDERS_CSV, index=False)
    else:
        try:
            df.to_csv(ORDERS_CSV, index=False)
            print(f"✅ Saved {len(df)} orders to CSV")
        except Exception as e:
            st.error(f"Error saving orders to CSV: {e}")

def gen_req_id(df):
    existing_ids = df["REQ#"].tolist() if "REQ#" in df.columns and not df.empty else []
    base = datetime.now().strftime("REQ-%y%m%d")
    suffix = 1
    
    while f"{base}-{suffix:03d}" in existing_ids:
        suffix += 1
    
    return f"{base}-{suffix:03d}"

def compute_total(qty, unit_price):
    return round(qty * unit_price, 2)

def validate_order(item, qty, unit_price, vendor):
    if not item or not item.strip():
        return False, "Item name is required"
    
    if qty <= 0:
        return False, "Quantity must be greater than 0"
    
    if unit_price <= 0:
        return False, "Price must be greater than 0"
    
    if not vendor or not vendor.strip():
        return False, "Vendor name is required"
    
    return True, "OK"

def generate_alert_column(df):
    df = df.copy()
    df["ALERT"] = df.apply(
        lambda row: "✅ Received" if pd.notna(row.get("DATE RECEIVED")) and row.get("DATE RECEIVED") != "" else "⏳ Pending",
        axis=1,
    )
    return df

def filter_unreceived_orders(df):
    df = df.copy()
    if "DATE RECEIVED" in df.columns:
        return df[df["DATE RECEIVED"].isna() | (df["DATE RECEIVED"] == "")]
    return pd.DataFrame()

def filter_by_lab(df, user_email):
    if df.empty:
        return df
    
    if is_admin(user_email):
        return df
    
    lab_name = get_user_lab(user_email)
    
    if "LAB" in df.columns:
        return df[df["LAB"] == lab_name]
    
    return df

def create_account(email: str, password: str, lab: str = None):
    if not email or not email.strip():
        return False, "Email is required"
    
    email = email.strip().lower()
    
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters"
    
    if "@" not in email or "." not in email.split("@")[1]:
        return False, "Invalid email format"
    
    # Check if email is allowed
    if not is_allowed_email(email):
        return False, f"Registration is restricted to @{ALLOWED_DOMAIN} emails. Contact admin for access."
    
    hashed = hash_password(password)
    lab_name = lab or get_user_lab(email)
    
    user_data = {
        "password": hashed,
        "role": "admin" if is_admin(email) else "user",
        "lab": lab_name,
        "created_at": datetime.now().isoformat()
    }

    try:
        if USE_FIRESTORE and db:
            user_ref = db.collection("users").document(email)
            if user_ref.get().exists:
                return False, "Account already exists. Try logging in or reset your password."
            
            user_ref.set(user_data)
            
            # Send welcome email (non-blocking - don't fail if email fails)
            if EMAIL_ENABLED:
                try:
                    send_welcome_email(email, lab_name)
                except:
                    pass  # Don't fail account creation if email fails
            
            return True, "Account created successfully! You can now login."
            
        else:
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
    if not email or not email.strip():
        return False, "Email is required"
    
    email = email.strip().lower()
    
    try:
        if USE_FIRESTORE and db:
            user_ref = db.collection("users").document(email)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                return False, "Email not found. Please check your email or create a new account."
            
            # Generate temporary password
            temp_password = generate_temp_password()
            hashed_temp = hash_password(temp_password)
            
            # Update user's password in Firestore
            user_ref.update({
                "password": hashed_temp,
                "password_reset_at": datetime.now().isoformat(),
                "temp_password": True  # Flag to indicate temp password
            })
            
            # Send email with temporary password
            if EMAIL_ENABLED:
                success, msg = send_password_reset_email(email, temp_password)
                if success:
                    return True, f"✅ Password reset email sent to {email}. Check your inbox (and spam folder)."
                else:
                    # Revert password change if email fails
                    user_data = user_doc.to_dict()
                    user_ref.update({"password": user_data.get("password")})
                    return False, f"Failed to send email: {msg}"
            else:
                # Email not configured - show temp password on screen (less secure)
                return True, f"✅ Your temporary password is: **{temp_password}**\n\nUse this to log in. (Email not configured)"
        else:
            # Development mode
            return True, "Password reset (Development Mode). Contact admin at ogunbowaleadeola@gmail.com"
            
    except Exception as e:
        return False, f"Error requesting password reset: {e}"

def get_firebase_status():
    status = {
        "firebase_available": FIREBASE_AVAILABLE,
        "use_firestore": USE_FIRESTORE,
        "firebase_json_exists": bool(FIREBASE_JSON),
        "db_connected": db is not None,
        "email_enabled": EMAIL_ENABLED
    }
    return status
