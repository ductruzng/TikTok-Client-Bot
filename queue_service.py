"""Durable routing/FIFO admission shared by one-shot and queue execution."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3

import ledger
import rotation


class QueueHeld(ledger.LedgerError):
    def __init__(self, code, detail):
        self.code, self.detail = code, detail
        super().__init__(f'{code}: {detail}')

    def __reduce__(self):
        return type(self), (self.code, self.detail)


def policy_fingerprint(config):
    from ledger_requests import settings_from_config
    from main import validate_config
    valid, _, targets = validate_config(config)
    if not valid:
        raise ValueError('Queue policy configuration is invalid')
    return rotation.fingerprint({'session': config['session'], 'targets': targets,
        'message': config.get('message', '') if 'rotation' not in config else None,
        'rotation': rotation.catalog(config), 'settings': settings_from_config(config)})


def normalize_policy(config):
    from main import validate_config
    valid, _, targets = validate_config(config)
    if not valid:
        raise ValueError('Queue policy configuration is invalid')
    return dict(config, targets=targets)


def binding(conn, session):
    row = conn.execute("SELECT canonical_uid FROM breaker_state WHERE scope_type='session' AND scope_key=?", (session,)).fetchone()
    if not session or not row or not row[0]:
        raise QueueHeld('IDENTITY_UNBOUND', 'Session requires an existing server-verified identity binding')
    return row[0]


def verified_uid(session, *, db_path):
    ledger.check_ready(db_path)
    with closing(ledger._get_readonly_connection(db_path)) as conn:
        return binding(conn, session)


def insert_entry(conn, request_id, uid, session=None, policy_reference=None, policy_config=None):
    if session is None and policy_reference is None and policy_config is None:
        conn.execute('INSERT INTO queue_entries(request_id) VALUES(?)', (request_id,))
        return
    if not session or not policy_reference or policy_config is None:
        raise QueueHeld('ROUTE_UNBOUND', 'Session and explicit policy reference/configuration are required together')
    if binding(conn, session) != uid or policy_config.get('session') != session:
        raise QueueHeld('IDENTITY_MISMATCH', 'Queue routing does not match verified identity')
    conn.execute('INSERT INTO queue_entries(request_id,session_name,policy_reference,policy_fingerprint) VALUES(?,?,?,?)',
                 (request_id, session, str(Path(policy_reference).absolute()), policy_fingerprint(policy_config)))


def check_claim(conn, row, session, policy_reference, policy_config):
    route = conn.execute('SELECT * FROM queue_entries WHERE request_id=?', (row['request_id'],)).fetchone()
    if not route or not route['session_name']:
        raise QueueHeld('ROUTE_UNBOUND', 'Review this request with queue-bind before execution')
    if binding(conn, session) != row['canonical_uid'] or session != route['session_name']:
        raise QueueHeld('IDENTITY_MISMATCH', 'Claim session does not match the verified request account')
    if not policy_reference or str(Path(policy_reference).absolute()) != route['policy_reference'] or policy_config is None:
        raise QueueHeld('POLICY_UNBOUND', 'Claim requires the exact bound policy reference and current configuration')
    if policy_config.get('session') != session or policy_fingerprint(policy_config) != route['policy_fingerprint']:
        raise QueueHeld('POLICY_CHANGED', 'Current configuration differs; explicitly review/rebind the queued request')
    target = json.loads(row['payload_json']).get('target')
    if target not in normalize_policy(policy_config)['targets']:
        raise QueueHeld('TARGET_CHANGED', 'Snapshot target is absent from the current policy')


def check_fifo(conn, row):
    head = conn.execute('''SELECT r.request_id FROM send_requests r JOIN queue_entries q USING(request_id)
        WHERE r.canonical_uid=? AND r.conv_id=? AND r.status IN ('queued','pending')
        ORDER BY q.enqueue_seq LIMIT 1''', (row['canonical_uid'], row['conv_id'])).fetchone()
    if not head or head[0] != row['request_id']:
        raise QueueHeld('FIFO_BLOCKED', f'Older conversation head {head[0] if head else "missing"} must be handled first')


def _bind_preview(conn, request_id, config, policy_reference):
    from ledger_requests import require_queued
    row = conn.execute('SELECT * FROM send_requests WHERE request_id=?', (request_id,)).fetchone()
    require_queued(row)
    uid = binding(conn, config.get('session'))
    if uid != row['canonical_uid']:
        raise QueueHeld('IDENTITY_MISMATCH', 'Configuration session belongs to another account')
    payload = json.loads(row['payload_json'])
    if payload.get('target') not in normalize_policy(config)['targets']:
        raise QueueHeld('TARGET_CHANGED', 'Exact request target must be present in the policy')
    if row['campaign_id'] is None and payload.get('message') != config.get('message'):
        raise QueueHeld('MESSAGE_CHANGED', 'Fixed message differs; cancel and enqueue a new request')
    route = conn.execute('SELECT * FROM queue_entries WHERE request_id=?', (request_id,)).fetchone()
    binding_event = conn.execute("SELECT max(event_id) FROM request_events WHERE request_id=? AND event_type='QUEUE_BOUND'", (request_id,)).fetchone()[0]
    return dict(request=dict(row), current_route=dict(route), session_name=config['session'],
                policy_reference=str(Path(policy_reference).absolute()), policy_fingerprint=policy_fingerprint(config),
                binding_event=binding_event)


def preview_bind(request_id, config, policy_reference, *, db_path):
    ledger.check_ready(db_path)
    with closing(ledger._get_readonly_connection(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute('BEGIN')
        return _bind_preview(conn, request_id, config, policy_reference)


def bind_request(request_id, config, policy_reference, preview, reason, *, db_path):
    from ledger_requests import transaction, require_reason, event
    require_reason(reason)
    with transaction(db_path) as conn:
        actual = _bind_preview(conn, request_id, config, policy_reference)
        if actual != preview:
            raise QueueHeld('STALE_PREVIEW', 'Review the queue binding again')
        conn.execute('UPDATE queue_entries SET session_name=?,policy_reference=?,policy_fingerprint=? WHERE request_id=?',
                     (actual['session_name'], actual['policy_reference'], actual['policy_fingerprint'], request_id))
        event(conn, request_id, 'QUEUE_BOUND', {'reason': reason, 'review': actual})


def enqueue(config, policy_reference, key, *, db_path):
    from ledger_requests import create_request
    if not isinstance(key, str) or not key.strip():
        raise ValueError('Explicit idempotency key required')
    config = normalize_policy(config)
    uid = verified_uid(config['session'], db_path=db_path)
    rows = []
    for target in config['targets']:
        payload = {'target': target, 'message': config.get('message', '')}
        row, _ = create_request(uid, target['conv_id'], task_request_key(key, target['conv_id']), payload,
            db_path=db_path, rotation_config=config if 'rotation' in config else None,
            session_name=config['session'], policy_reference=policy_reference, policy_config=config)
        rows.append(row)
    return rows


def task_request_key(key, conv_id):
    """Keep the existing one-shot key encoding for compatibility across adapters."""
    return json.dumps([key, conv_id])


def list_queue(*, db_path, session=None):
    ledger.check_ready(db_path)
    with closing(ledger._get_readonly_connection(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        sql = 'SELECT r.*,q.enqueue_seq,q.session_name,q.policy_reference,q.policy_fingerprint FROM send_requests r JOIN queue_entries q USING(request_id)'
        rows = conn.execute(sql + (' WHERE q.session_name=?' if session else '') + ' ORDER BY q.enqueue_seq', (session,) if session else ())
        return [dict(r) for r in rows]


def candidates(*, db_path, session):
    """Fixed finite snapshot; blocked heads cannot be overtaken in their conversation."""
    verified_uid(session, db_path=db_path)
    return [r for r in list_queue(db_path=db_path, session=session) if r['status'] == 'queued']


def preview_run(*, db_path, session):
    from ledger_requests import check_admission, settings_from_config
    result = []
    ledger.check_ready(db_path)
    with closing(ledger._get_readonly_connection(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute('BEGIN')
        for row in candidates(db_path=db_path, session=session):
            item = dict(request_id=row['request_id'], enqueue_seq=row['enqueue_seq'], eligible=False)
            try:
                cfg = read_policy(row['policy_reference'])
                check_admission(conn, row, settings_from_config(cfg), rotation_config=cfg,
                    session_name=session, policy_reference=row['policy_reference'], policy_config=cfg)
                item['eligible'] = True
            except (ledger.LedgerError, ValueError, OSError) as exc:
                item.update(reason=getattr(exc, 'code', type(exc).__name__), detail=str(exc))
                if hasattr(exc, 'result'):
                    item.update(exc.result())
            result.append(item)
    return result


def read_policy(path):
    from runtime_paths import contained
    contained(path, private=True)
    with open(path, encoding='utf-8-sig') as stream:
        config = json.load(stream)
    policy_fingerprint(config)
    return normalize_policy(config)


async def run_once(*, db_path, session, max_jobs=1, confirm_request=None):
    """Explicit finite consumer. No retries, sleep, automatic accounts or new-job polling."""
    from oneshot import run_oneshot_send
    if type(max_jobs) is not int or not 1 <= max_jobs <= 100:
        raise ValueError('max_jobs must be between 1 and 100')
    if confirm_request is None:
        raise ValueError('Queue execution requires interactive per-request confirmation')
    ledger.check_ready(db_path)
    results = []
    transmitted_jobs = 0
    with ledger.RunLock(str(Path(db_path).absolute().parent / 'run.lock')) as lock:
        from ledger_requests import recover_pending
        recover_pending(db_path=db_path, run_lock=lock)
        fixed = candidates(db_path=db_path, session=session)
        for candidate in fixed:
            if transmitted_jobs >= max_jobs:
                break
            from ledger_requests import get_request
            was_transmitted = get_request(candidate['request_id'], db_path=db_path)['transmitted']
            try:
                output = await run_oneshot_send(candidate['policy_reference'], db_path=db_path,
                    request_id=candidate['request_id'], confirm_request=confirm_request, _run_lock=lock,
                    _expected_session=session)
                results.extend(output['results'])
            except (ledger.LedgerError, ValueError, OSError) as exc:
                stored = get_request(candidate['request_id'], db_path=db_path)
                results.append(dict(request_id=candidate['request_id'], status='skipped', existing_status=stored['status'],
                    reason=getattr(exc, 'code', type(exc).__name__), detail=str(exc)))
                if getattr(exc, 'code', None) == 'IDENTITY_UNBOUND':
                    break
            finally:
                # Count durable transmission markers even if cleanup/result handling failed.
                transmitted_jobs += int(not was_transmitted and get_request(candidate['request_id'], db_path=db_path)['transmitted'])
    return {'results': results}
