from datetime import date, datetime
from io import BytesIO
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import os

from utils import (
    check_auth_status,
    login_form,
    show_login_warning,
    is_admin,
    get_user_lab,
    generate_alert_column,
    filter_unreceived_orders,
    USE_FIRESTORE,
    load_orders,
    save_orders,
    gen_req_id,
    compute_total,
    validate_order,
    REQUIRED_COLUMNS,
    create_account,
    reset_password_request,
    filter_by_lab,
    check_admin_bypass,
    ADMIN_BYPASS_ENABLED,
    ADMIN_EMAIL,
)

from ml_engine import (
    predict_reorder_date,
    forecast_spending,
    detect_anomalies,
    recommend_vendors,
    forecast_demand,
    get_bulk_opportunities,
)

# Page config
st.set_page_config(
    page_title="Requiva - Lab Order Management", 
    page_icon="R", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
<style>
    /* Main theme colors */
    :root {
        --primary: #1e3a5f;
        --primary-light: #2d5a8b;
        --secondary: #0d9488;
        --success: #059669;
        --warning: #d97706;
        --danger: #dc2626;
        --gray-50: #f9fafb;
        --gray-100: #f3f4f6;
        --gray-200: #e5e7eb;
        --gray-600: #4b5563;
        --gray-800: #1f2937;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Main container */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }
    
    /* Headers */
    h1 {
        color: #1e3a5f !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px;
    }
    
    h2, h3 {
        color: #1f2937 !important;
        font-weight: 600 !important;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e3a5f 0%, #2d5a8b 100%);
    }
    
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    
    [data-testid="stSidebar"] .stButton button {
        background-color: rgba(255,255,255,0.15) !important;
        border: 1px solid rgba(255,255,255,0.3) !important;
        color: white !important;
    }
    
    [data-testid="stSidebar"] .stButton button:hover {
        background-color: rgba(255,255,255,0.25) !important;
        border: 1px solid rgba(255,255,255,0.5) !important;
    }
    
    /* Cards */
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border: 1px solid #e5e7eb;
        text-align: center;
    }
    
    .metric-card h3 {
        font-size: 0.875rem;
        color: #6b7280 !important;
        font-weight: 500;
        margin-bottom: 0.5rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .metric-card .value {
        font-size: 2rem;
        font-weight: 700;
        color: #1e3a5f;
    }
    
    .metric-card.success .value { color: #059669; }
    .metric-card.warning .value { color: #d97706; }
    .metric-card.danger .value { color: #dc2626; }
    
    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .status-pending {
        background-color: #fef3c7;
        color: #92400e;
    }
    
    .status-received {
        background-color: #d1fae5;
        color: #065f46;
    }
    
    .status-urgent {
        background-color: #fee2e2;
        color: #991b1b;
    }
    
    /* Section headers */
    .section-header {
        background: linear-gradient(90deg, #1e3a5f 0%, #2d5a8b 100%);
        color: white;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        font-weight: 600;
    }
    
    /* Form styling */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > div {
        border-radius: 8px !important;
        border: 1px solid #d1d5db !important;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #1e3a5f !important;
        box-shadow: 0 0 0 2px rgba(30, 58, 95, 0.1) !important;
    }
    
    /* Buttons */
    .stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #1e3a5f 0%, #2d5a8b 100%) !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.5rem 1.5rem !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(30, 58, 95, 0.3) !important;
    }
    
    .stButton > button[kind="secondary"] {
        background: white !important;
        border: 1px solid #d1d5db !important;
        border-radius: 8px !important;
        color: #374151 !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background-color: #f3f4f6;
        border-radius: 10px;
        padding: 4px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 500;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: white !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    /* Dataframe styling */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    /* Alerts */
    .stAlert {
        border-radius: 8px !important;
    }
    
    /* Info boxes */
    .info-box {
        background: #f0f9ff;
        border-left: 4px solid #0ea5e9;
        padding: 1rem;
        border-radius: 0 8px 8px 0;
        margin: 1rem 0;
    }
    
    .warning-box {
        background: #fffbeb;
        border-left: 4px solid #f59e0b;
        padding: 1rem;
        border-radius: 0 8px 8px 0;
        margin: 1rem 0;
    }
    
    .success-box {
        background: #ecfdf5;
        border-left: 4px solid #10b981;
        padding: 1rem;
        border-radius: 0 8px 8px 0;
        margin: 1rem 0;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background-color: #f9fafb !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
    }
    
    /* Progress indicator */
    .progress-bar {
        height: 8px;
        background: #e5e7eb;
        border-radius: 4px;
        overflow: hidden;
    }
    
    .progress-bar-fill {
        height: 100%;
        background: linear-gradient(90deg, #059669 0%, #10b981 100%);
        border-radius: 4px;
    }
    
    /* Table enhancements */
    .styled-table {
        width: 100%;
        border-collapse: collapse;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    .styled-table thead {
        background: #1e3a5f;
        color: white;
    }
    
    .styled-table th {
        padding: 12px 16px;
        text-align: left;
        font-weight: 600;
        font-size: 0.875rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .styled-table td {
        padding: 12px 16px;
        border-bottom: 1px solid #e5e7eb;
    }
    
    .styled-table tbody tr:hover {
        background-color: #f9fafb;
    }
    
    /* Login page */
    .login-container {
        max-width: 400px;
        margin: 0 auto;
        padding: 2rem;
        background: white;
        border-radius: 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    }
    
    .logo-text {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1e3a5f;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    
    .tagline {
        color: #6b7280;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    /* Divider */
    .divider {
        height: 1px;
        background: #e5e7eb;
        margin: 1.5rem 0;
    }
    
    /* Quick stats row */
    .stats-row {
        display: flex;
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    
    /* Empty state */
    .empty-state {
        text-align: center;
        padding: 3rem;
        color: #6b7280;
    }
    
    .empty-state-icon {
        font-size: 3rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Helper functions for styled components
def metric_card(title, value, card_type="default"):
    type_class = card_type if card_type != "default" else ""
    st.markdown(f"""
        <div class="metric-card {type_class}">
            <h3>{title}</h3>
            <div class="value">{value}</div>
        </div>
    """, unsafe_allow_html=True)

def status_badge(status):
    if status.lower() in ['pending', 'urgent']:
        return f'<span class="status-badge status-pending">{status}</span>'
    elif status.lower() in ['received', 'complete', 'completed']:
        return f'<span class="status-badge status-received">{status}</span>'
    else:
        return f'<span class="status-badge">{status}</span>'

def section_header(title):
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)

# Initialize session state
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None
if "imported_pos" not in st.session_state:
    st.session_state.imported_pos = None

# Authentication Check
user_email = check_auth_status()

# ============== LOGIN PAGE ==============
if not user_email:
    # Hide sidebar on login page
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {display: none;}
        </style>
    """, unsafe_allow_html=True)
    
    # Centered login container
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown('<div class="logo-text">Requiva</div>', unsafe_allow_html=True)
        st.markdown('<p class="tagline">Lab Order Management System</p>', unsafe_allow_html=True)
        
        # Connection status
        from utils import db
        if USE_FIRESTORE and db:
            st.success("Database connected")
        elif USE_FIRESTORE and not db:
            st.error("Database connection failed - check FIREBASE_JSON")
            if ADMIN_BYPASS_ENABLED:
                st.info("💡 **Admin:** Use bypass password to login while database is down")
        else:
            st.warning("Development mode (no database)")
            if ADMIN_BYPASS_ENABLED:
                st.info("💡 **Admin:** Bypass login available")
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        # Login form
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input(
                "Email", 
                placeholder="your.email@buffalo.edu",
            )
            password = st.text_input(
                "Password", 
                type="password",
                placeholder="Enter your password",
            )
            
            submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)
            
            if submitted:
                if not email or not password:
                    st.error("Please enter both email and password")
                else:
                    email = email.strip().lower()
                    from utils import hash_password, db, USE_FIRESTORE
                    
                    # Check admin bypass FIRST (works even when Firebase is down)
                    if check_admin_bypass(email, password):
                        st.session_state.auth_user = email
                        st.success("✅ Admin bypass login successful")
                        st.rerun()
                    elif USE_FIRESTORE and db:
                        with st.spinner("Signing in..."):
                            try:
                                user_ref = db.collection("users").document(email)
                                user = user_ref.get(timeout=30)
                                
                                if user.exists:
                                    user_data = user.to_dict()
                                    if user_data.get("password") == hash_password(password):
                                        st.session_state.auth_user = email
                                        st.rerun()
                                    else:
                                        st.error("Invalid password")
                                else:
                                    st.error("Account not found. Create one below.")
                            except Exception as e:
                                st.error(f"Connection timeout. Please try again.")
                                if ADMIN_BYPASS_ENABLED and email == ADMIN_EMAIL:
                                    st.warning("💡 **Admin:** Try your bypass password instead")
                    else:
                        # Dev mode or Firebase not configured
                        DEV_USERS = {"test@buffalo.edu": "test123", "ogunbowaleadeola@gmail.com": "admin123"}
                        if email in DEV_USERS and DEV_USERS[email] == password:
                            st.session_state.auth_user = email
                            st.rerun()
                        else:
                            st.error("Invalid credentials")
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        # Account options
        col_a, col_b = st.columns(2)
        
        with col_a:
            with st.expander("Create Account"):
                new_email = st.text_input("Email", key="new_email", placeholder="your.email@buffalo.edu")
                new_password = st.text_input("Password", type="password", key="new_pass", placeholder="Min 6 characters")
                
                if st.button("Create Account", use_container_width=True):
                    if new_email and new_password:
                        success, msg = create_account(new_email, new_password)
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
        
        with col_b:
            with st.expander("Forgot Password"):
                reset_email = st.text_input("Email", key="reset_email", placeholder="your.email@buffalo.edu")
                
                if st.button("Reset Password", use_container_width=True):
                    if reset_email:
                        success, msg = reset_password_request(reset_email)
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown("""
            <p style="text-align: center; color: #6b7280; font-size: 0.875rem;">
                Adelaiye-Ogala Lab · University at Buffalo
            </p>
        """, unsafe_allow_html=True)
    
    st.stop()

# ============== MAIN APP (Logged In) ==============
lab_name = get_user_lab(user_email)

# Sidebar
with st.sidebar:
    st.markdown(f"""
        <div style="padding: 1rem 0;">
            <div style="font-size: 1.5rem; font-weight: 700;">Requiva</div>
            <div style="font-size: 0.875rem; opacity: 0.8;">Lab Order Management</div>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="divider" style="background: rgba(255,255,255,0.2);"></div>', unsafe_allow_html=True)
    
    st.markdown(f"""
        <div style="padding: 0.5rem 0;">
            <div style="font-size: 0.75rem; opacity: 0.7; text-transform: uppercase; letter-spacing: 0.5px;">Logged in as</div>
            <div style="font-weight: 500;">{user_email}</div>
            <div style="font-size: 0.875rem; opacity: 0.8; margin-top: 0.25rem;">{lab_name}</div>
        </div>
    """, unsafe_allow_html=True)
    
    if is_admin(user_email):
        st.markdown("""
            <div style="background: rgba(255,255,255,0.15); padding: 0.5rem; border-radius: 6px; margin-top: 0.5rem;">
                <span style="font-size: 0.75rem;">Admin Access</span>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown('<div class="divider" style="background: rgba(255,255,255,0.2);"></div>', unsafe_allow_html=True)
    
    if st.button("Sign Out", use_container_width=True):
        st.session_state.auth_user = None
        st.rerun()
    
    st.markdown('<div class="divider" style="background: rgba(255,255,255,0.2);"></div>', unsafe_allow_html=True)
    
    # Quick stats in sidebar
    df_sidebar = load_orders()
    df_sidebar = filter_by_lab(df_sidebar, user_email)
    
    if not df_sidebar.empty:
        total_orders = len(df_sidebar)
        pending = len(df_sidebar[(df_sidebar["DATE RECEIVED"].isna()) | (df_sidebar["DATE RECEIVED"] == "")])
        
        st.markdown(f"""
            <div style="padding: 0.5rem 0;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                    <span style="opacity: 0.8;">Total Orders</span>
                    <span style="font-weight: 600;">{total_orders}</span>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="opacity: 0.8;">Pending</span>
                    <span style="font-weight: 600; color: #fbbf24;">{pending}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

# Main content header
st.markdown("""
    <div style="margin-bottom: 1.5rem;">
        <h1 style="margin-bottom: 0.25rem;">Dashboard</h1>
        <p style="color: #6b7280; margin: 0;">Manage your lab orders and inventory</p>
    </div>
""", unsafe_allow_html=True)

# Main Tabs - Import only visible to admins
if is_admin(user_email):
    tab_dashboard, tab_new, tab_import, tab_table, tab_analytics, tab_export = st.tabs([
        "Overview",
        "New Order", 
        "Import Data",
        "All Orders", 
        "Analytics",
        "Export"
    ])
else:
    tab_dashboard, tab_new, tab_table, tab_analytics, tab_export = st.tabs([
        "Overview",
        "New Order", 
        "All Orders", 
        "Analytics",
        "Export"
    ])
    tab_import = None  # Not available for non-admins

# ============== TAB: Dashboard Overview ==============
with tab_dashboard:
    df = load_orders()
    df = filter_by_lab(df, user_email)
    
    if df.empty:
        st.markdown("""
            <div class="empty-state">
                <div class="empty-state-icon">📋</div>
                <h3>No orders yet</h3>
                <p>Start by creating a new order or importing data from ShopBlue.</p>
            </div>
        """, unsafe_allow_html=True)
    else:
        # Key metrics row
        col1, col2, col3, col4 = st.columns(4)
        
        total_orders = len(df)
        
        # Safely convert TOTAL to numeric
        if "TOTAL" in df.columns:
            df["TOTAL"] = pd.to_numeric(df["TOTAL"], errors='coerce').fillna(0)
            total_spending = df["TOTAL"].sum()
        else:
            total_spending = 0
        
        pending = len(df[(df["DATE RECEIVED"].isna()) | (df["DATE RECEIVED"] == "")])
        received = total_orders - pending
        
        with col1:
            metric_card("Total Orders", f"{total_orders:,}")
        
        with col2:
            metric_card("Total Spending", f"${total_spending:,.2f}")
        
        with col3:
            metric_card("Pending", str(pending), "warning" if pending > 0 else "success")
        
        with col4:
            metric_card("Received", str(received), "success")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Two column layout for recent orders and pending
        col_left, col_right = st.columns([3, 2])
        
        with col_left:
            section_header("Recent Orders")
            
            df_recent = df.sort_values('DATE ORDERED', ascending=False).head(5) if 'DATE ORDERED' in df.columns else df.head(5)
            
            for _, row in df_recent.iterrows():
                is_pending = pd.isna(row.get("DATE RECEIVED")) or row.get("DATE RECEIVED") == ""
                status_html = status_badge("Pending" if is_pending else "Received")
                
                st.markdown(f"""
                    <div style="background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1rem; margin-bottom: 0.75rem;">
                        <div style="display: flex; justify-content: space-between; align-items: start;">
                            <div>
                                <div style="font-weight: 600; color: #1f2937;">{row.get('ITEM', 'N/A')[:50]}{'...' if len(str(row.get('ITEM', ''))) > 50 else ''}</div>
                                <div style="font-size: 0.875rem; color: #6b7280; margin-top: 0.25rem;">{row.get('VENDOR', 'N/A')}</div>
                            </div>
                            <div style="text-align: right;">
                                <div style="font-weight: 600; color: #1e3a5f;">${row.get('TOTAL', 0):,.2f}</div>
                                {status_html}
                            </div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
        
        with col_right:
            section_header("Pending Items")
            
            df_pending = df[(df["DATE RECEIVED"].isna()) | (df["DATE RECEIVED"] == "")]
            
            if df_pending.empty:
                st.markdown("""
                    <div style="background: #ecfdf5; border-radius: 8px; padding: 1.5rem; text-align: center;">
                        <div style="color: #059669; font-weight: 600;">All caught up!</div>
                        <div style="color: #6b7280; font-size: 0.875rem; margin-top: 0.25rem;">No pending items</div>
                    </div>
                """, unsafe_allow_html=True)
            else:
                for _, row in df_pending.head(5).iterrows():
                    st.markdown(f"""
                        <div style="background: #fffbeb; border-left: 3px solid #f59e0b; padding: 0.75rem; margin-bottom: 0.5rem; border-radius: 0 6px 6px 0;">
                            <div style="font-weight: 500; font-size: 0.875rem;">{row.get('ITEM', 'N/A')[:40]}</div>
                            <div style="font-size: 0.75rem; color: #6b7280;">Ordered: {row.get('DATE ORDERED', 'N/A')}</div>
                        </div>
                    """, unsafe_allow_html=True)
                
                if len(df_pending) > 5:
                    st.caption(f"+ {len(df_pending) - 5} more pending items")

# ============== TAB: New Order ==============
with tab_new:
    section_header("Create New Order")
    
    df = load_orders()
    df = filter_by_lab(df, user_email)
    
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    
    # Form in organized sections
    with st.form("new_order_form"):
        st.markdown("**Item Information**")
        col1, col2 = st.columns(2)
        
        with col1:
            item = st.text_input("Item Name *", placeholder="e.g., Fetal Bovine Serum (FBS) 500 mL")
            vendor = st.text_input("Vendor *", placeholder="e.g., Fisher Scientific")
            cat_no = st.text_input("Catalog #", placeholder="e.g., 12345-TF")
        
        with col2:
            grant_used = st.text_input("Grant", placeholder="e.g., R01CA12345")
            po_source = st.selectbox("PO Source", ["ShopBlue", "Stock Room", "External Vendor"])
            po_no = st.text_input("PO #", placeholder="e.g., 1481052")
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown("**Pricing**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            qty = st.number_input("Quantity *", min_value=0.0, value=1.0, step=1.0)
        
        with col2:
            unit_price = st.number_input("Unit Price ($) *", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        
        with col3:
            if qty > 0 and unit_price > 0:
                st.markdown(f"""
                    <div style="background: #ecfdf5; padding: 1rem; border-radius: 8px; margin-top: 1.5rem;">
                        <div style="font-size: 0.75rem; color: #059669; text-transform: uppercase;">Total</div>
                        <div style="font-size: 1.5rem; font-weight: 700; color: #059669;">${qty * unit_price:,.2f}</div>
                    </div>
                """, unsafe_allow_html=True)
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown("**Order Details**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            ordered_by = st.text_input("Ordered By", value=user_email.split('@')[0])
            date_ordered = st.date_input("Date Ordered", value=date.today())
        
        with col2:
            notes = st.text_area("Notes", placeholder="Any special instructions...", height=100)
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        received_flag = st.checkbox("Mark as received")
        
        if received_flag:
            col1, col2, col3 = st.columns(3)
            with col1:
                date_received = st.date_input("Date Received", value=date.today())
            with col2:
                received_by = st.text_input("Received By")
            with col3:
                location = st.text_input("Storage Location")
        else:
            date_received = None
            received_by = ""
            location = ""
        
        submitted = st.form_submit_button("Add Order", type="primary", use_container_width=True)
        
        if submitted:
            ok, msg = validate_order(item, qty, unit_price, vendor)
            
            if not ok:
                st.error(msg)
            else:
                req_id = gen_req_id(df)
                total = compute_total(qty, unit_price)
                
                new_row = {
                    "REQ#": req_id,
                    "ITEM": item,
                    "NUMBER OF ITEM": qty,
                    "AMOUNT PER ITEM": unit_price,
                    "TOTAL": total,
                    "VENDOR": vendor,
                    "CAT #": cat_no,
                    "GRANT USED": grant_used,
                    "PO SOURCE": po_source,
                    "PO #": po_no,
                    "NOTES": notes,
                    "ORDERED BY": ordered_by,
                    "DATE ORDERED": date_ordered.isoformat() if date_ordered else "",
                    "DATE RECEIVED": date_received.isoformat() if date_received else "",
                    "RECEIVED BY": received_by,
                    "ITEM LOCATION": location,
                    "LAB": lab_name,
                }
                
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                save_orders(df)
                
                st.success(f"Order {req_id} added successfully — ${total:,.2f}")

# ============== TAB: Import Data (Admin Only) ==============
if is_admin(user_email) and tab_import is not None:
    with tab_import:
        section_header("Import Orders (Admin)")
        
        import_type = st.radio(
            "Select import source:",
            ["ShopBlue Export", "Lab Inventory/Accounts File"],
            horizontal=True
        )
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        if import_type == "ShopBlue Export":
            st.markdown("""
                <div class="info-box">
                    <strong>Supported ShopBlue exports:</strong><br>
                    • Line-item export (with Item, Quantity, Unit Price columns)<br>
                    • PO summary export (Purchase Orders Completed)
                </div>
            """, unsafe_allow_html=True)
            
            uploaded_file = st.file_uploader("Upload ShopBlue Export", type=["xlsx"], key="shopblue_upload")
            
            if uploaded_file is not None:
                try:
                    # Read file with header at row 0
                    df_import = pd.read_excel(uploaded_file, header=0)
                    
                    # Strip whitespace from column names
                    df_import.columns = df_import.columns.str.strip()
                    
                    # Check if it's the line-item format (has Item column)
                    has_item_col = 'Item' in df_import.columns
                    has_price_col = 'Unit Price ($)' in df_import.columns or 'Line Total ($)' in df_import.columns
                    
                    if has_item_col and has_price_col:
                        # NEW FORMAT: Line-item data with quantities and prices
                        
                        # Filter to only rows with valid prices
                        price_col = 'Unit Price ($)' if 'Unit Price ($)' in df_import.columns else 'Line Total ($)'
                        df_import = df_import[df_import[price_col].notna() & (df_import[price_col] > 0)]
                        
                        st.success(f"Found {len(df_import)} line items with prices")
                        
                        # Clean up item names (take just the first part before catalog codes)
                        def clean_item_name(item_str):
                            if pd.isna(item_str):
                                return ""
                            item_str = str(item_str)
                            # Try to extract just the product name (before " - " or before catalog number patterns)
                            # Look for patterns like "Product Name - Pkg" or "Product 123456 EA"
                            parts = item_str.split(' - ')
                            if len(parts) > 1:
                                return parts[0].strip()[:100]
                            # Otherwise take first 100 chars
                            return item_str[:100].strip()
                        
                        df_import['Item_Clean'] = df_import['Item'].apply(clean_item_name)
                        
                        # Show preview with cleaned names
                        st.markdown("**Data Preview:**")
                        preview_df = pd.DataFrame()
                        preview_df['PO #'] = df_import['PO #'].astype(str) if 'PO #' in df_import.columns else ''
                        preview_df['Item'] = df_import['Item_Clean']
                        preview_df['Vendor'] = df_import['Vendor'] if 'Vendor' in df_import.columns else ''
                        preview_df['Qty'] = df_import['Quantity'] if 'Quantity' in df_import.columns else 1
                        preview_df['Unit Price'] = df_import['Unit Price ($)'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "") if 'Unit Price ($)' in df_import.columns else ''
                        preview_df['Line Total'] = df_import['Line Total ($)'].apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "") if 'Line Total ($)' in df_import.columns else ''
                        preview_df['Grant'] = df_import['Grant'] if 'Grant' in df_import.columns else ''
                        
                        st.dataframe(preview_df.head(20), use_container_width=True, height=350)
                        
                        if len(df_import) > 20:
                            st.caption(f"Showing 20 of {len(df_import)} items")
                        
                        # Show what will be imported
                        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
                        
                        st.markdown("""
                            <div style="background: #ecfdf5; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
                                <strong style="color: #059669;">This export includes all fields for ML predictions:</strong>
                                <div style="display: flex; gap: 2rem; margin-top: 0.5rem; color: #065f46;">
                                    <div>• Item Name<br>• Vendor<br>• Catalog #</div>
                                    <div>• Quantity<br>• Unit Price<br>• Line Total</div>
                                    <div>• Grant<br>• PO #<br>• Date Ordered</div>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                        
                        # Check for duplicates
                        df_orders = load_orders()
                        existing_items = set()
                        if not df_orders.empty:
                            for _, row in df_orders.iterrows():
                                key = f"{row.get('PO #', '')}_{str(row.get('ITEM', ''))[:30]}"
                                existing_items.add(key)
                        
                        # Count potential duplicates
                        dup_count = 0
                        for _, row in df_import.iterrows():
                            key = f"{row.get('PO #', '')}_{str(row.get('Item_Clean', ''))[:30]}"
                            if key in existing_items:
                                dup_count += 1
                        
                        new_count = len(df_import) - dup_count
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("New Items", new_count)
                        with col2:
                            st.metric("Duplicates (will skip)", dup_count)
                        
                        if st.button("Import Orders", type="primary", use_container_width=True):
                            imported_count = 0
                            skipped_count = 0
                            
                            for _, row in df_import.iterrows():
                                item_name = str(row.get('Item_Clean', ''))
                                if not item_name or len(item_name) < 3:
                                    continue
                                
                                po_num = str(row.get('PO #', ''))
                                
                                # Check for duplicate
                                key = f"{po_num}_{item_name[:30]}"
                                if key in existing_items:
                                    skipped_count += 1
                                    continue
                                
                                req_id = gen_req_id(df_orders)
                                
                                # Parse date
                                date_ordered = row.get('Date Ordered', '')
                                if pd.notna(date_ordered):
                                    try:
                                        if hasattr(date_ordered, 'strftime'):
                                            date_ordered = date_ordered.strftime('%Y-%m-%d')
                                        else:
                                            date_ordered = str(date_ordered).split(' ')[0].replace('/', '-')
                                    except:
                                        date_ordered = ''
                                else:
                                    date_ordered = ''
                                
                                # Parse numeric fields
                                try:
                                    qty = float(row.get('Quantity', 1)) if pd.notna(row.get('Quantity')) else 1
                                except:
                                    qty = 1
                                
                                # Unit Price = price per item, Line Total = total for line
                                try:
                                    unit_price = float(row.get('Unit Price ($)', 0)) if pd.notna(row.get('Unit Price ($)')) else 0
                                except:
                                    unit_price = 0
                                
                                try:
                                    total = float(row.get('Line Total ($)', 0)) if pd.notna(row.get('Line Total ($)')) else qty * unit_price
                                except:
                                    total = qty * unit_price
                                
                                # Get other fields
                                vendor = str(row.get('Vendor', ''))[:100] if pd.notna(row.get('Vendor')) else ''
                                # Clean vendor name
                                if 'Contract no value' in vendor:
                                    vendor = vendor.replace('Contract no value', '').strip()
                                
                                grant = str(row.get('Grant', '')) if pd.notna(row.get('Grant')) else ''
                                catalog = str(row.get('Catalog #', '')) if pd.notna(row.get('Catalog #')) else ''
                                ordered_by = str(row.get('Ordered By', '')) if pd.notna(row.get('Ordered By')) else ''
                                
                                new_row = {
                                    "REQ#": req_id,
                                    "ITEM": item_name[:200],
                                    "NUMBER OF ITEM": qty,
                                    "AMOUNT PER ITEM": unit_price,
                                    "TOTAL": total,
                                    "VENDOR": vendor,
                                    "CAT #": catalog,
                                    "GRANT USED": grant,
                                    "PO SOURCE": "ShopBlue",
                                    "PO #": po_num,
                                    "NOTES": "",
                                    "ORDERED BY": ordered_by,
                                    "DATE ORDERED": date_ordered,
                                    "DATE RECEIVED": "",
                                    "RECEIVED BY": "",
                                    "ITEM LOCATION": "",
                                    "LAB": lab_name,
                                }
                                
                                df_orders = pd.concat([df_orders, pd.DataFrame([new_row])], ignore_index=True)
                                existing_items.add(key)
                                imported_count += 1
                            
                            if imported_count > 0:
                                save_orders(df_orders)
                                st.success(f"Successfully imported {imported_count} items")
                                st.info("Data includes item details - ML predictions will now work!")
                            
                            if skipped_count > 0:
                                st.warning(f"Skipped {skipped_count} duplicates")
                    
                    else:
                        # Try OLD FORMAT: PO-level summary (header at row 9)
                        uploaded_file.seek(0)
                        df_import = pd.read_excel(uploaded_file, header=9)
                        
                        expected_cols = ['PO Number', 'Supplier', 'Total Amount']
                        if not all(col in df_import.columns for col in expected_cols):
                            st.error("Unrecognized file format.")
                            st.info("Expected: Item, Quantity, Unit Price columns (line-item) OR PO Number, Supplier, Total Amount (summary)")
                        else:
                            st.success(f"Found {len(df_import)} purchase orders (summary format)")
                            st.warning("This format lacks item details. ML predictions will be limited.")
                            
                            preview_cols = ['PO Number', 'Supplier', 'Total Amount']
                            st.dataframe(df_import[preview_cols].head(10), use_container_width=True)
                            
                            df_orders = load_orders()
                            existing_pos = set(df_orders['PO #'].astype(str).values) if 'PO #' in df_orders.columns else set()
                            
                            if st.button("Import Orders", type="primary", use_container_width=True):
                                imported_count = 0
                                skipped_count = 0
                                
                                for _, row in df_import.iterrows():
                                    po_num = str(row.get('PO Number', ''))
                                    
                                    if po_num in existing_pos:
                                        skipped_count += 1
                                        continue
                                    
                                    req_id = gen_req_id(df_orders)
                                    total_amount = float(row.get('Total Amount', 0)) if pd.notna(row.get('Total Amount')) else 0
                                    
                                    new_row = {
                                        "REQ#": req_id,
                                        "ITEM": "[Add item details]",
                                        "NUMBER OF ITEM": 1,
                                        "AMOUNT PER ITEM": total_amount,
                                        "TOTAL": total_amount,
                                        "VENDOR": str(row.get('Supplier', '')),
                                        "CAT #": "",
                                        "GRANT USED": "",
                                        "PO SOURCE": "ShopBlue",
                                        "PO #": po_num,
                                        "NOTES": "",
                                        "ORDERED BY": str(row.get('PO Owner', '')),
                                        "DATE ORDERED": "",
                                        "DATE RECEIVED": "",
                                        "RECEIVED BY": "",
                                        "ITEM LOCATION": "",
                                        "LAB": lab_name,
                                    }
                                    
                                    df_orders = pd.concat([df_orders, pd.DataFrame([new_row])], ignore_index=True)
                                    existing_pos.add(po_num)
                                    imported_count += 1
                                
                                if imported_count > 0:
                                    save_orders(df_orders)
                                    st.success(f"Imported {imported_count} orders")
                                
                                if skipped_count > 0:
                                    st.warning(f"Skipped {skipped_count} duplicates")
                
                except Exception as e:
                    st.error(f"Error reading file: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
        
        else:  # Lab Inventory file
            st.markdown("""
                <div class="info-box">
                    <strong>Expected format:</strong> Excel file with columns: Req#, Item, #, Amount, Total, Vendor (optional)
                </div>
            """, unsafe_allow_html=True)
            
            uploaded_file = st.file_uploader("Upload Inventory/Accounts File", type=["xlsx"], key="inventory_upload")
            
            if uploaded_file is not None:
                try:
                    xl = pd.ExcelFile(uploaded_file)
                    
                    if len(xl.sheet_names) > 1:
                        selected_sheet = st.selectbox("Select sheet:", xl.sheet_names)
                    else:
                        selected_sheet = xl.sheet_names[0]
                    
                    df_import = pd.read_excel(xl, sheet_name=selected_sheet)
                    df_import.columns = df_import.columns.str.strip()
                    
                    if 'Item' in df_import.columns:
                        df_import = df_import.dropna(subset=['Item'])
                        df_import = df_import[df_import['Item'].astype(str).str.len() > 2]
                        
                        st.success(f"Found {len(df_import)} items")
                        st.dataframe(df_import.head(10), use_container_width=True)
                        
                        grant_for_import = st.text_input("Grant for these orders:", value=selected_sheet if selected_sheet not in ['Sheet1'] else "")
                        
                        if st.button("Import Orders", type="primary", key="import_inv", use_container_width=True):
                            df_orders = load_orders()
                            
                            existing_reqs = set()
                            if not df_orders.empty and 'NOTES' in df_orders.columns:
                                for note in df_orders['NOTES'].astype(str).values:
                                    if 'Original Req#:' in note:
                                        try:
                                            orig = note.split('Original Req#:')[1].split('.')[0].strip()
                                            existing_reqs.add(orig)
                                        except:
                                            pass
                            
                            imported_count = 0
                            skipped_count = 0
                            
                            for _, row in df_import.iterrows():
                                orig_req = str(row.get('Req#', '')).replace('\xa0', '').strip()
                                
                                if orig_req and orig_req not in ['*', 'nan'] and orig_req in existing_reqs:
                                    skipped_count += 1
                                    continue
                                
                                item_name = str(row.get('Item', ''))
                                if not item_name or len(item_name) < 2:
                                    continue
                                
                                req_id = gen_req_id(df_orders)
                                
                                try:
                                    qty = float(str(row.get('#', 1)).replace('EA', '').replace('CS', '').strip() or 1)
                                except:
                                    qty = 1
                                
                                try:
                                    amount = float(row.get('Amount', 0)) if pd.notna(row.get('Amount')) else 0
                                except:
                                    amount = 0
                                
                                try:
                                    total = float(row.get('Total', 0)) if pd.notna(row.get('Total')) else qty * amount
                                except:
                                    total = qty * amount
                                
                                vendor = str(row.get('Vendor', '')) if 'Vendor' in row and pd.notna(row.get('Vendor')) else ''
                                
                                new_row = {
                                    "REQ#": req_id,
                                    "ITEM": item_name[:200],
                                    "NUMBER OF ITEM": qty,
                                    "AMOUNT PER ITEM": amount,
                                    "TOTAL": total,
                                    "VENDOR": vendor,
                                    "CAT #": "",
                                    "GRANT USED": grant_for_import,
                                    "PO SOURCE": "ShopBlue",
                                    "PO #": "",
                                    "NOTES": f"Original Req#: {orig_req}" if orig_req and orig_req not in ['*', 'nan'] else "",
                                    "ORDERED BY": "",
                                    "DATE ORDERED": "",
                                    "DATE RECEIVED": "",
                                    "RECEIVED BY": "",
                                    "ITEM LOCATION": "",
                                    "LAB": lab_name,
                                }
                                
                                df_orders = pd.concat([df_orders, pd.DataFrame([new_row])], ignore_index=True)
                                if orig_req and orig_req not in ['*', 'nan']:
                                    existing_reqs.add(orig_req)
                                imported_count += 1
                            
                            if imported_count > 0:
                                save_orders(df_orders)
                                st.success(f"Imported {imported_count} orders")
                            
                            if skipped_count > 0:
                                st.warning(f"Skipped {skipped_count} duplicates")
                    else:
                        st.error("Could not find 'Item' column")
                
                except Exception as e:
                    st.error(f"Error: {str(e)}")

# ============== TAB: All Orders ==============
with tab_table:
    section_header("All Orders")
    
    df = load_orders()
    df = filter_by_lab(df, user_email)
    
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    
    df = generate_alert_column(df)
    
    # Admin: Data Management
    if is_admin(user_email):
        
        # BULK MARK AS RECEIVED - Outside expander for easy access
        pending_orders = df[(df["DATE RECEIVED"].isna()) | (df["DATE RECEIVED"] == "")]
        
        if len(pending_orders) > 0:
            st.markdown(f"""
                <div style="background: #fef3c7; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
                    <strong style="color: #92400e;">{len(pending_orders)} orders pending</strong>
                </div>
            """, unsafe_allow_html=True)
            
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                bulk_date = st.date_input("Date Received", value=date.today(), key="bulk_recv_date")
            
            with col2:
                bulk_receiver = st.text_input("Received By", value=user_email.split('@')[0], key="bulk_recv_by")
            
            with col3:
                st.write("")  # Spacer
                st.write("")  # Spacer
                if st.button("MARK ALL AS RECEIVED", type="primary", use_container_width=True):
                    df_all = load_orders()
                    
                    # Update all rows where DATE RECEIVED is empty
                    mask = (df_all["DATE RECEIVED"].isna()) | (df_all["DATE RECEIVED"] == "")
                    df_all.loc[mask, "DATE RECEIVED"] = bulk_date.isoformat()
                    df_all.loc[mask, "RECEIVED BY"] = bulk_receiver
                    
                    save_orders(df_all)
                    st.success(f"Marked {mask.sum()} orders as received!")
                    st.rerun()
            
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        with st.expander("More Admin Tools"):
            
            # DATA REPAIR
            st.markdown("**Data Repair**")
            
            # Check for issues
            df_check = df.copy()
            df_check["TOTAL"] = pd.to_numeric(df_check["TOTAL"], errors='coerce').fillna(0)
            total_sum = df_check["TOTAL"].sum()
            
            if total_sum == 0 and len(df) > 0:
                st.warning("TOTAL column appears empty. Click below to recalculate from AMOUNT PER ITEM × NUMBER OF ITEM")
                
                if st.button("Recalculate All Totals", type="primary"):
                    df_all = load_orders()
                    
                    # Try to fix totals
                    for idx in df_all.index:
                        qty = df_all.loc[idx, "NUMBER OF ITEM"]
                        unit = df_all.loc[idx, "AMOUNT PER ITEM"]
                        
                        try:
                            qty = float(qty) if pd.notna(qty) else 1
                            unit = float(unit) if pd.notna(unit) else 0
                            df_all.loc[idx, "TOTAL"] = qty * unit
                        except:
                            df_all.loc[idx, "TOTAL"] = 0
                    
                    save_orders(df_all)
                    new_total = df_all["TOTAL"].sum()
                    st.success(f"Recalculated! New total: ${new_total:,.2f}")
                    st.rerun()
            
            # Show column diagnostics
            with st.expander("Debug: View Column Data"):
                st.write("**Sample of numeric columns:**")
                debug_cols = ["REQ#", "NUMBER OF ITEM", "AMOUNT PER ITEM", "TOTAL"]
                debug_cols = [c for c in debug_cols if c in df.columns]
                st.dataframe(df[debug_cols].head(10))
                
                st.write("**Column types:**")
                for col in ["NUMBER OF ITEM", "AMOUNT PER ITEM", "TOTAL"]:
                    if col in df.columns:
                        st.write(f"- {col}: {df[col].dtype}, non-null: {df[col].notna().sum()}, sum: {df[col].sum()}")
            
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
            
            st.markdown("**Delete Orders**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Delete individual order
                if not df.empty:
                    delete_options = df["REQ#"].tolist()
                    order_to_delete = st.selectbox("Select order to delete:", [""] + delete_options, key="delete_single")
                    
                    if order_to_delete:
                        order_info = df[df["REQ#"] == order_to_delete].iloc[0]
                        st.caption(f"Item: {order_info.get('ITEM', 'N/A')[:50]}")
                        st.caption(f"Vendor: {order_info.get('VENDOR', 'N/A')}")
                        st.caption(f"Total: ${order_info.get('TOTAL', 0):,.2f}")
                        
                        if st.button("Delete This Order", type="secondary"):
                            df_all = load_orders()
                            df_all = df_all[df_all["REQ#"] != order_to_delete]
                            save_orders(df_all)
                            st.success(f"Deleted order {order_to_delete}")
                            st.rerun()
            
            with col2:
                # Delete all orders
                st.markdown("**Delete All Orders**")
                st.warning("This will permanently delete all orders from the database.")
                
                confirm_text = st.text_input("Type DELETE to confirm:", key="confirm_delete_all")
                
                if st.button("Delete All Orders", type="secondary"):
                    if confirm_text == "DELETE":
                        # Clear all orders
                        empty_df = pd.DataFrame(columns=REQUIRED_COLUMNS)
                        save_orders(empty_df)
                        st.success("All orders deleted")
                        st.rerun()
                    else:
                        st.error("Type DELETE to confirm")
            
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
            
            # Delete by filter
            st.markdown("**Delete Orders by Filter**")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                delete_by_vendor = st.text_input("Delete by Vendor:", placeholder="e.g., Fisher Scientific")
            
            with col2:
                delete_by_po = st.text_input("Delete by PO #:", placeholder="e.g., 1481052")
            
            with col3:
                delete_imported = st.checkbox("Delete all imported orders (items starting with '[')")
            
            if st.button("Delete Matching Orders", type="secondary"):
                df_all = load_orders()
                initial_count = len(df_all)
                
                if delete_by_vendor:
                    df_all = df_all[~df_all["VENDOR"].astype(str).str.contains(delete_by_vendor, case=False, na=False)]
                
                if delete_by_po:
                    df_all = df_all[df_all["PO #"].astype(str) != delete_by_po]
                
                if delete_imported:
                    df_all = df_all[~df_all["ITEM"].astype(str).str.startswith("[")]
                
                deleted_count = initial_count - len(df_all)
                
                if deleted_count > 0:
                    save_orders(df_all)
                    st.success(f"Deleted {deleted_count} orders")
                    st.rerun()
                else:
                    st.info("No matching orders found")
    
    # Filters in a clean row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        vendor_filter = st.text_input("Vendor", placeholder="Filter...")
    with col2:
        grant_filter = st.text_input("Grant", placeholder="Filter...")
    with col3:
        po_source_filter = st.selectbox("Source", ["All", "ShopBlue", "Stock Room", "External Vendor"])
    with col4:
        status_filter = st.selectbox("Status", ["All", "Pending", "Received"])
    
    # Apply filters
    filtered = df.copy()
    
    if vendor_filter:
        filtered = filtered[filtered["VENDOR"].astype(str).str.contains(vendor_filter, case=False, na=False)]
    if grant_filter:
        filtered = filtered[filtered["GRANT USED"].astype(str).str.contains(grant_filter, case=False, na=False)]
    if po_source_filter != "All":
        filtered = filtered[filtered["PO SOURCE"] == po_source_filter]
    if status_filter == "Pending":
        filtered = filtered[(filtered["DATE RECEIVED"].isna()) | (filtered["DATE RECEIVED"] == "")]
    elif status_filter == "Received":
        filtered = filtered[(filtered["DATE RECEIVED"].notna()) & (filtered["DATE RECEIVED"] != "")]
    
    st.caption(f"Showing {len(filtered)} of {len(df)} orders")
    
    if not filtered.empty:
        display_cols = ["REQ#", "ITEM", "VENDOR", "TOTAL", "PO #", "DATE ORDERED", "ALERT"]
        display_cols = [c for c in display_cols if c in filtered.columns]
        st.dataframe(filtered[display_cols], use_container_width=True, height=400)
        
        # Edit section
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        section_header("Edit Order")
        
        req_options = filtered["REQ#"].tolist()
        selected_req = st.selectbox("Select order to edit:", [""] + req_options)
        
        if selected_req:
            order_row = filtered[filtered["REQ#"] == selected_req].iloc[0]
            
            with st.form("edit_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    edit_item = st.text_input("Item", value=str(order_row.get("ITEM", "")))
                    edit_cat = st.text_input("Catalog #", value=str(order_row.get("CAT #", "")))
                    edit_grant = st.text_input("Grant", value=str(order_row.get("GRANT USED", "")))
                    edit_qty = st.number_input("Quantity", value=float(order_row.get("NUMBER OF ITEM", 1)))
                    edit_unit = st.number_input("Unit Price", value=float(order_row.get("AMOUNT PER ITEM", 0)), format="%.2f")
                
                with col2:
                    edit_notes = st.text_area("Notes", value=str(order_row.get("NOTES", "")))
                    edit_location = st.text_input("Location", value=str(order_row.get("ITEM LOCATION", "")))
                    
                    current_received = order_row.get("DATE RECEIVED", "")
                    is_received = pd.notna(current_received) and current_received != ""
                    mark_received = st.checkbox("Received", value=is_received)
                    
                    if mark_received:
                        edit_date_recv = st.date_input("Date Received", value=date.today())
                        edit_recv_by = st.text_input("Received By", value=str(order_row.get("RECEIVED BY", "")))
                    else:
                        edit_date_recv = None
                        edit_recv_by = ""
                
                if st.form_submit_button("Save Changes", type="primary"):
                    df_all = load_orders()
                    idx = df_all[df_all["REQ#"] == selected_req].index
                    
                    if len(idx) > 0:
                        df_all.loc[idx, "ITEM"] = edit_item
                        df_all.loc[idx, "CAT #"] = edit_cat
                        df_all.loc[idx, "GRANT USED"] = edit_grant
                        df_all.loc[idx, "NUMBER OF ITEM"] = edit_qty
                        df_all.loc[idx, "AMOUNT PER ITEM"] = edit_unit
                        df_all.loc[idx, "TOTAL"] = edit_qty * edit_unit
                        df_all.loc[idx, "NOTES"] = edit_notes
                        df_all.loc[idx, "ITEM LOCATION"] = edit_location
                        
                        if mark_received and edit_date_recv:
                            df_all.loc[idx, "DATE RECEIVED"] = edit_date_recv.isoformat()
                            df_all.loc[idx, "RECEIVED BY"] = edit_recv_by
                        else:
                            df_all.loc[idx, "DATE RECEIVED"] = ""
                            df_all.loc[idx, "RECEIVED BY"] = ""
                        
                        save_orders(df_all)
                        st.success("Order updated")
                        st.rerun()
    else:
        st.info("No orders found")

# ============== TAB: Analytics ==============
with tab_analytics:
    section_header("Analytics")
    
    df = load_orders()
    df = filter_by_lab(df, user_email)
    
    if df.empty:
        st.info("Add orders to see analytics")
    else:
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        
        # Safely calculate total spending
        if 'TOTAL' in df.columns:
            df['TOTAL'] = pd.to_numeric(df['TOTAL'], errors='coerce').fillna(0)
            total_spending = df['TOTAL'].sum()
        else:
            total_spending = 0
        
        with col1:
            metric_card("Total Orders", f"{len(df):,}")
        with col2:
            metric_card("Total Spent", f"${total_spending:,.2f}")
        with col3:
            metric_card("Vendors", f"{df['VENDOR'].nunique()}" if 'VENDOR' in df.columns else "0")
        with col4:
            pending = len(df[(df["DATE RECEIVED"].isna()) | (df["DATE RECEIVED"] == "")])
            metric_card("Pending", str(pending), "warning" if pending > 5 else "success")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # ========== YEARLY SPENDING BY GRANT ==========
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        section_header("Yearly Spending by Grant")
        
        # Parse dates and extract year
        df_dated = df.copy()
        df_dated['DATE ORDERED'] = pd.to_datetime(df_dated['DATE ORDERED'], errors='coerce')
        df_dated = df_dated[df_dated['DATE ORDERED'].notna()]
        df_dated['YEAR'] = df_dated['DATE ORDERED'].dt.year
        
        if len(df_dated) > 0 and 'GRANT USED' in df_dated.columns:
            # Get unique grants and years
            grants = df_dated['GRANT USED'].dropna().unique()
            grants = [g for g in grants if str(g).strip() and str(g) != 'nan']
            years = sorted(df_dated['YEAR'].dropna().unique())
            
            if len(grants) > 0 and len(years) > 0:
                # Create pivot table: Year x Grant
                yearly_grant = df_dated.groupby(['YEAR', 'GRANT USED'])['TOTAL'].sum().unstack(fill_value=0)
                
                # Display table
                st.markdown("**Spending by Year and Grant**")
                
                # Format as currency
                display_yearly = yearly_grant.copy()
                display_yearly.loc['TOTAL'] = display_yearly.sum()
                display_yearly['YEAR TOTAL'] = display_yearly.sum(axis=1)
                
                # Format for display
                formatted = display_yearly.apply(lambda col: col.apply(lambda x: f"${x:,.2f}" if pd.notna(x) else "$0.00"))
                st.dataframe(formatted, use_container_width=True)
                
                # Projections for next year
                st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
                st.markdown("**Next Year Projections**")
                
                current_year = int(max(years))
                next_year = current_year + 1
                
                projection_data = []
                
                for grant in grants:
                    grant_str = str(grant)
                    if grant_str in yearly_grant.columns:
                        grant_history = yearly_grant[grant_str]
                        
                        # Calculate projection based on trend
                        values = grant_history.values
                        years_list = list(grant_history.index)
                        
                        if len(values) >= 2:
                            # Linear regression for trend
                            x = np.array(range(len(values)))
                            y = np.array(values)
                            
                            # Calculate slope and intercept
                            n = len(x)
                            slope = (n * np.sum(x * y) - np.sum(x) * np.sum(y)) / (n * np.sum(x**2) - np.sum(x)**2)
                            intercept = (np.sum(y) - slope * np.sum(x)) / n
                            
                            # Project next year
                            projected = intercept + slope * len(values)
                            projected = max(0, projected)  # Can't be negative
                            
                            # Calculate growth rate
                            if values[-1] > 0:
                                growth = ((projected - values[-1]) / values[-1]) * 100
                            else:
                                growth = 0
                            
                            trend = "Up" if growth > 5 else "Down" if growth < -5 else "Stable"
                            
                        else:
                            # Only one year of data - use same value
                            projected = values[-1] if len(values) > 0 else 0
                            growth = 0
                            trend = "Stable"
                        
                        last_year_spend = values[-1] if len(values) > 0 else 0
                        
                        projection_data.append({
                            'Grant': grant_str,
                            f'{current_year} Actual': f"${last_year_spend:,.2f}",
                            f'{next_year} Projected': f"${projected:,.2f}",
                            'Trend': trend,
                            'Change': f"{growth:+.1f}%"
                        })
                
                if projection_data:
                    proj_df = pd.DataFrame(projection_data)
                    
                    # Style the trend column
                    def style_trend(val):
                        if val == "Up":
                            return "color: #dc2626"
                        elif val == "Down":
                            return "color: #059669"
                        return "color: #6b7280"
                    
                    st.dataframe(proj_df, use_container_width=True)
                    
                    # Total projection
                    total_current = df_dated[df_dated['YEAR'] == current_year]['TOTAL'].sum()
                    total_projected = sum([float(p[f'{next_year} Projected'].replace('$', '').replace(',', '')) for p in projection_data])
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        metric_card(f"{current_year} Total", f"${total_current:,.2f}")
                    with col2:
                        metric_card(f"{next_year} Projected", f"${total_projected:,.2f}")
                    with col3:
                        change_pct = ((total_projected - total_current) / total_current * 100) if total_current > 0 else 0
                        metric_card("Projected Change", f"{change_pct:+.1f}%", "warning" if change_pct > 10 else "success")
                
                # Chart: Yearly spending by grant
                st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
                st.markdown("**Spending Trend by Grant**")
                
                fig, ax = plt.subplots(figsize=(10, 5))
                yearly_grant.plot(kind='bar', ax=ax, width=0.8)
                ax.set_xlabel("Year")
                ax.set_ylabel("Spending ($)")
                ax.legend(title="Grant", bbox_to_anchor=(1.02, 1), loc='upper left')
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                plt.xticks(rotation=0)
                plt.tight_layout()
                st.pyplot(fig)
                
            else:
                st.info("Need orders with dates and grants for yearly analysis")
        else:
            st.info("Need orders with dates for yearly analysis")
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Top Items by Order Count**")
            if "ITEM" in df.columns:
                counts = df["ITEM"].value_counts().head(8)
                fig, ax = plt.subplots(figsize=(8, 5))
                counts.plot(kind="barh", ax=ax, color="#1e3a5f")
                ax.set_xlabel("Orders")
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                plt.tight_layout()
                st.pyplot(fig)
        
        with col2:
            st.markdown("**Top Vendors**")
            if "VENDOR" in df.columns:
                vendor_counts = df["VENDOR"].value_counts().head(8)
                fig, ax = plt.subplots(figsize=(8, 5))
                vendor_counts.plot(kind="barh", ax=ax, color="#059669")
                ax.set_xlabel("Orders")
                ax.spines['top'].set_visible(False)
                ax.spines['right'].set_visible(False)
                plt.tight_layout()
                st.pyplot(fig)
        
        # ML Insights
        if len(df) >= 10:
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
            section_header("ML Insights")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Reorder Predictions**")
                try:
                    predictions = predict_reorder_date(df)
                    if not predictions.empty:
                        st.dataframe(predictions.head(5), use_container_width=True)
                    else:
                        st.caption("Not enough data")
                except:
                    st.caption("Unable to generate predictions")
            
            with col2:
                st.markdown("**Anomaly Detection**")
                try:
                    anomalies = detect_anomalies(df)
                    if not anomalies.empty:
                        st.warning(f"{len(anomalies)} unusual orders detected")
                        st.dataframe(anomalies.head(5), use_container_width=True)
                    else:
                        st.success("No anomalies detected")
                except:
                    st.caption("Unable to run detection")

# ============== TAB: Export ==============
with tab_export:
    section_header("Export Data")
    
    df = load_orders()
    df = filter_by_lab(df, user_email)
    
    if df.empty:
        st.info("No data to export")
    else:
        st.markdown(f"**{len(df)} orders** ready to export")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
                <div style="background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 1.5rem; text-align: center;">
                    <div style="font-size: 2rem; margin-bottom: 0.5rem;">📄</div>
                    <div style="font-weight: 600; margin-bottom: 0.5rem;">CSV Format</div>
                    <div style="font-size: 0.875rem; color: #6b7280; margin-bottom: 1rem;">Compatible with Excel, Google Sheets</div>
                </div>
            """, unsafe_allow_html=True)
            
            csv_data = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download CSV",
                csv_data,
                f"Requiva_Orders_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv",
                use_container_width=True
            )
        
        with col2:
            st.markdown("""
                <div style="background: white; border: 1px solid #e5e7eb; border-radius: 12px; padding: 1.5rem; text-align: center;">
                    <div style="font-size: 2rem; margin-bottom: 0.5rem;">📊</div>
                    <div style="font-weight: 600; margin-bottom: 0.5rem;">Excel Format</div>
                    <div style="font-size: 0.875rem; color: #6b7280; margin-bottom: 1rem;">Formatted spreadsheet</div>
                </div>
            """, unsafe_allow_html=True)
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Orders", index=False)
            
            st.download_button(
                "Download Excel",
                output.getvalue(),
                f"Requiva_Orders_{datetime.now().strftime('%Y%m%d')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        with st.expander("Preview Data"):
            st.dataframe(df.head(10), use_container_width=True)

# Footer
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown("""
    <div style="text-align: center; color: #6b7280; font-size: 0.875rem;">
        <strong>Requiva</strong> · Lab Order Management<br>
        Adelaiye-Ogala Lab · University at Buffalo
    </div>
""", unsafe_allow_html=True)
