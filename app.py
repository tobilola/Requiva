from datetime import date, datetime
from io import BytesIO
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import numpy as np

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

st.set_page_config(page_title="Requiva - Lab Order Management", page_icon="🔬", layout="wide")

if "auth_user" not in st.session_state:
    st.session_state.auth_user = None
if "show_create_account" not in st.session_state:
    st.session_state.show_create_account = False
if "show_reset_password" not in st.session_state:
    st.session_state.show_reset_password = False

user_email = check_auth_status()
if not user_email:
    login_form()
    st.info("Don't have an account? Create one below.")
    with st.expander("Create Account"):
        new_email = st.text_input("New Email")
        new_password = st.text_input("New Password", type="password")
        if st.button("Create Account"):
            success, msg = create_account(new_email, new_password)
            if success:
                st.success(msg)
                st.session_state.auth_user = new_email
                st.rerun()
            else:
                st.error(msg)

    st.info("Forgot password?")
    with st.expander("Request Password Reset"):
        reset_email = st.text_input("Your Email for Reset")
        if st.button("Request Reset"):
            success, msg = reset_password_request(reset_email)
            if success:
                st.success(msg)
            else:
                st.error(msg)

    show_login_warning()
    st.stop()

lab_name = get_user_lab(user_email)
st.sidebar.success(f"Lab: {lab_name}")
st.sidebar.markdown(f"Logged in as: `{user_email}`")
if is_admin(user_email):
    st.sidebar.info("Admin privileges enabled")

if st.sidebar.button("Logout", key="logout_btn"):
    st.session_state.auth_user = None
    st.rerun()

st.write("Backend:", "Firestore" if USE_FIRESTORE else "CSV (development)")
if USE_FIRESTORE:
    st.success("Connected to Firestore")
else:
    st.warning("Using local CSV. Add Firebase credentials to enable Firestore.")

st.title("Requiva - Lab Order Management System")

tab_new, tab_table, tab_analytics, tab_ml_insights, tab_export = st.tabs([
    "New Order", 
    "Orders", 
    "Analytics", 
    "ML Insights",
    "Export"
])

with tab_new:
    st.subheader("Create a New Order")
    df = load_orders()
    df = filter_by_lab(df, user_email)
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    col1, col2, col3 = st.columns(3)
    with col1:
        item = st.text_input("ITEM *", placeholder="e.g., Fetal Bovine Serum (FBS) 500 mL", key="new_item")
        vendor = st.text_input("VENDOR *", placeholder="e.g., Thermo Fisher", key="new_vendor")
        cat_no = st.text_input("CAT #", placeholder="e.g., 12345-TF", key="new_cat")
        grant_used = st.text_input("GRANT USED", placeholder="e.g., R01CA12345 (comma separated)", key="new_grant")

    with col2:
        qty = st.number_input("NUMBER OF ITEM *", min_value=0.0, value=0.0, step=1.0, key="new_qty")
        unit_price = st.number_input("AMOUNT PER ITEM *", min_value=0.0, value=0.0, step=1.0, format="%.2f", key="new_price")
        po_source = st.selectbox("PO SOURCE", ["ShopBlue", "Stock Room", "External Vendor"], index=0, key="new_po_source")
        po_no = st.text_input("PO #", placeholder="e.g., PO-2025-00123", key="new_po_no")

    with col3:
        notes = st.text_area("NOTES", placeholder="Any notes (urgent, storage req., etc.)", key="new_notes")
        ordered_by = st.text_input("ORDERED BY", placeholder="Name / ID", key="new_ordered_by")
        date_ordered = st.date_input("DATE ORDERED", value=date.today(), key="new_date_ordered")
        received_flag = st.checkbox("Item received?", key="new_received_flag")
        date_received = st.date_input("DATE RECEIVED", value=date.today(), key="new_date_received") if received_flag else None
        received_by = st.text_input("RECEIVED BY", placeholder="Receiver name", key="new_received_by") if received_flag else ""
        location = st.text_input("ITEM LOCATION", placeholder="e.g., Freezer A, Shelf 2", key="new_location") if received_flag else ""

    with st.form("order_form", clear_on_submit=True):
        submitted = st.form_submit_button("Add Order", type="primary")
        
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
                st.success(f"Order {req_id} added successfully")
                
                anomaly_score = detect_anomalies(df, new_row)
                if anomaly_score > 0.7:
                    st.warning(f"Unusual order detected (score: {anomaly_score:.2f}). Please verify pricing and quantity.")

