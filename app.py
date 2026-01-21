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
)

from ml_engine import (
    predict_reorder_date,
    forecast_spending,
    detect_anomalies,
    recommend_vendors,
    forecast_demand,
    get_bulk_opportunities,
)

st.set_page_config(
    page_title="Requiva - Lab Order Management", 
    page_icon="🔬", 
    layout="wide"
)

# Initialize session state
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None
if "show_create_account" not in st.session_state:
    st.session_state.show_create_account = False
if "show_reset_password" not in st.session_state:
    st.session_state.show_reset_password = False

# Debug Info in Sidebar (Shows Firebase Connection Status)
with st.sidebar:
    st.markdown("---")
    with st.expander("🔍 System Status"):
        st.write(f"**Backend:** {'Firestore ✅' if USE_FIRESTORE else 'CSV (Dev Mode) ⚠️'}")
        
        # Check environment variables
        firebase_json_exists = bool(os.getenv("FIREBASE_JSON"))
        old_var_exists = bool(os.getenv("firebase-service-account.json"))
        
        st.write(f"**FIREBASE_JSON:** {'✅ Set' if firebase_json_exists else '❌ Not Set'}")
        
        if old_var_exists:
            st.warning("⚠️ Old variable 'firebase-service-account.json' detected. Rename to 'FIREBASE_JSON'")
        
        if USE_FIRESTORE:
            st.success("✅ Firestore Connected")
        else:
            st.error("❌ Firestore Not Connected")
            st.caption("Add FIREBASE_JSON env variable to enable Firestore")

# Authentication Check
user_email = check_auth_status()

if not user_email:
    # Show Login Page
    st.title("🔬 Requiva - Lab Order Management System")
    st.markdown("### Welcome! Please login to continue")
    
    # Login Form
    login_form()
    
    st.markdown("---")
    
    # Create Account Section
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("📝 Don't have an account? Create one below.")
        with st.expander("Create New Account", expanded=False):
            new_email = st.text_input("Email", key="new_account_email", placeholder="your.email@example.com")
            new_password = st.text_input("Password", type="password", key="new_account_password", placeholder="Min 6 characters")
            
            if st.button("Create Account", type="primary", key="create_account_btn"):
                if not new_email or not new_password:
                    st.error("❌ Email and password are required")
                elif len(new_password) < 6:
                    st.error("❌ Password must be at least 6 characters")
                else:
                    success, msg = create_account(new_email, new_password)
                    if success:
                        st.success(f"✅ {msg}")
                        st.info("Please login with your new credentials above")
                    else:
                        st.error(f"❌ {msg}")
    
    with col2:
        st.info("🔑 Forgot your password?")
        with st.expander("Request Password Reset", expanded=False):
            reset_email = st.text_input("Your Email", key="reset_email", placeholder="your.email@example.com")
            
            if st.button("Request Reset", type="secondary", key="reset_password_btn"):
                if not reset_email:
                    st.error("❌ Email is required")
                else:
                    success, msg = reset_password_request(reset_email)
                    if success:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")
    
    # Helpful tips for first-time users
    st.markdown("---")
    st.markdown("### 💡 Getting Started")
    st.markdown("""
    **For Lab Users:**
    - Create account with your lab email
    - Access your lab's orders
    - Track inventory and spending
    - View analytics for your lab
    
    **Features:**
    - Real-time order tracking
    - ML-powered predictions
    - Automated reporting
    - Multi-lab support
    """)
    
    show_login_warning()
    st.stop()

# User is logged in - Show Main App
lab_name = get_user_lab(user_email)

# Sidebar User Info
st.sidebar.title("👤 User Info")
st.sidebar.success(f"**Lab:** {lab_name}")
st.sidebar.info(f"**Email:** {user_email}")

if is_admin(user_email):
    st.sidebar.warning("🔑 **Admin Access**")
    st.sidebar.caption("You can see all labs")

