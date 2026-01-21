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
    page_icon="R", 
    layout="wide"
)

# Initialize session state
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None
if "show_create_account" not in st.session_state:
    st.session_state.show_create_account = False
if "show_reset_password" not in st.session_state:
    st.session_state.show_reset_password = False
if "imported_pos" not in st.session_state:
    st.session_state.imported_pos = None

# Sidebar System Status
with st.sidebar:
    st.markdown("---")
    with st.expander("System Status"):
        st.write(f"**Backend:** {'Firestore' if USE_FIRESTORE else 'CSV (Dev Mode)'}")
        
        firebase_json_exists = bool(os.getenv("FIREBASE_JSON"))
        old_var_exists = bool(os.getenv("firebase-service-account.json"))
        
        st.write(f"**FIREBASE_JSON:** {'Set' if firebase_json_exists else 'Not Set'}")
        
        if old_var_exists:
            st.warning("Old variable 'firebase-service-account.json' detected. Rename to 'FIREBASE_JSON'")
        
        if USE_FIRESTORE:
            st.success("Firestore Connected")
        else:
            st.error("Firestore Not Connected")
            st.caption("Add FIREBASE_JSON env variable to enable Firestore")

# Authentication Check
user_email = check_auth_status()

if not user_email:
    st.title("Requiva")
    st.markdown("##### Lab Order Management System")
    st.markdown("---")
    
    login_form()
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**New User?**")
        with st.expander("Create Account", expanded=False):
            new_email = st.text_input("Email", key="new_account_email", placeholder="your.email@buffalo.edu")
            new_password = st.text_input("Password", type="password", key="new_account_password", placeholder="Min 6 characters")
            
            if st.button("Create Account", type="primary", key="create_account_btn"):
                if not new_email or not new_password:
                    st.error("Email and password are required")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    success, msg = create_account(new_email, new_password)
                    if success:
                        st.success(msg)
                        st.info("Please login with your new credentials above")
                    else:
                        st.error(msg)
    
    with col2:
        st.markdown("**Forgot Password?**")
        with st.expander("Request Password Reset", expanded=False):
            reset_email = st.text_input("Your Email", key="reset_email", placeholder="your.email@buffalo.edu")
            
            if st.button("Request Reset", type="secondary", key="reset_password_btn"):
                if not reset_email:
                    st.error("Email is required")
                else:
                    success, msg = reset_password_request(reset_email)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
    
    st.markdown("---")
    st.markdown("**Getting Started**")
    st.markdown("""
    - Create an account with your @buffalo.edu email
    - Access your lab's orders and track inventory
    - View analytics and spending reports
    - Export data for reporting
    """)
    
    show_login_warning()
    st.stop()

# User is logged in - Show Main App
lab_name = get_user_lab(user_email)

# Sidebar User Info
st.sidebar.title("User")
st.sidebar.write(f"**Lab:** {lab_name}")
st.sidebar.write(f"**Email:** {user_email}")

if is_admin(user_email):
    st.sidebar.warning("Admin Access")
    st.sidebar.caption("You can see all labs")

if st.sidebar.button("Logout", key="logout_btn", type="primary"):
    st.session_state.auth_user = None
    st.success("Logged out successfully")
    st.rerun()

# Main App Title
st.title("Requiva")
st.caption("Lab Order Management System | Adelaiye-Ogala Lab")

# Backend Status
if USE_FIRESTORE:
    st.caption("Connected to Firestore")
else:
    st.warning("Using local CSV - Development Mode")

# Main Tabs
tab_new, tab_import, tab_table, tab_analytics, tab_ml_insights, tab_export = st.tabs([
    "New Order", 
    "Import Data",
    "Orders Table", 
    "Analytics", 
    "ML Insights",
    "Export"
])