with tab_table:
    st.subheader("Orders Table")
    df = load_orders()
    df = filter_by_lab(df, user_email)
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = generate_alert_column(df)

    c1, c2, c3 = st.columns(3)
    with c1:
        vendor_filter = st.text_input("Filter by VENDOR", key="filter_vendor")
    with c2:
        grant_filter = st.text_input("Filter by GRANT USED", key="filter_grant")
    with c3:
        po_source_filter = st.selectbox("Filter by PO SOURCE", ["All", "ShopBlue", "Stock Room", "External Vendor"], key="filter_po")

    filtered = df.copy()
    if vendor_filter:
        filtered = filtered[filtered["VENDOR"].astype(str).str.contains(vendor_filter, case=False, na=False)]
    if grant_filter:
        filtered = filtered[filtered["GRANT USED"].astype(str).str.contains(grant_filter, case=False, na=False)]
    if po_source_filter != "All":
        filtered = filtered[filtered["PO SOURCE"] == po_source_filter]

    display_columns = [col for col in ["REQ#", "ITEM", "VENDOR", "DATE ORDERED", "RECEIVED BY", "ALERT"] if col in filtered.columns]
    st.dataframe(filtered[display_columns], use_container_width=True)

    overdue = filter_unreceived_orders(filtered)
    if not overdue.empty:
        st.warning(f"{len(overdue)} items pending receipt")
    else:
        st.success("All recent items have been marked as received")

with tab_analytics:
    st.subheader("Top Items by Frequency")
    df = load_orders()
    df = filter_by_lab(df, user_email)
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    if not df.empty and "ITEM" in df.columns:
        counts = df["ITEM"].value_counts().head(10)
        fig, ax = plt.subplots(figsize=(8, 4))
        counts.plot(kind="bar", ax=ax)
        ax.set_xlabel("Item")
        ax.set_ylabel("Orders (count)")
        ax.set_title("Top 10 Ordered Items")
        st.pyplot(fig)
    else:
        st.info("No data available. Add orders to see analytics.")

with tab_ml_insights:
    st.subheader("Machine Learning Insights")
    df = load_orders()
    df = filter_by_lab(df, user_email)
    
    if df.empty or len(df) < 10:
        st.info("Need at least 10 orders for predictions. Keep adding orders.")
    else:
        ml_tab1, ml_tab2, ml_tab3, ml_tab4 = st.tabs([
            "Reorder Predictions",
            "Spending Forecast", 
            "Anomaly Detection",
            "Recommendations"
        ])
        
        with ml_tab1:
            st.markdown("### Predictive Reordering")
            st.write("Items that may need reordering based on usage patterns:")
            
            reorder_predictions = predict_reorder_date(df)
            if not reorder_predictions.empty:
                st.dataframe(reorder_predictions, use_container_width=True)
            else:
                st.info("No reorder predictions available. Need more historical data.")
        
        with ml_tab2:
            st.markdown("### Spending Forecast")
            
            forecast_months = st.slider("Forecast period (months)", 1, 12, 3, key="forecast_slider")
            spending_forecast = forecast_spending(df, months=forecast_months)
            
            if spending_forecast:
                st.metric("Predicted Spending", f"${spending_forecast['total_forecast']:,.2f}")
                st.metric("Average Monthly", f"${spending_forecast['monthly_avg']:,.2f}")
                
                fig, ax = plt.subplots(figsize=(10, 4))
                ax.plot(spending_forecast['dates'], spending_forecast['amounts'], marker='o')
                ax.set_xlabel("Month")
                ax.set_ylabel("Predicted Spending ($)")
                ax.set_title("Spending Forecast")
                ax.grid(True, alpha=0.3)
                st.pyplot(fig)
                
                if 'by_grant' in spending_forecast:
                    st.markdown("#### By Grant")
                    grant_df = pd.DataFrame(spending_forecast['by_grant'].items(), columns=['Grant', 'Amount'])
                    st.dataframe(grant_df, use_container_width=True)
        
        with ml_tab3:
            st.markdown("### Anomaly Detection")
            st.write("Unusual orders flagged by machine learning:")
            
            anomalies = detect_anomalies(df)
            if not anomalies.empty:
                st.warning(f"Found {len(anomalies)} potential anomalies")
                st.dataframe(anomalies[['REQ#', 'ITEM', 'VENDOR', 'TOTAL', 'ANOMALY_SCORE']], use_container_width=True)
            else:
                st.success("No anomalies detected. All orders appear normal.")
        
        with ml_tab4:
            st.markdown("### Recommendations")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### Recommended Vendors")
                vendor_recs = recommend_vendors(df)
                if vendor_recs:
                    for item, vendors in list(vendor_recs.items())[:5]:
                        st.write(f"**{item}**")
                        st.write(f"Suggested: {', '.join(vendors)}")
                else:
                    st.info("Need more order history for vendor recommendations")
            
            with col2:
                st.markdown("#### Bulk Order Opportunities")
                bulk_opps = get_bulk_opportunities(df)
                if bulk_opps:
                    for item, data in list(bulk_opps.items())[:5]:
                        st.write(f"**{item}**")
                        st.write(f"Suggested quantity: {data['suggested_qty']} units (potential savings: ${data['potential_savings']:.2f})")
                else:
                    st.info("No bulk opportunities identified")

with tab_export:
    st.subheader("Download Orders")
    df = load_orders()
    df = filter_by_lab(df, user_email)
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[[col for col in REQUIRED_COLUMNS if col in df.columns]]

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download CSV",
        data=csv_bytes,
        file_name=f"Requiva_Orders_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Orders", index=False)
    st.download_button(
        label="Download Excel",
        data=output.getvalue(),
        file_name=f"Requiva_Orders_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

st.markdown("---")
st.caption("Requiva - Lab Order Management System with Predictive Analytics")
st.caption("Powered by Tobilola Ogunbowale")