if st.sidebar.button("🚪 Logout", key="logout_btn", type="primary"):
    st.session_state.auth_user = None
    st.success("Logged out successfully!")
    st.rerun()

# Main App Title
st.title("🔬 Requiva - Lab Order Management System")

# Backend Status Banner
if USE_FIRESTORE:
    st.success("✅ Connected to Firestore - Production Mode")
else:
    st.warning("⚠️ Using local CSV - Development Mode. Add Firebase credentials to enable cloud storage.")

# Main Tabs
tab_new, tab_table, tab_analytics, tab_ml_insights, tab_export = st.tabs([
    "📝 New Order", 
    "📊 Orders Table", 
    "📈 Analytics", 
    "🤖 ML Insights",
    "💾 Export"
])

# TAB 1: New Order
with tab_new:
    st.subheader("Create a New Order")
    
    df = load_orders()
    df = filter_by_lab(df, user_email)
    
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**📦 Item Details**")
        item = st.text_input(
            "ITEM *", 
            placeholder="e.g., Fetal Bovine Serum (FBS) 500 mL", 
            key="new_item",
            help="Name and description of the item"
        )
        vendor = st.text_input(
            "VENDOR *", 
            placeholder="e.g., Thermo Fisher", 
            key="new_vendor",
            help="Supplier or vendor name"
        )
        cat_no = st.text_input(
            "CAT #", 
            placeholder="e.g., 12345-TF", 
            key="new_cat",
            help="Catalog or part number"
        )
        grant_used = st.text_input(
            "GRANT USED", 
            placeholder="e.g., R01CA12345", 
            key="new_grant",
            help="Grant number(s) - comma separated if multiple"
        )

    with col2:
        st.markdown("**💰 Pricing & Purchase**")
        qty = st.number_input(
            "NUMBER OF ITEMS *", 
            min_value=0.0, 
            value=1.0, 
            step=1.0, 
            key="new_qty",
            help="Quantity to order"
        )
        unit_price = st.number_input(
            "AMOUNT PER ITEM *", 
            min_value=0.0, 
            value=0.0, 
            step=1.0, 
            format="%.2f", 
            key="new_price",
            help="Price per unit in USD"
        )
        
        # Show calculated total
        if qty > 0 and unit_price > 0:
            calculated_total = qty * unit_price
            st.metric("Calculated Total", f"${calculated_total:,.2f}")
        
        po_source = st.selectbox(
            "PO SOURCE", 
            ["ShopBlue", "Stock Room", "External Vendor"], 
            index=0, 
            key="new_po_source",
            help="Purchase order source"
        )
        po_no = st.text_input(
            "PO #", 
            placeholder="e.g., PO-2025-00123", 
            key="new_po_no",
            help="Purchase order number"
        )

    with col3:
        st.markdown("**📋 Additional Info**")
        notes = st.text_area(
            "NOTES", 
            placeholder="Any notes (urgent, storage requirements, etc.)", 
            key="new_notes",
            help="Special instructions or notes"
        )
        ordered_by = st.text_input(
            "ORDERED BY", 
            placeholder="Your name", 
            value=user_email.split('@')[0],
            key="new_ordered_by",
            help="Person placing the order"
        )
        date_ordered = st.date_input(
            "DATE ORDERED", 
            value=date.today(), 
            key="new_date_ordered",
            help="Date the order was placed"
        )
        
        st.markdown("**📥 Receipt Information (Optional)**")
        received_flag = st.checkbox("Item already received?", key="new_received_flag")
        
        if received_flag:
            date_received = st.date_input(
                "DATE RECEIVED", 
                value=date.today(), 
                key="new_date_received"
            )
            received_by = st.text_input(
                "RECEIVED BY", 
                placeholder="Receiver name", 
                key="new_received_by"
            )
            location = st.text_input(
                "ITEM LOCATION", 
                placeholder="e.g., Freezer A, Shelf 2", 
                key="new_location"
            )
        else:
            date_received = None
            received_by = ""
            location = ""

    st.markdown("---")
    
    # Submit button
    col_submit, col_clear = st.columns([1, 4])
    
    with col_submit:
        if st.button("➕ Add Order", type="primary", key="submit_order", use_container_width=True):
            ok, msg = validate_order(item, qty, unit_price, vendor)
            
            if not ok:
                st.error(f"❌ {msg}")
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
                
                st.success(f"✅ Order {req_id} added successfully! Total: ${total:,.2f}")
                
                # ML Anomaly Detection
                try:
                    anomaly_score = detect_anomalies(df, new_row)
                    if anomaly_score > 0.7:
                        st.warning(f"⚠️ Unusual order detected (anomaly score: {anomaly_score:.2f}). Please verify pricing and quantity.")
                except Exception as e:
                    pass  # Silent fail for ML features
                
                st.info("🔄 Refresh the 'Orders Table' tab to see your new order")