# TAB 1: New Order
with tab_new:
    st.subheader("Create New Order")
    
    df = load_orders()
    df = filter_by_lab(df, user_email)
    
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Item Details**")
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
        st.markdown("**Pricing & Purchase**")
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
            placeholder="e.g., 1481052", 
            key="new_po_no",
            help="Purchase order number"
        )

    with col3:
        st.markdown("**Additional Info**")
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
        
        st.markdown("**Receipt Information (Optional)**")
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
    
    col_submit, col_clear = st.columns([1, 4])
    
    with col_submit:
        if st.button("Add Order", type="primary", key="submit_order", use_container_width=True):
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
                
                st.success(f"Order {req_id} added successfully. Total: ${total:,.2f}")
                st.info("Refresh the Orders Table tab to see your new order")

# TAB 2: Import Data
with tab_import:
    st.subheader("Import Orders")
    
    import_type = st.radio(
        "Select import source:",
        ["ShopBlue Export", "Accounts & Expenses / Inventory File"],
        horizontal=True
    )
    
    st.markdown("---")
    
    if import_type == "ShopBlue Export":
        st.markdown("""
        **How to export from ShopBlue:**
        1. Log into ShopBlue
        2. Click user icon (top right) → Manage Searches
        3. Navigate to Shared → UB - ShopBlue Support
        4. Click Export on "Purchase Orders Completed"
        5. Download the Excel file and upload below
        """)
        
        uploaded_file = st.file_uploader(
            "Upload ShopBlue Export (.xlsx)", 
            type=["xlsx"],
            key="shopblue_upload"
        )
        
        if uploaded_file is not None:
            try:
                df_import = pd.read_excel(uploaded_file, header=9)
                
                expected_cols = ['PO Number', 'Supplier', 'Created Date/Time', 'Total Amount']
                if not all(col in df_import.columns for col in expected_cols):
                    st.error("This doesn't appear to be a valid ShopBlue export. Please check the file.")
                else:
                    st.success(f"Found {len(df_import)} purchase orders")
                    
                    preview_cols = ['PO Number', 'Requisition Number', 'Supplier', 'Total Amount']
                    preview_cols = [c for c in preview_cols if c in df_import.columns]
                    st.dataframe(df_import[preview_cols].head(10), use_container_width=True)
                    
                    if len(df_import) > 10:
                        st.caption(f"Showing 10 of {len(df_import)} records")
                    
                    # Load existing orders to check for duplicates
                    df_orders = load_orders()
                    existing_pos = set(df_orders['PO #'].astype(str).values) if 'PO #' in df_orders.columns else set()
                    existing_reqs = set(df_orders['REQ#'].astype(str).str.replace('REQ-', '').values) if 'REQ#' in df_orders.columns else set()
                    
                    # Also check Requisition Numbers from ShopBlue
                    if 'Requisition Number' in df_import.columns:
                        shopblue_req_nums = df_import['Requisition Number'].astype(str).tolist()
                        already_imported = [r for r in shopblue_req_nums if r in existing_reqs]
                        if already_imported:
                            st.warning(f"Found {len(already_imported)} orders that may already exist (by Requisition Number)")
                    
                    st.markdown("---")
                    
                    po_numbers = df_import['PO Number'].astype(str).tolist()
                    selected_pos = st.multiselect(
                        "Select POs to import (leave empty for all)",
                        options=po_numbers,
                        default=[],
                        key="select_pos"
                    )
                    
                    if not selected_pos:
                        selected_pos = po_numbers
                    
                    st.write(f"Will import: {len(selected_pos)} purchase orders")
                    
                    if st.button("Import Selected POs", type="primary"):
                        df_orders = load_orders()
                        
                        # Build sets for duplicate checking
                        existing_pos = set(df_orders['PO #'].astype(str).values) if not df_orders.empty and 'PO #' in df_orders.columns else set()
                        existing_reqs = set()
                        if not df_orders.empty and 'REQ#' in df_orders.columns:
                            # Extract numeric part of REQ# for comparison
                            for req in df_orders['REQ#'].astype(str).values:
                                existing_reqs.add(req)
                        
                        # Also track Requisition Numbers stored in NOTES
                        if not df_orders.empty and 'NOTES' in df_orders.columns:
                            for note in df_orders['NOTES'].astype(str).values:
                                if 'Requisition:' in note:
                                    try:
                                        req_num = note.split('Requisition:')[1].split('.')[0].strip()
                                        existing_reqs.add(req_num)
                                    except:
                                        pass
                        
                        imported_count = 0
                        skipped_count = 0
                        skipped_details = []
                        
                        for _, row in df_import.iterrows():
                            po_num = str(row.get('PO Number', ''))
                            req_num = str(row.get('Requisition Number', ''))
                            
                            if po_num not in selected_pos:
                                continue
                            
                            # Check duplicates by PO # OR Requisition Number
                            if po_num in existing_pos:
                                skipped_count += 1
                                skipped_details.append(f"PO {po_num} (duplicate PO#)")
                                continue
                            
                            if req_num in existing_reqs:
                                skipped_count += 1
                                skipped_details.append(f"PO {po_num} (Req# {req_num} exists)")
                                continue
                            
                            req_id = gen_req_id(df_orders)
                            
                            created_date = row.get('Created Date/Time', '')
                            if pd.notna(created_date):
                                try:
                                    if isinstance(created_date, str):
                                        created_date = created_date.split(' ')[0]
                                    else:
                                        created_date = created_date.strftime('%Y-%m-%d')
                                except:
                                    created_date = datetime.now().strftime('%Y-%m-%d')
                            else:
                                created_date = datetime.now().strftime('%Y-%m-%d')
                            
                            total_amount = row.get('Total Amount', 0)
                            if pd.isna(total_amount):
                                total_amount = 0
                            
                            new_row = {
                                "REQ#": req_id,
                                "ITEM": f"[Import - add item details]",
                                "NUMBER OF ITEM": 1,
                                "AMOUNT PER ITEM": float(total_amount),
                                "TOTAL": float(total_amount),
                                "VENDOR": str(row.get('Supplier', '')),
                                "CAT #": "",
                                "GRANT USED": "",
                                "PO SOURCE": "ShopBlue",
                                "PO #": po_num,
                                "NOTES": f"Requisition: {req_num}. Status: {row.get('PO Status', '')}",
                                "ORDERED BY": str(row.get('PO Owner', '')),
                                "DATE ORDERED": created_date,
                                "DATE RECEIVED": "",
                                "RECEIVED BY": "",
                                "ITEM LOCATION": "",
                                "LAB": lab_name,
                            }
                            
                            df_orders = pd.concat([df_orders, pd.DataFrame([new_row])], ignore_index=True)
                            existing_pos.add(po_num)
                            existing_reqs.add(req_num)
                            imported_count += 1
                        
                        if imported_count > 0:
                            save_orders(df_orders)
                            st.success(f"Imported {imported_count} purchase orders")
                        
                        if skipped_count > 0:
                            st.warning(f"Skipped {skipped_count} duplicates:")
                            for detail in skipped_details[:10]:
                                st.caption(f"  - {detail}")
                            if len(skipped_details) > 10:
                                st.caption(f"  ... and {len(skipped_details) - 10} more")
                        
                        if imported_count == 0 and skipped_count == 0:
                            st.info("No orders to import")
            
            except Exception as e:
                st.error(f"Error reading file: {str(e)}")
    
    else:  # Accounts & Expenses / Inventory File
        st.markdown("""
        **Upload your lab tracking spreadsheet** (Accounts & Expenses or Inventory file)
        
        Expected columns: Req#, Item, #, Amount, Total, Vendor (optional)
        """)
        
        uploaded_file = st.file_uploader(
            "Upload Excel file (.xlsx)", 
            type=["xlsx"],
            key="inventory_upload"
        )
        
        if uploaded_file is not None:
            try:
                xl = pd.ExcelFile(uploaded_file)
                
                if len(xl.sheet_names) > 1:
                    selected_sheet = st.selectbox("Select sheet to import:", xl.sheet_names)
                else:
                    selected_sheet = xl.sheet_names[0]
                
                df_import = pd.read_excel(xl, sheet_name=selected_sheet)
                
                # Clean column names
                df_import.columns = df_import.columns.str.strip()
                
                # Check for expected columns
                if 'Req#' not in df_import.columns and 'Item' not in df_import.columns:
                    st.error("Could not find expected columns (Req#, Item). Please check your file format.")
                else:
                    # Clean up data
                    df_import = df_import.dropna(subset=['Item'] if 'Item' in df_import.columns else df_import.columns[0:1])
                    df_import = df_import[df_import['Item'].astype(str).str.len() > 2]  # Remove empty/short rows
                    
                    st.success(f"Found {len(df_import)} items in sheet '{selected_sheet}'")
                    
                    st.dataframe(df_import.head(10), use_container_width=True)
                    
                    if len(df_import) > 10:
                        st.caption(f"Showing 10 of {len(df_import)} records")
                    
                    # Grant field for this import
                    grant_for_import = st.text_input(
                        "Grant/Fund for these orders (optional):",
                        value=selected_sheet if selected_sheet not in ['Sheet1', 'Sheet2'] else "",
                        help="This will be applied to all imported orders from this sheet"
                    )
                    
                    st.markdown("---")
                    
                    if st.button("Import Orders", type="primary", key="import_inventory"):
                        df_orders = load_orders()
                        
                        # Build set of existing Req#s for duplicate checking
                        existing_reqs = set()
                        if not df_orders.empty and 'REQ#' in df_orders.columns:
                            existing_reqs = set(df_orders['REQ#'].astype(str).values)
                        
                        # Also check NOTES for Requisition numbers
                        if not df_orders.empty and 'NOTES' in df_orders.columns:
                            for note in df_orders['NOTES'].astype(str).values:
                                if 'Requisition:' in note:
                                    try:
                                        req_num = note.split('Requisition:')[1].split('.')[0].strip()
                                        existing_reqs.add(req_num)
                                    except:
                                        pass
                        
                        # Check original Req# field too
                        if not df_orders.empty and 'NOTES' in df_orders.columns:
                            for note in df_orders['NOTES'].astype(str).values:
                                if 'Original Req#:' in note:
                                    try:
                                        orig_req = note.split('Original Req#:')[1].split('.')[0].strip()
                                        existing_reqs.add(orig_req)
                                    except:
                                        pass
                        
                        imported_count = 0
                        skipped_count = 0
                        
                        for _, row in df_import.iterrows():
                            # Get original Req# from source file
                            orig_req = str(row.get('Req#', '')).replace('\xa0', '').replace('?', '').strip()
                            
                            # Skip invalid entries
                            if orig_req in ['*', '', 'nan', 'None'] or len(orig_req) < 3:
                                orig_req = ""
                            
                            # Check for duplicates
                            if orig_req and orig_req in existing_reqs:
                                skipped_count += 1
                                continue
                            
                            item_name = str(row.get('Item', ''))
                            if not item_name or item_name == 'nan' or len(item_name) < 2:
                                continue
                            
                            req_id = gen_req_id(df_orders)
                            
                            # Parse quantity
                            qty_raw = row.get('#', 1)
                            try:
                                if isinstance(qty_raw, str):
                                    qty = float(''.join(filter(lambda x: x.isdigit() or x == '.', qty_raw))) or 1
                                else:
                                    qty = float(qty_raw) if pd.notna(qty_raw) else 1
                            except:
                                qty = 1
                            
                            # Parse amount
                            amount_raw = row.get('Amount', 0)
                            try:
                                amount = float(amount_raw) if pd.notna(amount_raw) else 0
                            except:
                                amount = 0
                            
                            # Parse total
                            total_raw = row.get('Total', 0)
                            try:
                                total = float(total_raw) if pd.notna(total_raw) else (qty * amount)
                            except:
                                total = qty * amount
                            
                            # Get vendor if available
                            vendor = str(row.get('Vendor', '')) if 'Vendor' in row else ''
                            if vendor == 'nan':
                                vendor = ''
                            
                            new_row = {
                                "REQ#": req_id,
                                "ITEM": item_name[:200],  # Truncate long names
                                "NUMBER OF ITEM": qty,
                                "AMOUNT PER ITEM": amount,
                                "TOTAL": total,
                                "VENDOR": vendor,
                                "CAT #": "",
                                "GRANT USED": grant_for_import,
                                "PO SOURCE": "ShopBlue",
                                "PO #": "",
                                "NOTES": f"Original Req#: {orig_req}. Imported from {selected_sheet}." if orig_req else f"Imported from {selected_sheet}.",
                                "ORDERED BY": "",
                                "DATE ORDERED": "",
                                "DATE RECEIVED": "",
                                "RECEIVED BY": "",
                                "ITEM LOCATION": "",
                                "LAB": lab_name,
                            }
                            
                            df_orders = pd.concat([df_orders, pd.DataFrame([new_row])], ignore_index=True)
                            if orig_req:
                                existing_reqs.add(orig_req)
                            imported_count += 1
                        
                        if imported_count > 0:
                            save_orders(df_orders)
                            st.success(f"Imported {imported_count} orders")
                        
                        if skipped_count > 0:
                            st.warning(f"Skipped {skipped_count} duplicates (Req# already exists)")
                        
                        if imported_count == 0 and skipped_count == 0:
                            st.info("No valid orders found to import")
            
            except Exception as e:
                st.error(f"Error reading file: {str(e)}")
                st.info("Make sure your file has columns: Req#, Item, #, Amount, Total")
    
    st.markdown("---")
    st.markdown("**Duplicate Detection:**")
    st.markdown("""
    The system checks for duplicates by:
    - PO Number (for ShopBlue imports)
    - Requisition Number (stored in notes)
    - Original Req# (for Accounts/Inventory imports)
    
    Orders that already exist will be skipped automatically.
    """)

