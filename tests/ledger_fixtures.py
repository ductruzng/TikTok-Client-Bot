"""Explicit fixture setup and simulated clocks for pre-rate-limiter regressions."""
from contextlib import closing
from datetime import datetime
from pathlib import Path
import sqlite3
import json
from copy import deepcopy
from unittest.mock import patch

import ledger
import ledger_migrations
import ledger_requests
import circuit_breaker
import queue_service


def fixture_policy(uid, conv_id, payload, rotation_config=None):
    cfg = deepcopy(rotation_config or {})
    cfg['session'] = 'fixture_' + uid
    cfg['targets'] = [payload.get('target', {'conv_id': conv_id, 'conv_short_id': 1, 'conv_type': 1})]
    if 'rotation' not in cfg:
        cfg['message'] = payload.get('message', 'fixture') or 'fixture'
    return cfg


def fixture_create(uid, conv_id, key, payload, *, db_path, rotation_config=None, **options):
    """Explicit synthetic binding and valid target; no production admission is patched."""
    payload = dict(payload)
    payload.setdefault('target', {'conv_id': conv_id, 'conv_short_id': 1, 'conv_type': 1})
    payload.setdefault('message', 'fixture')
    cfg = fixture_policy(uid, conv_id, payload, rotation_config)
    ensure_fixture_binding(uid, cfg['session'], db_path)
    return ledger_requests.create_request(uid, conv_id, key, payload, db_path=db_path,
        rotation_config=rotation_config, session_name=cfg['session'],
        policy_reference=str(Path(db_path).parent / ('policy-' + conv_id.replace(':', '_') + '.json')),
        policy_config=cfg, **options)


def fixture_start(request_id, *, db_path, rotation_config=None, **options):
    row = ledger_requests.get_request(request_id, db_path=db_path)
    cfg = fixture_policy(row['canonical_uid'], row['conv_id'], json.loads(row['payload_json']), rotation_config)
    cfg.update({k: v for k, v in options.items() if k in ledger_requests.DEFAULT_SETTINGS})
    reference = str(Path(db_path).parent / ('policy-' + row['conv_id'].replace(':', '_') + '.json'))
    if row['status'] == 'queued':
        view = queue_service.preview_bind(request_id, cfg, reference, db_path=db_path)
        queue_service.bind_request(request_id, cfg, reference, view, 'fixture routing review', db_path=db_path)
    return ledger_requests.start_transmission(request_id, db_path=db_path, rotation_config=rotation_config,
        session_name=cfg['session'], policy_reference=reference, policy_config=cfg, **options)


async def fixture_send(ws, uid, target, text, *, db_path, rotation_config=None, existing_request=None, **options):
    """Transport regression adapter supplying explicit fake routing to the actual send core."""
    import oneshot
    cfg = fixture_policy(uid, target['conv_id'], {'target': target, 'message': text}, rotation_config)
    cfg.update({k: v for k, v in options.items() if k in ledger_requests.DEFAULT_SETTINGS})
    reference = str(Path(db_path).parent / ('policy-' + target['conv_id'].replace(':', '_') + '.json'))
    ensure_fixture_binding(uid, cfg['session'], db_path)
    if existing_request and ledger_requests.get_request(existing_request, db_path=db_path)['status'] == 'queued':
        # Tests that explicitly approve a changed snapshot also explicitly rebind its policy.
        view = queue_service.preview_bind(existing_request, cfg, reference, db_path=db_path)
        queue_service.bind_request(existing_request, cfg, reference, view, 'fixture reviewed routing', db_path=db_path)
    return await oneshot._send_target_oneshot(ws, uid, target, text, db_path=db_path,
        rotation_config=rotation_config, existing_request=existing_request,
        session_name=cfg['session'], policy_reference=reference, policy_config=cfg, **options)


def ensure_fixture_binding(uid, session, db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        row = conn.execute("SELECT canonical_uid FROM breaker_state WHERE scope_type='session' AND scope_key=?", (session,)).fetchone()
    if not row or not row[0]:
        circuit_breaker.bind_session(uid, session, db_path=db_path)


def initialize_fixture(path):
    if not Path(path).exists():
        ledger_migrations.initialize(path)


def fixture_clock(path, date):
    day = date or ledger.get_current_ho_chi_minh_date()
    base = int(datetime.fromisoformat(day + 'T12:00:00+07:00').timestamp() * 1000)
    with closing(sqlite3.connect(path)) as conn:
        last = conn.execute('SELECT max(transmission_started_at_ms) FROM send_requests WHERE date=?', (day,)).fetchone()[0]
    return max(base, (last + 60000) if last is not None else base)


def reserve_at(*args, date=None, db_path, **kwargs):
    if kwargs:
        raise TypeError('Legacy force/other options are unsupported')
    initialize_fixture(db_path)
    with patch.object(ledger_requests, 'utc_now_ms', return_value=fixture_clock(db_path, date)):
        uid, cid, client_id = args
        row, created = fixture_create(uid, cid, 'legacy-api:' + client_id, {'message': 'fixture'}, db_path=db_path, client_msg_id=client_id)
        if not created:
            raise ledger.QuotaExceededError('Reservation already exists')
        fixture_start(row['request_id'], db_path=db_path, date=date)
        return date or ledger.get_current_ho_chi_minh_date()


def start_at(*args, date=None, db_path, **kwargs):
    with patch.object(ledger_requests, 'utc_now_ms', return_value=fixture_clock(db_path, date)):
        return fixture_start(*args, date=date, db_path=db_path, **kwargs)


def migrate_v2_fixture(path):
    with closing(sqlite3.connect(path, isolation_level=None, timeout=30)) as conn:
        ledger_migrations._migrate_v2(conn, path)