# TAB 2: Orders Table
with tab_table:
    st.subheader("Orders Table")
    
    df = load_orders()
    df = filter_by_lab(df, user_email)
    
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    
    df = generate_alert_column(df)

    # Filters
    st.markdown("### 🔍 Filters")
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        vendor_filter = st.text_input("Filter by VENDOR", key="filter_vendor", placeholder="Type vendor name...")
    with c2:
        grant_filter = st.text_input("Filter by GRANT", key="filter_grant", placeholder="Type grant number...")
    with c3:
        po_source_filter = st.selectbox("PO SOURCE", ["All", "ShopBlue", "Stock Room", "External Vendor"], key="filter_po")
    with c4:
        status_filter = st.selectbox("STATUS", ["All", "Pending", "Received"], key="filter_status")

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

    # Display results
    st.markdown(f"**Showing {len(filtered)} of {len(df)} orders**")
    
    if not filtered.empty:
        display_columns = [col for col in ["REQ#", "ITEM", "VENDOR", "TOTAL", "DATE ORDERED", "RECEIVED BY", "ALERT"] if col in filtered.columns]
        st.dataframe(filtered[display_columns], use_container_width=True, height=400)
        
        # Pending items warning
        overdue = filter_unreceived_orders(filtered)
        if not overdue.empty:
            st.warning(f"⚠️ {len(overdue)} items pending receipt")
            with st.expander("View Pending Items"):
                pending_display = [col for col in ["REQ#", "ITEM", "VENDOR", "DATE ORDERED"] if col in overdue.columns]
                st.dataframe(overdue[pending_display], use_container_width=True)
        else:
            st.success("✅ All items have been marked as received")
    else:
        st.info("No orders match your filters. Try adjusting the search criteria.")

# TAB 3: Analytics
with tab_analytics:
    st.subheader("📈 Analytics Dashboard")
    
    df = load_orders()
    df = filter_by_lab(df, user_email)
    
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    if not df.empty and "ITEM" in df.columns:
        # Key Metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_orders = len(df)
            st.metric("Total Orders", f"{total_orders:,}")
        
        with col2:
            if "TOTAL" in df.columns:
                total_spending = df["TOTAL"].sum()
                st.metric("Total Spending", f"${total_spending:,.2f}")
        
        with col3:
            pending = len(df[(df["DATE RECEIVED"].isna()) | (df["DATE RECEIVED"] == "")])
            st.metric("Pending Items", pending)
        
        with col4:
            unique_vendors = df["VENDOR"].nunique()
            st.metric("Unique Vendors", unique_vendors)
        
        st.markdown("---")
        
        # Charts
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.markdown("### Top 10 Ordered Items")
            counts = df["ITEM"].value_counts().head(10)
            fig, ax = plt.subplots(figsize=(8, 5))
            counts.plot(kind="barh", ax=ax, color="#1f77b4")
            ax.set_xlabel("Number of Orders")
            ax.set_ylabel("Item")
            ax.set_title("Most Frequently Ordered Items")
            plt.tight_layout()
            st.pyplot(fig)
        
        with col_chart2:
            st.markdown("### Top 5 Vendors by Orders")
            if "VENDOR" in df.columns:
                vendor_counts = df["VENDOR"].value_counts().head(5)
                fig, ax = plt.subplots(figsize=(8, 5))
                vendor_counts.plot(kind="bar", ax=ax, color="#2ca02c")
                ax.set_xlabel("Vendor")
                ax.set_ylabel("Number of Orders")
                ax.set_title("Most Used Vendors")
                ax.tick_params(axis='x', rotation=45)
                plt.tight_layout()
                st.pyplot(fig)
    else:
        st.info("📊 No data available yet. Add orders to see analytics.")
        st.markdown("Analytics will show:")
        st.markdown("- Total orders and spending")
        st.markdown("- Top ordered items")
        st.markdown("- Vendor usage statistics")
        st.markdown("- Spending trends over time")