# TAB 3: Orders Table
with tab_table:
    st.subheader("Orders Table")
    
    df = load_orders()
    df = filter_by_lab(df, user_email)
    
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    
    df = generate_alert_column(df)

    # Filters
    st.markdown("**Filters**")
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        vendor_filter = st.text_input("Filter by Vendor", key="filter_vendor", placeholder="Type vendor name...")
    with c2:
        grant_filter = st.text_input("Filter by Grant", key="filter_grant", placeholder="Type grant number...")
    with c3:
        po_source_filter = st.selectbox("PO Source", ["All", "ShopBlue", "Stock Room", "External Vendor"], key="filter_po")
    with c4:
        status_filter = st.selectbox("Status", ["All", "Pending", "Received"], key="filter_status")

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

    st.markdown(f"**Showing {len(filtered)} of {len(df)} orders**")
    
    if not filtered.empty:
        display_columns = [col for col in ["REQ#", "ITEM", "VENDOR", "TOTAL", "PO #", "DATE ORDERED", "ALERT"] if col in filtered.columns]
        st.dataframe(filtered[display_columns], use_container_width=True, height=400)
        
        # Pending items
        overdue = filter_unreceived_orders(filtered)
        if not overdue.empty:
            st.warning(f"{len(overdue)} items pending receipt")
            with st.expander("View Pending Items"):
                pending_display = [col for col in ["REQ#", "ITEM", "VENDOR", "PO #", "DATE ORDERED"] if col in overdue.columns]
                st.dataframe(overdue[pending_display], use_container_width=True)
        else:
            st.success("All items have been marked as received")
        
        # Edit Section
        st.markdown("---")
        st.markdown("**Edit Order**")
        st.caption("Select an order to update item details or mark as received")
        
        req_options = filtered["REQ#"].tolist()
        selected_req = st.selectbox("Select Order (REQ#)", [""] + req_options, key="edit_select")
        
        if selected_req:
            order_row = filtered[filtered["REQ#"] == selected_req].iloc[0]
            
            with st.form(key="edit_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    edit_item = st.text_input("ITEM", value=str(order_row.get("ITEM", "")), key="edit_item")
                    edit_cat = st.text_input("CAT #", value=str(order_row.get("CAT #", "")), key="edit_cat")
                    edit_grant = st.text_input("GRANT USED", value=str(order_row.get("GRANT USED", "")), key="edit_grant")
                    edit_qty = st.number_input("NUMBER OF ITEMS", value=float(order_row.get("NUMBER OF ITEM", 1)), min_value=0.0, key="edit_qty")
                    edit_unit = st.number_input("AMOUNT PER ITEM", value=float(order_row.get("AMOUNT PER ITEM", 0)), min_value=0.0, format="%.2f", key="edit_unit")
                
                with col2:
                    edit_notes = st.text_area("NOTES", value=str(order_row.get("NOTES", "")), key="edit_notes")
                    edit_location = st.text_input("ITEM LOCATION", value=str(order_row.get("ITEM LOCATION", "")), key="edit_location")
                    
                    st.markdown("**Receipt Information**")
                    current_received = order_row.get("DATE RECEIVED", "")
                    is_received = pd.notna(current_received) and current_received != ""
                    
                    mark_received = st.checkbox("Mark as Received", value=is_received, key="edit_received")
                    
                    if mark_received:
                        edit_date_received = st.date_input("Date Received", value=date.today(), key="edit_date_recv")
                        edit_received_by = st.text_input("Received By", value=str(order_row.get("RECEIVED BY", "")), key="edit_recv_by")
                    else:
                        edit_date_received = None
                        edit_received_by = ""
                
                submitted = st.form_submit_button("Save Changes", type="primary")
                
                if submitted:
                    # Update the order
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
                        
                        if mark_received and edit_date_received:
                            df_all.loc[idx, "DATE RECEIVED"] = edit_date_received.isoformat()
                            df_all.loc[idx, "RECEIVED BY"] = edit_received_by
                        elif not mark_received:
                            df_all.loc[idx, "DATE RECEIVED"] = ""
                            df_all.loc[idx, "RECEIVED BY"] = ""
                        
                        save_orders(df_all)
                        st.success(f"Order {selected_req} updated successfully")
                        st.rerun()
    else:
        st.info("No orders match your filters.")

# TAB 4: Analytics
with tab_analytics:
    st.subheader("Analytics Dashboard")
    
    df = load_orders()
    df = filter_by_lab(df, user_email)
    
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    if not df.empty and "ITEM" in df.columns:
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
        
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.markdown("**Top 10 Ordered Items**")
            counts = df["ITEM"].value_counts().head(10)
            fig, ax = plt.subplots(figsize=(8, 5))
            counts.plot(kind="barh", ax=ax, color="#1f77b4")
            ax.set_xlabel("Number of Orders")
            ax.set_ylabel("Item")
            ax.set_title("Most Frequently Ordered Items")
            plt.tight_layout()
            st.pyplot(fig)
        
        with col_chart2:
            st.markdown("**Top 5 Vendors by Orders**")
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
        st.info("No data available yet. Add orders to see analytics.")

# TAB 5: ML Insights
with tab_ml_insights:
    st.subheader("ML Insights")
    st.caption("Predictive analytics and anomaly detection")
    
    df = load_orders()
    df = filter_by_lab(df, user_email)
    
    if df.empty or len(df) < 10:
        st.info("Need at least 10 orders to generate ML predictions.")
        st.markdown("""
        **Available Features:**
        - Predictive reordering based on usage patterns
        - Spending forecasts for budget planning
        - Anomaly detection for unusual orders
        - Vendor recommendations based on history
        - Bulk order optimization opportunities
        """)
    else:
        ml_tab1, ml_tab2, ml_tab3, ml_tab4 = st.tabs([
            "Reorder Predictions",
            "Spending Forecast", 
            "Anomaly Detection",
            "Recommendations"
        ])
        
        with ml_tab1:
            st.markdown("**Predictive Reordering**")
            st.write("Items that may need reordering soon based on usage patterns:")
            
            try:
                reorder_predictions = predict_reorder_date(df)
                if not reorder_predictions.empty:
                    st.dataframe(reorder_predictions, use_container_width=True)
                else:
                    st.info("No reorder predictions available. Need more historical data.")
            except Exception as e:
                st.error(f"Error generating predictions: {e}")
        
        with ml_tab2:
            st.markdown("**Spending Forecast**")
            
            forecast_months = st.slider("Forecast period (months)", 1, 12, 3, key="forecast_slider")
            
            try:
                spending_forecast = forecast_spending(df, months=forecast_months)
                
                if spending_forecast:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Predicted Spending", f"${spending_forecast['total_forecast']:,.2f}")
                    with col2:
                        st.metric("Average Monthly", f"${spending_forecast['monthly_avg']:,.2f}")
                    
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
                        st.markdown("**Spending by Grant**")
                        grant_df = pd.DataFrame(spending_forecast['by_grant'].items(), columns=['Grant', 'Predicted Amount'])
                        grant_df['Predicted Amount'] = grant_df['Predicted Amount'].apply(lambda x: f"${x:,.2f}")
                        st.dataframe(grant_df, use_container_width=True)
                else:
                    st.info("Unable to generate forecast. Need more historical data.")
            except Exception as e:
                st.error(f"Error generating forecast: {e}")
        
        with ml_tab3:
            st.markdown("**Anomaly Detection**")
            st.write("Orders flagged as unusual:")
            
            try:
                anomalies = detect_anomalies(df)
                if not anomalies.empty:
                    st.warning(f"Found {len(anomalies)} potential anomalies")
                    display_cols = [col for col in ['REQ#', 'ITEM', 'VENDOR', 'TOTAL', 'ANOMALY_SCORE'] if col in anomalies.columns]
                    st.dataframe(anomalies[display_cols], use_container_width=True)
                    st.caption("Anomalies may indicate data entry errors, unusual bulk orders, or price changes")
                else:
                    st.success("No anomalies detected. All orders appear normal.")
            except Exception as e:
                st.error(f"Error detecting anomalies: {e}")
        
        with ml_tab4:
            st.markdown("**Recommendations**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Recommended Vendors**")
                try:
                    vendor_recs = recommend_vendors(df)
                    if vendor_recs:
                        for item, vendors in list(vendor_recs.items())[:5]:
                            st.markdown(f"**{item}**")
                            st.markdown(f"Suggested: {', '.join(vendors)}")
                            st.markdown("---")
                    else:
                        st.info("Need more order history for vendor recommendations")
                except Exception as e:
                    st.error(f"Error: {e}")
            
            with col2:
                st.markdown("**Bulk Order Opportunities**")
                try:
                    bulk_opps = get_bulk_opportunities(df)
                    if bulk_opps:
                        for item, data in list(bulk_opps.items())[:5]:
                            st.markdown(f"**{item}**")
                            st.markdown(f"Suggested: {data['suggested_qty']} units")
                            st.markdown(f"Potential savings: ${data['potential_savings']:.2f}")
                            st.markdown("---")
                    else:
                        st.info("No bulk opportunities identified yet")
                except Exception as e:
                    st.error(f"Error: {e}")

# TAB 6: Export
with tab_export:
    st.subheader("Export Data")
    st.write("Download your order data in CSV or Excel format.")
    
    df = load_orders()
    df = filter_by_lab(df, user_email)
    
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    
    df_export = df[[col for col in REQUIRED_COLUMNS if col in df.columns]]
    
    if not df_export.empty:
        st.metric("Total Orders", len(df_export))
        
        col1, col2 = st.columns(2)
        
        with col1:
            csv_bytes = df_export.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download CSV",
                data=csv_bytes,
                file_name=f"Requiva_Orders_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                type="primary",
                use_container_width=True
            )
            st.caption("CSV format - Compatible with Excel, Google Sheets")
        
        with col2:
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_export.to_excel(writer, sheet_name="Orders", index=False)
            
            st.download_button(
                label="Download Excel",
                data=output.getvalue(),
                file_name=f"Requiva_Orders_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="secondary",
                use_container_width=True
            )
            st.caption("Excel format - Formatted for reporting")
        
        with st.expander("Preview Export Data"):
            st.dataframe(df_export.head(10), use_container_width=True)
            st.caption(f"Showing first 10 of {len(df_export)} records")
    else:
        st.info("No orders to export yet.")

# Footer
st.markdown("---")
st.markdown("**Requiva** | Lab Order Management System")
st.caption("Adelaiye-Ogala Lab | University at Buffalo")
st.caption(f"Version 2.1 | {datetime.now().strftime('%B %Y')}")
