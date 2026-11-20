"""One-way, non-destructive Requiva Firestore -> PostgreSQL snapshot.

Run from Render Shell only after DATABASE_URL and FIREBASE_JSON are configured.
Requires: firebase-admin, psycopg2-binary.

Copies orders, users, supply_requests, supply_notifications, supply_receivers,
supply_events to requiva_migration_records. No Firestore writes or deletes.
This is a migration staging table, NOT a live backend switch.
"""
import os
import json
import sys
from datetime import datetime, date, timezone
from decimal import Decimal

COLLECTIONS = ('orders', 'users', 'supply_requests', 'supply_notifications',
               'supply_receivers', 'supply_events')


def encode(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        import base64
        return {'__base64__': base64.b64encode(value).decode('ascii')}
    if hasattr(value, 'path') and hasattr(value, 'id'):
        return {'__firestore_reference__': value.path}
    raise TypeError(f'Unsupported Firestore value: {type(value).__name__}')


def main():
    url = os.environ.get('DATABASE_URL')
    firebase_json = os.environ.get('FIREBASE_JSON')
    if not url or not firebase_json:
        sys.exit('Missing DATABASE_URL or FIREBASE_JSON; no changes made.')
    try:
        import psycopg2
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError as exc:
        sys.exit(f'Missing dependency: {exc}. Install psycopg2-binary and firebase-admin.')

    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(json.loads(firebase_json)))
    source = firestore.client()
    conn = psycopg2.connect(url, connect_timeout=15)
    try:
        with conn:
            with conn.cursor() as cursor:
                cursor.execute('''CREATE TABLE IF NOT EXISTS requiva_migration_records (
                    collection_name TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    document_data JSONB NOT NULL,
                    migrated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (collection_name, document_id)
                )''')
        for collection in COLLECTIONS:
            count = 0
            print(f'Copying {collection}...', flush=True)
            # Commit per collection; source records remain untouched.
            with conn:
                with conn.cursor() as cursor:
                    for doc in source.collection(collection).stream():
                        payload = json.dumps(doc.to_dict() or {}, default=encode, allow_nan=False)
                        cursor.execute('''INSERT INTO requiva_migration_records
                            (collection_name, document_id, document_data)
                            VALUES (%s, %s, %s::jsonb)
                            ON CONFLICT (collection_name, document_id)
                            DO UPDATE SET document_data = EXCLUDED.document_data,
                                          migrated_at = NOW()''',
                                       (collection, doc.id, payload))
                        count += 1
            with conn.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) FROM requiva_migration_records WHERE collection_name=%s',
                               (collection,))
                pg_count = cursor.fetchone()[0]
            print(f'{collection}: {count} source records copied; {pg_count} in PostgreSQL staging', flush=True)
            if pg_count < count:
                raise RuntimeError(f'Count mismatch in {collection}; stop and investigate.')
        print('Staging copy complete. Firebase is unchanged. Do NOT remove FIREBASE_JSON yet.')
        print('Requiva still uses Firebase until its application backend is separately switched.')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