# TAB 4: ML Insights
with tab_ml_insights:
    st.subheader("🤖 Machine Learning Insights")
    st.caption("Powered by predictive analytics and anomaly detection")
    
    df = load_orders()
    df = filter_by_lab(df, user_email)
    
    if df.empty or len(df) < 10:
        st.info("📊 Need at least 10 orders to generate ML predictions. Keep adding orders!")
        st.markdown("**ML Features Available:**")
        st.markdown("- ⏰ Predictive reordering based on usage patterns")
        st.markdown("- 💰 Spending forecasts for budget planning")
        st.markdown("- 🚨 Anomaly detection for unusual orders")
        st.markdown("- 🏆 Vendor recommendations based on history")
        st.markdown("- 📦 Bulk order optimization opportunities")
    else:
        ml_tab1, ml_tab2, ml_tab3, ml_tab4 = st.tabs([
            "⏰ Reorder Predictions",
            "💰 Spending Forecast", 
            "🚨 Anomaly Detection",
            "🏆 Recommendations"
        ])
        
        with ml_tab1:
            st.markdown("### Predictive Reordering")
            st.write("Items that may need reordering soon based on usage patterns:")
            
            try:
                reorder_predictions = predict_reorder_date(df)
                if not reorder_predictions.empty:
                    st.dataframe(reorder_predictions, use_container_width=True)
                    st.caption("🔮 Predictions based on historical ordering frequency")
                else:
                    st.info("No reorder predictions available. Need more historical data with consistent items.")
            except Exception as e:
                st.error(f"Error generating predictions: {e}")
        
        with ml_tab2:
            st.markdown("### Spending Forecast")
            
            forecast_months = st.slider("Forecast period (months)", 1, 12, 3, key="forecast_slider")
            
            try:
                spending_forecast = forecast_spending(df, months=forecast_months)
                
                if spending_forecast:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Predicted Spending", f"${spending_forecast['total_forecast']:,.2f}")
                    with col2:
                        st.metric("Average Monthly", f"${spending_forecast['monthly_avg']:,.2f}")
                    
                    # Chart
                    fig, ax = plt.subplots(figsize=(10, 4))
                    ax.plot(spending_forecast['dates'], spending_forecast['amounts'], marker='o', linewidth=2)
                    ax.set_xlabel("Month")
                    ax.set_ylabel("Predicted Spending ($)")
                    ax.set_title(f"Spending Forecast - Next {forecast_months} Months")
                    ax.grid(True, alpha=0.3)
                    plt.xticks(rotation=45)
                    plt.tight_layout()
                    st.pyplot(fig)
                    
                    if 'by_grant' in spending_forecast:
                        st.markdown("#### Spending by Grant")
                        grant_df = pd.DataFrame(spending_forecast['by_grant'].items(), columns=['Grant', 'Predicted Amount'])
                        grant_df['Predicted Amount'] = grant_df['Predicted Amount'].apply(lambda x: f"${x:,.2f}")
                        st.dataframe(grant_df, use_container_width=True)
                else:
                    st.info("Unable to generate forecast. Need more historical spending data.")
            except Exception as e:
                st.error(f"Error generating forecast: {e}")
        
        with ml_tab3:
            st.markdown("### Anomaly Detection")
            st.write("Machine learning flagged these orders as unusual:")
            
            try:
                anomalies = detect_anomalies(df)
                if not anomalies.empty:
                    st.warning(f"⚠️ Found {len(anomalies)} potential anomalies")
                    display_cols = [col for col in ['REQ#', 'ITEM', 'VENDOR', 'TOTAL', 'ANOMALY_SCORE'] if col in anomalies.columns]
                    st.dataframe(anomalies[display_cols], use_container_width=True)
                    st.caption("💡 Anomalies may indicate data entry errors, unusual bulk orders, or price changes")
                else:
                    st.success("✅ No anomalies detected. All orders appear normal.")
            except Exception as e:
                st.error(f"Error detecting anomalies: {e}")
        
        with ml_tab4:
            st.markdown("### Recommendations")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🏆 Recommended Vendors")
                try:
                    vendor_recs = recommend_vendors(df)
                    if vendor_recs:
                        for item, vendors in list(vendor_recs.items())[:5]:
                            with st.container():
                                st.markdown(f"**{item}**")
                                st.markdown(f"→ Suggested: {', '.join(vendors)}")
                                st.markdown("---")
                    else:
                        st.info("Need more order history for vendor recommendations")
                except Exception as e:
                    st.error(f"Error: {e}")
            
            with col2:
                st.markdown("#### 📦 Bulk Order Opportunities")
                try:
                    bulk_opps = get_bulk_opportunities(df)
                    if bulk_opps:
                        for item, data in list(bulk_opps.items())[:5]:
                            with st.container():
                                st.markdown(f"**{item}**")
                                st.markdown(f"→ Suggested: {data['suggested_qty']} units")
                                st.markdown(f"💰 Potential savings: ${data['potential_savings']:.2f}")
                                st.markdown("---")
                    else:
                        st.info("No bulk opportunities identified yet")
                except Exception as e:
                    st.error(f"Error: {e}")

