"""Explicit finite worker consent and internal admission waits. No enqueue or scheduler."""
import asyncio
from contextlib import closing
from dataclasses import dataclass, field
from datetime import timedelta
import json
from pathlib import Path
import secrets
import sqlite3
import time

from relttk.identity import circuit_breaker as breaker
from relttk.storage import ledger
from relttk.storage import ledger_requests as requests
from relttk.storage import queue_service as queue
from relttk.runtime import rotation

TEMPORAL = {'MIN_INTERVAL', 'SLIDING_WINDOW', 'ACCOUNT_DAILY_LIMIT',
            'CONVERSATION_DAILY_LIMIT', 'REPEAT_DISABLED', 'CROSSOVER_GUARD'}
TERMINAL = {'COMPLETE', 'WAIT_LIMIT', 'HELD', 'NEEDS_OWNER_REVIEW', 'REVOKED'}


class WorkerHeld(queue.QueueHeld):
    pass


@dataclass(frozen=True)
class RunContext:
    run_id: str
    fingerprint: str
    monotonic_deadline: float | None = None
    stop_event: object = field(default=None, repr=False, compare=False)


def _connection(db_path):
    ledger.check_ready(db_path)
    conn = ledger._get_readonly_connection(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute('BEGIN')
    return conn


def _circuits(conn, uid, session):
    return {kind: (conn.execute('SELECT version FROM breaker_state WHERE scope_type=? AND scope_key=?',
            (kind, key)).fetchone() or [0])[0] for kind, key in breaker.scopes(uid, session)}


def _expected(conn, row):
    route = conn.execute('SELECT * FROM queue_entries WHERE request_id=?', (row['request_id'],)).fetchone()
    bound = conn.execute("SELECT max(event_id) FROM request_events WHERE request_id=? AND event_type='QUEUE_BOUND'",
                         (row['request_id'],)).fetchone()[0]
    identity = {k: row[k] for k in ('request_id', 'canonical_uid', 'conv_id', 'client_msg_id',
        'payload_json', 'snapshot_json', 'intent_json', 'campaign_id', 'rotation_seq', 'selection_generation')}
    return {'request_id': row['request_id'], 'identity_hash': rotation.fingerprint(identity),
            'route': dict(route), 'binding_event': bound}


def _preview(conn, session, ids, max_jobs, max_wait, expires_at_ms):
    if type(max_jobs) is not int or not 1 <= max_jobs <= 100:
        raise ValueError('max_jobs must be an integer between 1 and 100')
    if type(max_wait) is not int or not 0 <= max_wait <= 86400:
        raise ValueError('max_wait must be an integer between 0 and 86400 seconds')
    if not isinstance(ids, (list, tuple)) or not ids or any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Explicit distinct request IDs required')
    instant = requests.utc_now_ms()
    if type(expires_at_ms) is not int or expires_at_ms <= instant:
        raise ValueError('Consent expiry must be a future UTC epoch millisecond timestamp')
    uid = queue.binding(conn, session)
    breaker.check(conn, uid, session)
    members, messages = [], []
    for rid in ids:
        row = conn.execute('SELECT * FROM send_requests WHERE request_id=?', (rid,)).fetchone()
        requests.require_queued(row)
        if row['canonical_uid'] != uid:
            raise WorkerHeld('IDENTITY_MISMATCH', 'Request does not belong to the selected verified account')
        expected = _expected(conn, row)
        route = expected['route']
        if not route['policy_reference']:
            raise WorkerHeld('ROUTE_UNBOUND', 'Review queue binding before worker approval')
        cfg = queue.read_policy(route['policy_reference'])
        queue.check_claim(conn, row, session, route['policy_reference'], cfg)
        requests.check_snapshot(conn, row, cfg)
        members.append(expected)
        messages.append({'request_id': rid, 'payload': json.loads(row['payload_json']),
                         'snapshot': json.loads(row['snapshot_json']) if row['snapshot_json'] else None})
    members.sort(key=lambda m: m['route']['enqueue_seq'])
    consent = dict(session=session, uid=uid, max_jobs=max_jobs, max_wait=max_wait,
        expires_at_ms=expires_at_ms, circuits=_circuits(conn, uid, session), members=members)
    messages.sort(key=lambda m: next(i for i, member in enumerate(members) if member['request_id'] == m['request_id']))
    return dict(consent=consent, fingerprint=rotation.fingerprint(consent), messages=messages)


def preview(session, ids, *, db_path, max_jobs=1, max_wait=300, expires_at_ms=None):
    if expires_at_ms is None:
        local = requests.local_time(requests.utc_now_ms())
        expires_at_ms = int((local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).timestamp()*1000)
    with closing(_connection(db_path)) as conn:
        return _preview(conn, session, ids, max_jobs, max_wait, expires_at_ms)


def _event(conn, run_id, kind, details=None):
    # Never forge a transmission timestamp. Administrative outcome time is monotonic in history.
    last = conn.execute('SELECT max(at_ms) FROM worker_events WHERE run_id=?', (run_id,)).fetchone()[0] or 0
    conn.execute('INSERT INTO worker_events(run_id,event_type,at_ms,details_json) VALUES(?,?,?,?)',
                 (run_id, kind, max(last, requests.utc_now_ms()), rotation.encode(details or {})))


def authorize(review, reason, *, db_path):
    requests.require_reason(reason)
    c = review['consent']
    with requests.transaction(db_path) as conn:
        actual = _preview(conn, c['session'], [m['request_id'] for m in c['members']],
                          c['max_jobs'], c['max_wait'], c['expires_at_ms'])
        if actual != review:
            raise WorkerHeld('STALE_PREVIEW', 'Worker scope changed; review again')
        return _insert_authorization(conn, actual, reason)


def _insert_authorization(conn, review, reason, *, parent=None):
    """Internal insertion only after caller validates finite or recurring authority."""
    c = review['consent']
    run_id = secrets.token_hex(16)
    conn.execute('INSERT INTO worker_runs VALUES(?,?,?,?)',
                 (run_id, review['fingerprint'], rotation.encode(c), requests.utc_now_ms()))
    for ordinal, member in enumerate(c['members']):
        conn.execute('INSERT INTO worker_run_requests VALUES(?,?,?,?)',
                     (run_id, ordinal, member['request_id'], rotation.encode(member)))
    _event(conn, run_id, 'APPROVED', {'reason': reason, 'fingerprint': review['fingerprint'], **({'recurring_parent': parent} if parent else {})})
    return run_id


def _load(conn, run_id, fingerprint=None):
    row = conn.execute('SELECT * FROM worker_runs WHERE run_id=?', (run_id,)).fetchone()
    if not row or (fingerprint is not None and row['manifest_fingerprint'] != fingerprint):
        raise WorkerHeld('CONSENT_INVALID', 'Exact existing run ID and manifest fingerprint required')
    c = json.loads(row['consent_json'])
    if rotation.fingerprint(c) != row['manifest_fingerprint']:
        raise WorkerHeld('CONSENT_INVALID', 'Worker manifest integrity failed')
    members = [json.loads(r[0]) for r in conn.execute('SELECT expected_json FROM worker_run_requests WHERE run_id=? ORDER BY ordinal', (run_id,))]
    if members != c['members']:
        raise WorkerHeld('CONSENT_INVALID', 'Worker membership integrity failed')
    return c


def _used(conn, run_id):
    return conn.execute('''SELECT count(*) FROM worker_run_requests m JOIN send_requests r USING(request_id)
        WHERE m.run_id=? AND r.transmitted=1''', (run_id,)).fetchone()[0]


def check_authorization(conn, row, context, *, claim=False):
    """Called again inside the same writer transaction that commits the marker."""
    if not isinstance(context, RunContext):
        raise WorkerHeld('CONSENT_INVALID', 'Typed worker execution context required')
    c = _load(conn, context.run_id, context.fingerprint)
    from relttk.runtime.scheduling import check_parent
    check_parent(conn, run_id=context.run_id, claim=claim)
    last = conn.execute('SELECT event_type,at_ms FROM worker_events WHERE run_id=? ORDER BY event_id DESC LIMIT 1', (context.run_id,)).fetchone()
    if last[0] in TERMINAL:
        raise WorkerHeld('RUN_CLOSED', 'Worker run is closed; old consent cannot resume')
    if conn.execute("SELECT 1 FROM worker_events WHERE run_id=? AND event_type IN ('REVOKED','NEEDS_OWNER_REVIEW')", (context.run_id,)).fetchone():
        raise WorkerHeld('CONSENT_REVOKED', 'Owner review or fresh consent required')
    instant = requests.utc_now_ms()
    if instant < last[1]:
        raise WorkerHeld('CLOCK_SKEW', 'Worker clock precedes durable history')
    if queue.binding(conn, c['session']) != c['uid']:
        raise WorkerHeld('IDENTITY_MISMATCH', 'Worker account binding changed')
    breaker.check(conn, c['uid'], c['session'])
    if _circuits(conn, c['uid'], c['session']) != c['circuits']:
        raise WorkerHeld('CIRCUIT_CHANGED', 'Circuit version changed, including OPEN then RESET; fresh consent required')
    started = conn.execute("SELECT details_json FROM worker_events WHERE run_id=? AND event_type='RUN_STARTED'", (context.run_id,)).fetchone()
    deadline = json.loads(started[0])['deadline_ms'] if started else c['expires_at_ms']
    if instant >= min(c['expires_at_ms'], deadline) or (context.monotonic_deadline is not None and time.monotonic() >= context.monotonic_deadline):
        raise WorkerHeld('CONSENT_EXPIRED', 'Original worker deadline/consent expired')
    if context.stop_event is not None and context.stop_event.is_set():
        raise WorkerHeld('WORKER_STOPPED', 'Shutdown requested before transmission')
    if claim and not started:
        raise WorkerHeld('RUN_NOT_STARTED', 'Durable first start is required before a worker claim')
    if _used(conn, context.run_id) >= c['max_jobs']:
        raise WorkerHeld('WORKER_BUDGET', 'Manifest transmission budget exhausted')
    if row is not None:
        member = next((m for m in c['members'] if m['request_id'] == row['request_id']), None)
        if not member or _expected(conn, row) != member:
            raise WorkerHeld('SCOPE_CHANGED', 'Request snapshot/routing/bind version differs from Owner consent')
    return c


def status(run_id, *, db_path):
    with closing(_connection(db_path)) as conn:
        c = _load(conn, run_id)
        events = [dict(r) for r in conn.execute('SELECT * FROM worker_events WHERE run_id=? ORDER BY event_id', (run_id,))]
        return dict(run_id=run_id, fingerprint=rotation.fingerprint(c), consent=c,
                    transmitted=_used(conn, run_id), state=events[-1]['event_type'], events=events)


def revoke(run_id, expected, reason, *, db_path):
    requests.require_reason(reason)
    with requests.transaction(db_path) as conn:
        c = _load(conn, run_id)
        events = [dict(r) for r in conn.execute('SELECT * FROM worker_events WHERE run_id=? ORDER BY event_id', (run_id,))]
        actual = dict(run_id=run_id, fingerprint=rotation.fingerprint(c), consent=c,
                      transmitted=_used(conn, run_id), state=events[-1]['event_type'], events=events)
        if actual != expected:
            raise WorkerHeld('STALE_PREVIEW', 'Worker changed; review revocation again')
        _event(conn, run_id, 'REVOKED', {'reason': reason})


def _record(run_id, kind, *, db_path, details=None):
    with requests.transaction(db_path) as conn:
        # A late pass from another runner must never reopen a closed consent.
        last = conn.execute('SELECT event_type FROM worker_events WHERE run_id=? ORDER BY event_id DESC LIMIT 1',
                            (run_id,)).fetchone()
        if last and last[0] in TERMINAL:
            return
        _event(conn, run_id, kind, details)


def _start(context, db_path):
    with requests.transaction(db_path) as conn:
        c = check_authorization(conn, None, context)
        first = conn.execute("SELECT details_json FROM worker_events WHERE run_id=? AND event_type='RUN_STARTED'", (context.run_id,)).fetchone()
        if first:
            return json.loads(first[0])['deadline_ms']
        instant = requests.utc_now_ms()
        deadline = min(c['expires_at_ms'], instant+c['max_wait']*1000) if c['max_wait'] else c['expires_at_ms']
        _event(conn, context.run_id, 'RUN_STARTED', {'first_started_at_ms': instant, 'deadline_ms': deadline})
        return deadline


async def _wait(stop, seconds):
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        pass


async def run(run_id, fingerprint, *, db_path, stop_event=None, wait=None):
    """Only rate admission is reconsidered. Terminal requests are never retried."""
    from relttk.transport.oneshot import run_oneshot_send
    stop = stop_event if stop_event is not None else asyncio.Event()
    wait = wait or _wait
    context = RunContext(run_id, fingerprint, stop_event=stop)
    results, held = [], []
    # Invalid IDs/hashes never append events to an unrelated run.
    with closing(_connection(db_path)) as conn:
        c = _load(conn, run_id, fingerprint)
        last = conn.execute('SELECT event_type FROM worker_events WHERE run_id=? ORDER BY event_id DESC LIMIT 1', (run_id,)).fetchone()[0]
        if last in TERMINAL:
            from relttk.runtime.scheduling import check_parent, ScheduleHeld
            try:
                check_parent(conn, run_id=run_id)
            except ScheduleHeld as exc:
                return dict(state='NEEDS_OWNER_REVIEW', reason=exc.code, results=[], held=[])
            return dict(state=last, results=[], held=[])
    try:
        deadline = None
        while True:
            if stop.is_set():
                _record(run_id, 'STOPPED', db_path=db_path)
                return dict(state='STOPPED', results=results, held=held)
            wake_times, held, queued = [], [], 0
            # One pass owns the process lock; absolutely no lock, connection or WS survives sleep.
            with ledger.RunLock(str(Path(db_path).absolute().parent / 'run.lock')) as lock:
                requests.recover_pending(db_path=db_path, run_lock=lock)
                if deadline is None:
                    deadline = _start(context, db_path)
                    context = RunContext(run_id, fingerprint, time.monotonic()+max(0,(deadline-requests.utc_now_ms())/1000), stop)
                with closing(_connection(db_path)) as conn:
                    check_authorization(conn, None, context)
                _record(run_id, 'RUNNING', db_path=db_path)
                for member in c['members']:
                    if stop.is_set():
                        break
                    with closing(_connection(db_path)) as conn:
                        if _used(conn, run_id) >= c['max_jobs']:
                            break
                        row = conn.execute('SELECT * FROM send_requests WHERE request_id=?', (member['request_id'],)).fetchone()
                        if row['status'] != 'queued':
                            continue
                        queued += 1
                        try:
                            cfg = queue.read_policy(member['route']['policy_reference'])
                            check_authorization(conn, row, context)
                            # Admission may aggregate rate limits before FIFO/circuit; neither can be masked.
                            queue.check_fifo(conn, row)
                            requests.check_admission(conn, row, requests.settings_from_config(cfg), rotation_config=cfg,
                                session_name=c['session'], policy_reference=member['route']['policy_reference'], policy_config=cfg)
                        except requests.RateLimitError as exc:
                            times = [r['retry_at_ms'] for r in exc.reasons]
                            if exc.reasons and all(r['code'] in TEMPORAL and type(r['retry_at_ms']) is int for r in exc.reasons):
                                wake_times.append(max(times))
                            held.append(exc.result())
                            continue
                        except queue.QueueHeld as exc:
                            if isinstance(exc, WorkerHeld) and exc.code != 'SCOPE_CHANGED':
                                raise
                            held.append(dict(request_id=row['request_id'], reason=exc.code))
                            continue
                        except ledger.LedgerError as exc:
                            held.append(dict(request_id=row['request_id'], reason=type(exc).__name__))
                            continue
                        except (OSError, ValueError):
                            held.append(dict(request_id=row['request_id'], reason='POLICY_UNAVAILABLE'))
                            continue
                    output = await run_oneshot_send(member['route']['policy_reference'], db_path=db_path,
                        request_id=member['request_id'], _run_lock=lock, _expected_session=c['session'],
                        _worker_context=context)
                    results.extend(output['results'])
                    # No result label can refund the durable marker budget, including cleanup failures.
                    with closing(_connection(db_path)) as conn:
                        if _used(conn, run_id) < c['max_jobs'] and not stop.is_set():
                            check_authorization(conn, None, context)
                        else:
                            from relttk.runtime.scheduling import check_parent
                            if not stop.is_set():
                                check_parent(conn, run_id=run_id)
                            breaker.check(conn, c['uid'], c['session'])
            if stop.is_set():
                continue
            with closing(_connection(db_path)) as conn:
                # Manual activity during an unlocked interval may exhaust the budget
                # AND open the circuit. Check safety gates before reporting completion.
                check_authorization(conn, None, context)
                queued = conn.execute("SELECT count(*) FROM worker_run_requests m JOIN send_requests r USING(request_id) WHERE m.run_id=? AND r.status='queued'", (run_id,)).fetchone()[0]
            if not queued:
                outcome = 'COMPLETE'
                break
            if not wake_times:
                outcome = 'HELD'
                break
            remaining = min((deadline-requests.utc_now_ms())/1000, context.monotonic_deadline-time.monotonic())
            if not c['max_wait'] or remaining <= 0:
                outcome = 'WAIT_LIMIT'
                break
            delay = min(remaining, max(1, (min(wake_times)-requests.utc_now_ms())/1000))
            _record(run_id, 'WAITING_RATE_LIMIT', db_path=db_path, details={'retry_at_ms': min(wake_times)})
            await wait(stop, delay)
        _record(run_id, outcome, db_path=db_path)
        return dict(state=outcome, results=results, held=held)
    except ledger.LockError:
        return dict(state='BUSY', results=results, held=held)
    except Exception as exc:
        from relttk.runtime.scheduling import record_hold
        record_hold(exc, db_path=db_path)
        code = getattr(exc, 'code', type(exc).__name__)
        outcome = ('STOPPED' if code == 'WORKER_STOPPED' else 'COMPLETE' if code == 'WORKER_BUDGET'
                   else 'WAIT_LIMIT' if code == 'CONSENT_EXPIRED' else 'NEEDS_OWNER_REVIEW')
        # Preserve actual send/UNKNOWN history; only worker audit gets an outcome.
        _record(run_id, outcome, db_path=db_path, details={'reason': code})
        return dict(state=outcome, reason=code, results=results, held=held)
