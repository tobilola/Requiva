"""Requiva Supply Hub: Firestore-backed requests, purchasing, receipts and audit trail.
No email alerts; no writes to the legacy 'orders' collection.
"""
import re
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from firebase_admin import firestore, storage
from utils import db, USE_FIRESTORE, get_user_lab, is_admin

REQUESTS = 'supply_requests'
NOTIFICATIONS = 'supply_notifications'
RECEIVERS = 'supply_receivers'
EVENTS = 'supply_events'
EASTERN = ZoneInfo('America/New_York')
SOURCES = ['ShopBlue', 'UB Biochemistry Stockroom']
OPEN_STATUSES = {'Requested', 'Approved', 'Ordered', 'Partially Received'}
PRIORITIES = ['Normal', 'Urgent', 'Critical']


def now():
    return datetime.now(timezone.utc)


def display_time(value):
    if value is None:
        return '—'
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return value
    if not isinstance(value, datetime):
        return str(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(EASTERN).strftime('%b %d, %Y %I:%M %p %Z')


def normalized(value):
    return re.sub(r'[^a-z0-9]+', ' ', str(value or '').lower()).strip()


def item_key(item, catalog, company):
    if catalog.strip():
        return 'catalog:' + normalized(company) + ':' + normalized(catalog)
    return 'item:' + normalized(item)


def lab_for(email):
    return get_user_lab(email.strip().lower())


def require_db():
    if not USE_FIRESTORE or db is None:
        st.error('Supply Hub requires Firestore. No request was saved.')
        return False
    return True


def get_requests(email):
    email = email.strip().lower()
    collection = db.collection(REQUESTS)
    docs = (collection.stream() if is_admin(email)
            else collection.where('lab', '==', lab_for(email)).stream())
    rows = [dict(doc.to_dict() or {}, id=doc.id) for doc in docs]
    return sorted(rows, key=lambda r: str(r.get('created_at', '')), reverse=True)


def notify(recipient, lab, message, request_id):
    db.collection(NOTIFICATIONS).add({
        'recipient': recipient.lower(), 'lab': lab, 'message': message,
        'request_id': request_id, 'read': False,
        'created_at': firestore.SERVER_TIMESTAMP,
    })


def audit(request_id, actor, event, details=None):
    db.collection(EVENTS).add({
        'request_id': request_id, 'actor': actor.lower(),
        'event': event, 'details': details or {},
        'at': firestore.SERVER_TIMESTAMP,
    })


def create_request(email, item, qty, priority, source, catalog, company, grant, notes,
                   duplicate_reason=''):
    email = email.strip().lower()
    if not item.strip() or int(qty) < 1 or priority not in PRIORITIES or source not in SOURCES:
        raise ValueError('Enter a valid item, quantity, priority and purchasing source.')
    lab = lab_for(email)
    key = item_key(item, catalog, company)
    duplicates = [r for r in get_requests(email) if r.get('lab') == lab
                  and r.get('item_key') == key and r.get('status') in OPEN_STATUSES]
    if duplicates and not duplicate_reason.strip():
        raise ValueError('A matching request is already open. Enter a reason to request more.')
    request_id = 'SR-' + uuid.uuid4().hex[:12].upper()
    data = {
        'item': item.strip(), 'item_key': key, 'quantity': int(qty),
        'priority': priority, 'source': source, 'catalog': catalog.strip(),
        'company': company.strip(), 'grant': grant.strip(), 'notes': notes.strip(),
        'duplicate_reason': duplicate_reason.strip(), 'lab': lab,
        'requested_by': email, 'created_at': firestore.SERVER_TIMESTAMP,
        'updated_at': firestore.SERVER_TIMESTAMP, 'status': 'Requested',
        'ordered_by': '', 'ordered_at': None, 'po_number': '',
        'ordered_quantity': 0, 'received_quantity': 0,
        'last_received_by': '', 'last_received_at': None,
        'requisition_path': '', 'requisition_name': '',
    }
    db.collection(REQUESTS).document(request_id).create(data)
    audit(request_id, email, 'Requested', {'quantity': int(qty), 'priority': priority})
    notify(email, lab, f'Request {request_id} submitted: {item}', request_id)
    # Admin sees all requests directly on the Supply Hub, even if notification fails.
    return request_id


def can_receive(email, lab):
    email = email.strip().lower()
    if is_admin(email):
        return True
    if lab_for(email) != lab:
        return False
    doc = db.collection(RECEIVERS).document(email).get()
    return bool(doc.exists and doc.to_dict().get('enabled')
                and doc.to_dict().get('lab') == lab)


def set_receiver(admin_email, email, lab, enabled):
    if not is_admin(admin_email.strip().lower()):
        raise PermissionError('Admin only.')
    email = email.strip().lower()
    if not email or '@' not in email or is_admin(email):
        raise ValueError('Enter a valid non-admin user email.')
    user = db.collection('users').document(email).get()
    if not user.exists or lab_for(email) != lab:
        raise ValueError('This account does not belong to the selected laboratory.')
    db.collection(RECEIVERS).document(email).set({
        'enabled': bool(enabled), 'lab': lab,
        'updated_by': admin_email.lower(), 'updated_at': firestore.SERVER_TIMESTAMP,
    })


def approve_request(admin_email, request_id, approve):
    if not is_admin(admin_email.lower()):
        raise PermissionError('Admin only.')
    ref = db.collection(REQUESTS).document(request_id)
    snap = ref.get()
    if not snap.exists or snap.to_dict().get('status') != 'Requested':
        raise ValueError('Only new requests can be approved or rejected.')
    new_status = 'Approved' if approve else 'Rejected'
    ref.update({'status': new_status, 'approved_by': admin_email.lower(),
                'approved_at': firestore.SERVER_TIMESTAMP,
                'updated_at': firestore.SERVER_TIMESTAMP})
    data = snap.to_dict()
    audit(request_id, admin_email, new_status)
    notify(data['requested_by'], data['lab'], f'{request_id} is {new_status}', request_id)


def upload_requisition(file, request_id):
    """Private Cloud Storage object; Firebase Admin storageBucket must be configured."""
    if file is None:
        raise ValueError('Attach a requisition document.')
    allowed = {'application/pdf', 'image/png', 'image/jpeg'}
    if file.type not in allowed:
        raise ValueError('Only PDF, PNG and JPEG requisitions are supported.')
    data = file.getvalue()
    if not data or len(data) > 10 * 1024 * 1024:
        raise ValueError('File must be between 1 byte and 10 MB.')
    bucket = storage.bucket(name=__import__("os").environ.get("FIREBASE_STORAGE_BUCKET") or None)
    extension = {'application/pdf': '.pdf', 'image/png': '.png',
                 'image/jpeg': '.jpg'}[file.type]
    path = f'requiva_requisitions/{request_id}/{uuid.uuid4().hex}{extension}'
    blob = bucket.blob(path)
    blob.upload_from_string(data, content_type=file.type)
    return path, file.name


def mark_ordered(admin_email, request_id, po, quantity, file):
    if not is_admin(admin_email.lower()):
        raise PermissionError('Admin only.')
    ref = db.collection(REQUESTS).document(request_id)
    snap = ref.get()
    if not snap.exists:
        raise ValueError('Request not found.')
    row = snap.to_dict()
    if row['status'] != 'Approved':
        raise ValueError('Approve the request before marking it ordered.')
    if not po.strip() or int(quantity) < 1 or int(quantity) > int(row['quantity']):
        raise ValueError('Enter a PO/requisition number and valid ordered quantity.')
    if file is None:
        raise ValueError('Attach the ShopBlue or Stockroom requisition.')
    path, name = upload_requisition(file, request_id)
    # Recheck state after uploading. Only one order confirmation is accepted.
    if ref.get().to_dict().get('status') != 'Approved':
        storage.bucket(name=__import__("os").environ.get("FIREBASE_STORAGE_BUCKET") or None).blob(path).delete()
        raise ValueError('Request status changed. Refresh and try again.')
    ref.update({
        'status': 'Ordered', 'po_number': po.strip(),
        'ordered_quantity': int(quantity), 'ordered_by': admin_email.lower(),
        'ordered_at': firestore.SERVER_TIMESTAMP,
        'requisition_path': path, 'requisition_name': name,
        'uploaded_by': admin_email.lower(), 'uploaded_at': firestore.SERVER_TIMESTAMP,
        'updated_at': firestore.SERVER_TIMESTAMP,
    })
    audit(request_id, admin_email, 'Ordered', {'po_number': po, 'quantity': int(quantity)})
    notify(row['requested_by'], row['lab'], f'{request_id} has been ordered', request_id)


@firestore.transactional
def _receive_transaction(transaction, ref, qty, actor):
    snap = ref.get(transaction=transaction)
    if not snap.exists:
        raise ValueError('Request not found.')
    row = snap.to_dict()
    if not can_receive(actor, row['lab']):
        raise PermissionError('You are not an authorized receiver for this lab.')
    if row['status'] not in ('Ordered', 'Partially Received'):
        raise ValueError('Only ordered supplies can be received.')
    received = int(row.get('received_quantity', 0)) + qty
    ordered = int(row.get('ordered_quantity', 0))
    if qty < 1 or received > ordered:
        raise ValueError('Received quantity exceeds the outstanding quantity.')
    status = 'Received' if received == ordered else 'Partially Received'
    transaction.update(ref, {
        'received_quantity': received, 'status': status,
        'last_received_by': actor, 'last_received_at': firestore.SERVER_TIMESTAMP,
        'updated_at': firestore.SERVER_TIMESTAMP,
    })
    return row, status


def receive(email, request_id, qty, location):
    email = email.strip().lower()
    ref = db.collection(REQUESTS).document(request_id)
    transaction = db.transaction()
    row, status = _receive_transaction(transaction, ref, int(qty), email)
    audit(request_id, email, 'Received quantity', {'quantity': int(qty),
                                                   'location': location, 'status': status})
    notify(row['requested_by'], row['lab'], f'{request_id}: {status}', request_id)
    return status


def show_notifications(email):
    docs = db.collection(NOTIFICATIONS).where('recipient', '==', email.lower()).stream()
    unread = [(d.id, d.to_dict()) for d in docs if not d.to_dict().get('read')]
    st.subheader(f'Your notifications ({len(unread)})')
    for doc_id, note in unread[:30]:
        st.write(note.get('message', 'Notification'))
        if st.button('Mark read', key='note_' + doc_id):
            db.collection(NOTIFICATIONS).document(doc_id).update({'read': True})
            st.rerun()
    if not unread:
        st.caption('No unread notifications.')


def show_hub(email):
    email = email.strip().lower()
    st.markdown('### Your lab supply workspace')
    st.caption('Shared requests · ShopBlue / Stockroom · Deliveries · Notifications')
    with st.expander('📖 How Requiva Works — Quick Handbook', expanded=st.session_state.get('rq_expand_handbook', False)):
        from pathlib import Path
        handbook_guide = Path(__file__).with_name('handbook_scientist.png')
        if handbook_guide.is_file():
            st.image(str(handbook_guide), width=140, caption='Your friendly lab guide')
        st.markdown("""
        ### For every lab member
        **1. Check the Shared request board first.** Search the visible requests before asking for an item again. Each lab sees its own requests; the administrator can see all labs.

        **2. Request supplies.** Open **Request supplies**, then enter the **item, quantity, priority, and order place** (ShopBlue or UB Biochemistry Stockroom). Add catalog number, company, grant, and notes where available. If Requiva warns of a duplicate, review it; give a reason if another request is truly needed.

        **3. Follow the status.** **Requested** means submitted; **Approved** means approved but not yet purchased; **Ordered** means a purchase was confirmed; **Partially Received** means some of the ordered quantity arrived; **Received** means the full ordered quantity arrived. Rejected requests are not purchased.

        ### For administrators
        **4. Approve or reject.** Use **Manage requests** to review a request. Place the actual purchase manually through ShopBlue or the Stockroom.

        **5. Confirm the order.** Select the approved request, enter its PO/requisition number and quantity, attach the requisition PDF or image, and click **Confirm ordered**. Requiva automatically records the ordering account and timestamp. Uploading alone does not place an order.

        **6. Authorize receivers.** Open **Admin: designated receiving permissions**. Enter an existing lab member's email and exact lab name to grant or revoke receiving permission.

        ### For designated receivers and administrators
        **7. Record deliveries.** Under **Manage requests**, select an ordered request, enter the quantity received and storage location, and click **Confirm receipt**. Requiva records who received it and when. Partial deliveries remain **Partially Received** until all ordered units arrive.

        ### Weekly and monthly reports
        **8. Review Order frequency.** Use the weekly or monthly view to see how often items were **actually ordered**. Request submissions and delivery updates do not count as extra purchases. The current Supply Hub report covers orders recorded through the Supply Hub, not historical orders imported elsewhere.

        **Notifications:** In-app alerts are under **Dashboard notifications**. Email alerts are intentionally postponed.

        **Help:** If a button is missing, your account may not have permission. Contact the Requiva administrator. If requisition uploads fail, ask the administrator to check Firebase Storage configuration.
        """)
    if not require_db():
        return
    try:
        rows = get_requests(email)
    except Exception as exc:
        st.error(f'Unable to load supply requests: {exc}')
        return
    visible_labs = sorted(set(r['lab'] for r in rows))
    if is_admin(email) and visible_labs:
        chosen_lab = st.selectbox('View laboratory', ['All laboratories'] + visible_labs)
        shown = rows if chosen_lab == 'All laboratories' else [r for r in rows if r['lab'] == chosen_lab]
    else:
        shown = rows
    st.subheader('Shared request board')
    if shown:
        display = []
        for r in shown:
            display.append({
                'Request ID': r['id'], 'Item': r.get('item'), 'Qty': r.get('quantity'),
                'Priority': r.get('priority'), 'Source': r.get('source'),
                'Catalog #': r.get('catalog'), 'Company': r.get('company'),
                'Grant': r.get('grant'), 'Lab': r.get('lab'),
                'Status': r.get('status'), 'Ordered qty': r.get('ordered_quantity', 0),
                'Received qty': r.get('received_quantity', 0),
                'Requested by': r.get('requested_by'),
                'Requested at (ET)': display_time(r.get('created_at')),
                'Ordered by': r.get('ordered_by'),
                'Ordered at (ET)': display_time(r.get('ordered_at')),
                'Received by': r.get('last_received_by'),
                'Received at (ET)': display_time(r.get('last_received_at')),
                'PO #': r.get('po_number'),
            })
        st.dataframe(pd.DataFrame(display), use_container_width=True, hide_index=True)
    else:
        st.info('No requests yet. Submit the first request below.')
    with st.expander('➕ Request supplies', expanded=st.session_state.get('rq_expand_request', False) or not bool(shown)):
        with st.form('new_supply_request'):
            item = st.text_input('Item name *')
            qcol, pcol = st.columns(2)
            qty = qcol.number_input('Quantity *', min_value=1, value=1, step=1)
            priority = pcol.selectbox('Priority *', PRIORITIES)
            source = st.selectbox('Order place *', SOURCES)
            catalog = st.text_input('Catalog number')
            company = st.text_input('Company / Vendor')
            grant = st.text_input('Grant')
            notes = st.text_area('Notes')
            key = item_key(item, catalog, company)
            matches = [r for r in rows if r['lab'] == lab_for(email)
                       and r.get('item_key') == key and r['status'] in OPEN_STATUSES]
            if matches and item.strip():
                st.warning('Already requested: ' + ', '.join(
                    f"{r['id']} ({r['status']}, qty {r['quantity']})" for r in matches[:5]))
            duplicate_reason = st.text_input('Reason for additional request (required if duplicate)')
            submit = st.form_submit_button('Submit request', type='primary')
        if submit:
            try:
                rid = create_request(email, item, qty, priority, source, catalog,
                                     company, grant, notes, duplicate_reason)
                st.success(f'Saved {rid}')
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    st.subheader('Order frequency — weekly and monthly')
    st.caption('Counts confirmed purchases by their actual order date (Eastern Time), not requests or deliveries.')
    period = st.radio('View orders by', ['This week', 'This month', 'All time'],
                      horizontal=True, key='supply_order_period')
    # Store and compare calendar dates in the lab's Eastern Time zone.
    current_date = datetime.now(EASTERN).date()
    week_start = current_date - pd.Timedelta(days=current_date.weekday())
    month_start = current_date.replace(day=1)
    ordered_rows = []
    for r in shown:
        ordered_at = r.get('ordered_at')
        if not isinstance(ordered_at, datetime):
            continue
        if ordered_at.tzinfo is None:
            ordered_at = ordered_at.replace(tzinfo=timezone.utc)
        ordered_date = ordered_at.astimezone(EASTERN).date()
        if period == 'This week' and ordered_date < week_start:
            continue
        if period == 'This month' and ordered_date < month_start:
            continue
        if ordered_date > current_date:
            continue
        ordered_rows.append((r, ordered_date))
    if ordered_rows:
        st.metric('Confirmed orders in selected period', len(ordered_rows))
        frequency = pd.DataFrame([{
            'Item': r.get('item', ''),
            'Catalog #': r.get('catalog', ''),
            'Times ordered': 1,
            'Total quantity': int(r.get('ordered_quantity', 0)),
        } for r, _ in ordered_rows])
        frequency = frequency.groupby(['Item', 'Catalog #'], as_index=False).sum()
        st.dataframe(frequency.sort_values('Times ordered', ascending=False),
                     use_container_width=True, hide_index=True)
    else:
        st.info('No confirmed orders in this period.')
    if period == 'All time':
        st.caption('Select This week or This month to see recent purchasing activity.')
    st.divider()
    st.subheader('Manage requests')
    actionable = [r for r in rows if is_admin(email) or can_receive(email, r['lab'])]
    if actionable:
        selected_id = st.selectbox('Select request', [r['id'] for r in actionable],
                                   format_func=lambda rid: next(
                                       f"{r['id']} · {r['item']} · {r['status']}"
                                       for r in actionable if r['id'] == rid))
        selected = next(r for r in actionable if r['id'] == selected_id)
        st.write('**Status:**', selected['status'])
        st.write('**Order date:**', display_time(selected.get('ordered_at')))
        st.write('**Ordered by:**', selected.get('ordered_by') or '—')
        if is_admin(email) and selected['status'] == 'Requested':
            left, right = st.columns(2)
            if left.button('Approve', key='approve_' + selected_id):
                try:
                    approve_request(email, selected_id, True)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            if right.button('Reject', key='reject_' + selected_id):
                try:
                    approve_request(email, selected_id, False)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        if is_admin(email) and selected['status'] == 'Approved':
            with st.form('mark_ordered'):
                st.caption('Confirm the purchase was placed manually in ShopBlue or Stockroom.')
                po = st.text_input('PO / requisition number *')
                quantity = st.number_input('Quantity ordered *', min_value=1,
                                           max_value=int(selected['quantity']),
                                           value=int(selected['quantity']))
                document = st.file_uploader('Requisition PDF, PNG or JPG *',
                                            type=['pdf', 'png', 'jpg', 'jpeg'])
                if st.form_submit_button('Confirm ordered'):
                    try:
                        mark_ordered(email, selected_id, po, quantity, document)
                        st.success('Order recorded with automatic date/time and purchaser.')
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
        if selected['status'] in ('Ordered', 'Partially Received') and can_receive(email, selected['lab']):
            remaining = int(selected.get('ordered_quantity', 0)) - int(selected.get('received_quantity', 0))
            if remaining > 0:
                with st.form('receive_supply'):
                    received_qty = st.number_input('Quantity received', min_value=1,
                                                   max_value=remaining, value=remaining)
                    location = st.text_input('Storage location')
                    if st.form_submit_button('Confirm receipt'):
                        try:
                            status = receive(email, selected_id, received_qty, location)
                            st.success(f'Updated: {status}')
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))
        path = selected.get('requisition_path')
        if path and (is_admin(email) or selected['lab'] == lab_for(email)):
            if st.button('View requisition (10-minute private link)'):
                try:
                    from datetime import timedelta
                    url = storage.bucket(name=__import__("os").environ.get("FIREBASE_STORAGE_BUCKET") or None).blob(path).generate_signed_url(
                        version='v4', expiration=timedelta(minutes=10), method='GET')
                    st.link_button('Open requisition', url)
                except Exception as exc:
                    st.error(f'Cannot create secure document link: {exc}')
    else:
        st.caption('You can view and submit requests. Only authorized staff manage purchasing or receiving.')
    if is_admin(email):
        with st.expander('Admin: designated receiving permissions'):
            receiver_email = st.text_input('Existing lab member email').strip().lower()
            receiver_lab = st.text_input('Laboratory name (exactly as assigned to the user)')
            enabled = st.checkbox('Authorized to receive supplies', value=True)
            if st.button('Save receiving permission'):
                try:
                    set_receiver(email, receiver_email, receiver_lab, enabled)
                    st.success('Receiving permission saved.')
                except Exception as exc:
                    st.error(str(exc))
    with st.expander('🔔 Dashboard notifications'):
        show_notifications(email)