# TAB 5: Export
with tab_export:
    st.subheader("💾 Download Orders")
    st.write("Export your order data in CSV or Excel format")
    
    df = load_orders()
    df = filter_by_lab(df, user_email)
    
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    
    df_export = df[[col for col in REQUIRED_COLUMNS if col in df.columns]]
    
    if not df_export.empty:
        st.metric("Total Orders to Export", len(df_export))
        
        col1, col2 = st.columns(2)
        
        with col1:
            # CSV Export
            csv_bytes = df_export.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📄 Download CSV",
                data=csv_bytes,
                file_name=f"Requiva_Orders_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                type="primary",
                use_container_width=True
            )
            st.caption("CSV format - Compatible with Excel, Google Sheets, etc.")
        
        with col2:
            # Excel Export
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_export.to_excel(writer, sheet_name="Orders", index=False)
            
            st.download_button(
                label="📊 Download Excel",
                data=output.getvalue(),
                file_name=f"Requiva_Orders_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="secondary",
                use_container_width=True
            )
            st.caption("Excel format - Formatted for professional reporting")
        
        # Preview
        with st.expander("📋 Preview Export Data"):
            st.dataframe(df_export.head(10), use_container_width=True)
            st.caption(f"Showing first 10 of {len(df_export)} records")
    else:
        st.info("No orders to export yet. Add orders first!")

# Footer
st.markdown("---")
st.markdown("### 🔬 Requiva - Lab Order Management System")
st.caption("Powered by Machine Learning & Predictive Analytics")
st.caption("Developed by Tobilola Ogunbowale | University at Buffalo")
st.caption(f"Version 2.0 | Last updated: {datetime.now().strftime('%B %Y')}")
