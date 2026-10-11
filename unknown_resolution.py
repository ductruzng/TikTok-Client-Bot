"""Owner decisions about uncertainty: immutable evidence, never a success or retry."""
import json
import re
import secrets
import sqlite3
import uuid
from contextlib import closing

import ledger
import rotation

ACTIONS = ('KEEP_BLOCKED', 'CLOSE_WITHOUT_RESEND', 'AUTHORIZE_REPLACEMENT')


def unresolved_sql(alias='r'):
    # Alias is internal, never caller/user SQL.
    if alias not in ('r', 'send_requests'):
        raise ValueError('Invalid internal SQL alias')
    return (f"({alias}.status='failed_unknown' AND NOT EXISTS(SELECT 1 FROM unknown_resolution_events ur "
            f"WHERE ur.request_id={alias}.request_id AND ur.action!='KEEP_BLOCKED'))")


def safe_note(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 2000:
        raise ValueError('A nonempty reason/evidence note of at most 2000 characters is required')
    if any(ord(c) < 32 for c in value) or re.search(r'(?i)(cookie|sessionid|access[_ -]?key|authorization|bearer|mstoken|token)\s*[:=]|https?://\S*\?', value):
        raise ValueError('Use a short observation/reference without credentials, URL queries or raw logs')
    return value


def _preview(conn, request_id):
    from ledger_requests import utc_now_ms, local_time
    row = conn.execute('SELECT * FROM send_requests WHERE request_id=?', (request_id,)).fetchone()
    if not row or row['status'] != 'failed_unknown':
        raise ledger.LedgerError('Review requires an UNKNOWN request')
    events = [dict(r) for r in conn.execute('SELECT * FROM unknown_resolution_events WHERE request_id=? ORDER BY event_id', (request_id,))]
    final = any(r['action'] != 'KEEP_BLOCKED' for r in events)
    outstanding = [r[0] for r in conn.execute(f'SELECT r.request_id FROM send_requests r WHERE r.canonical_uid=? AND r.conv_id=? AND {unresolved_sql()} ORDER BY r.request_id', (row['canonical_uid'], row['conv_id']))]
    breakers = [dict(r) for r in conn.execute("SELECT * FROM breaker_state WHERE scope_type='account' AND scope_key=? OR scope_type='session' AND canonical_uid=? ORDER BY scope_type,scope_key", (row['canonical_uid'], row['canonical_uid']))]
    state = conn.execute('SELECT * FROM rotation_state WHERE canonical_uid=? AND conv_id=? AND campaign_id=?', (row['canonical_uid'], row['conv_id'], row['campaign_id'])).fetchone()
    active = [r[0] for r in conn.execute("SELECT request_id FROM send_requests WHERE canonical_uid=? AND conv_id=? AND status IN ('queued','pending') ORDER BY request_id", (row['canonical_uid'], row['conv_id']))]
    route = conn.execute('SELECT * FROM queue_entries WHERE request_id=?', (request_id,)).fetchone()
    day = local_time(utc_now_ms()).date().isoformat()
    usage = conn.execute('SELECT count(*) FROM send_requests WHERE canonical_uid=? AND date=? AND transmitted=1', (row['canonical_uid'], day)).fetchone()[0]
    conv_usage = conn.execute('SELECT count(*) FROM send_requests WHERE canonical_uid=? AND conv_id=? AND date=? AND transmitted=1', (row['canonical_uid'], row['conv_id'], day)).fetchone()[0]
    preview = dict(request=dict(row), decisions=events, resolved=final, outstanding_unknown=outstanding,
        circuits=breakers, rotation=dict(state) if state else None, active_requests=active,
        route=dict(route), day=day, account_transmitted_today=usage, conversation_transmitted_today=conv_usage,
        warning='Resolution is not SUCCESS. No quota refund, rotation advance, breaker reset or send. Closing permits future new requests.')
    preview['fingerprint'] = rotation.fingerprint(preview)
    return preview


def preview(request_id, *, db_path):
    ledger.check_ready(db_path)
    with closing(ledger._get_readonly_connection(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute('BEGIN')
        return _preview(conn, request_id)


def resolve(request_id, action, expected_preview, reason, evidence, *, db_path):
    from ledger_requests import transaction, event, utc_now_ms, now
    from queue_service import binding
    if action not in ACTIONS:
        raise ValueError('Unknown resolution action')
    reason, evidence = safe_note(reason), safe_note(evidence)
    with transaction(db_path) as conn:
        actual = _preview(conn, request_id)
        if actual != expected_preview or actual['resolved']:
            raise ledger.LedgerError('Stale or already resolved UNKNOWN preview; review again')
        replacement = None
        if action == 'AUTHORIZE_REPLACEMENT':
            old = actual['request']
            route = actual['route']
            if not route['session_name'] or binding(conn, route['session_name']) != old['canonical_uid']:
                raise ledger.LedgerError('Replacement requires an existing verified queue binding')
            payload = json.loads(old['payload_json'])
            if not isinstance(payload.get('message'), str) or not payload.get('target'):
                raise ledger.LedgerError('Legacy UNKNOWN has no sendable immutable payload; replacement refused')
            state = actual['rotation']
            if old['campaign_id'] is not None:
                if not state or (state['success_seq'], state['selection_generation']) != (old['rotation_seq'], old['selection_generation']):
                    raise ledger.LedgerError('Stale rotation selection; replacement refused')
                if conn.execute("SELECT 1 FROM send_requests WHERE canonical_uid=? AND conv_id=? AND campaign_id=? AND status IN ('queued','pending')", (old['canonical_uid'], old['conv_id'], old['campaign_id'])).fetchone():
                    raise ledger.LedgerError('Rotation scope has an active request; review it first')
            replacement = secrets.token_hex(16)
            key = 'replacement:' + replacement
            conn.execute('''INSERT INTO send_requests(request_id,canonical_uid,conv_id,idempotency_key,payload_json,
                status,created_at,client_msg_id,campaign_id,rotation_seq,selection_generation,snapshot_json,intent_json)
                VALUES(?,?,?,?,?,'queued',?,?,?,?,?,?,?)''', (replacement, old['canonical_uid'], old['conv_id'], key,
                old['payload_json'], now(), str(uuid.uuid4()), old['campaign_id'], old['rotation_seq'],
                old['selection_generation'], old['snapshot_json'], old['intent_json']))
            conn.execute('INSERT INTO queue_entries(request_id,session_name,policy_reference,policy_fingerprint) VALUES(?,?,?,?)',
                (replacement, route['session_name'], route['policy_reference'], route['policy_fingerprint']))
            event(conn, replacement, 'REPLACEMENT_CREATED', {'source_unknown_request_id': request_id, 'reason': reason})
        conn.execute('''INSERT INTO unknown_resolution_events(request_id,action,reason,evidence,preview_fingerprint,at_ms,replacement_request_id)
            VALUES(?,?,?,?,?,?,?)''', (request_id, action, reason, evidence, actual['fingerprint'], utc_now_ms(), replacement))
        event(conn, request_id, 'UNKNOWN_REVIEWED', {'action': action, 'replacement_request_id': replacement})
        return dict(action=action, request_id=request_id, replacement_request_id=replacement, sent=False)
