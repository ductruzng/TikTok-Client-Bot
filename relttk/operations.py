"""Opt-in metadata sinks and explicit local administration; no send authority."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

_result = None
STATES = frozenset(('BLOCKED', 'UNKNOWN', 'DUE', 'NOT_DUE', 'MISSED', 'GRANT_EXPIRED',
    'GRANT_INACTIVE', 'HELD', 'ENQUEUED', 'EXISTING', 'COMPLETE', 'BUSY', 'STOPPED',
    'WAIT_LIMIT', 'NEEDS_OWNER_REVIEW', 'REVOKED', 'BACKUP_COMPLETE', 'QUIESCENT'))
# Strings from arbitrary nested data never become journal values.
REASONS = frozenset(('IDENTITY_CONTRACT_BLOCKED', 'DATABASE_NOT_QUIESCENT',
    'LOCAL_CHECK_FAILED', 'OPERATION_FAILED', 'CIRCUIT_OPEN', 'UNKNOWN_UNRESOLVED',
    'CLOCK_SKEW', 'GRANT_INACTIVE', 'GRANT_EXPIRED', 'MISSED', 'NOT_DUE',
    'POLICY_CHANGED', 'SCOPE_CHANGED', 'MIN_INTERVAL', 'SLIDING_WINDOW',
    'ACCOUNT_DAILY_LIMIT', 'CONVERSATION_DAILY_LIMIT', 'REPEAT_DISABLED',
    'BACKUP_COMPLETE', 'UNSUPPORTED_WORKLOAD', 'OUTPUT_UNAVAILABLE',
    'WAL_BACKUP_REQUIRES_NO_CKPT_ON_CLOSE'))
COUNTS = ('daily_used', 'daily_limit', 'total_used', 'total_limit', 'markers',
          'success', 'unknown', 'requests', 'last_occurrence_at_ms', 'retry_at_ms')


def metadata(result):
    if not isinstance(result, dict):
        result = {}
    worker = result.get('worker')
    source = worker if isinstance(worker, dict) else result
    state = source.get('state')
    out = {'state': state if isinstance(state, str) and state in STATES else 'UNKNOWN',
           'identity': 'IDENTITY_CONTRACT_BLOCKED'}
    reason = source.get('reason')
    if reason is not None:
        out['reason'] = reason if isinstance(reason, str) and reason in REASONS else 'OPERATION_FAILED'
    grant_state = result.get('grant_state')
    if isinstance(grant_state, str) and grant_state in ('AUTHORIZED','ACTIVATED','PAUSED','REVOKED','HELD'):
        out['grant_state'] = grant_state
    for values in (result, result.get('usage')):
        if isinstance(values, dict):
            for key in COUNTS:
                value = values.get(key)
                if type(value) is int and 0 <= value <= 2**63-1:
                    out[key] = value
    return out


def note(result):
    global _result
    _result = metadata(result)


def cli_entry(function, *, output_fd=None):
    """Mute Python AND native fd sinks before imports/parse/dispatch; capture nothing.

    If fd suppression cannot be installed, do not execute the function. Restore
    descriptors for callers, emit only an allowlist envelope to the saved fd.
    """
    global _result
    _result = None
    saved = []
    streams = (sys.stdout, sys.stderr)
    target = None
    status = 3
    muted = None
    try:
        for stream in streams:
            stream.flush()
        target = os.dup(1 if output_fd is None else output_fd)
        for fd in (1, 2):
            saved.append(os.dup(fd))
        muted = open(os.devnull, 'w', encoding='utf-8')
        os.dup2(muted.fileno(), 1)
        os.dup2(muted.fileno(), 2)
        sys.stdout = sys.stderr = muted
        try:
            status = function()
        except SystemExit as exc:
            status = exc.code if type(exc.code) is int else 3
        except BaseException:
            status = 3
        if type(status) is not int or status not in (0, 1, 2, 3):
            status = 3
        out = _result or {'state': 'BLOCKED', 'reason': 'OPERATION_FAILED',
                          'identity': 'IDENTITY_CONTRACT_BLOCKED'}
        out['exit_code'] = status
        data = (json.dumps(out, separators=(',', ':'))+'\n').encode('ascii')
        if len(data) > 2048:
            raise ValueError('OUTPUT_UNAVAILABLE')
        os.write(target, data)
    except BaseException:
        status = 3
    finally:
        sys.stdout, sys.stderr = streams
        for fd, original in zip((1, 2), saved):
            try:
                os.dup2(original, fd)
            finally:
                os.close(original)
        if muted is not None:
            muted.close()
        if target is not None:
            os.close(target)
    return status


def status(grant_id, *, db_path):
    from relttk.runtime import scheduling
    try:
        with scheduling.readonly(db_path) as conn:
            c, fp, event = scheduling._load(conn, grant_id)
            from relttk.storage.ledger_requests import local_time, utc_now_ms
            day = local_time(utc_now_ms()).date().isoformat()
            usage = scheduling._budgets(conn, c, day)
            counts = conn.execute('''SELECT count(*), coalesce(sum(transmitted),0),
                coalesce(sum(status='confirmed'),0), coalesce(sum(status='failed_unknown'),0)
                FROM daily_occurrence_requests m JOIN daily_occurrences d USING(occurrence_id)
                JOIN send_requests r USING(request_id) WHERE d.grant_id=?''', (grant_id,)).fetchone()
            last = conn.execute('SELECT max(start_ms) FROM daily_occurrences WHERE grant_id=?', (grant_id,)).fetchone()[0]
            # Quiescence is a storage observation; the identity gate is still blocked.
            return dict(state='BLOCKED', reason='IDENTITY_CONTRACT_BLOCKED', usage=usage,
                        grant_state=event['event_type'],
                        requests=counts[0], markers=counts[1], success=counts[2], unknown=counts[3],
                        last_occurrence_at_ms=last)
    except Exception as exc:
        return dict(state='UNKNOWN', reason='DATABASE_NOT_QUIESCENT' if str(exc)=='DATABASE_NOT_QUIESCENT'
                    else 'LOCAL_CHECK_FAILED')


def backup(db_path, destination, *, timeout=10.0):
    """Backup committed WAL under a writer reservation; never recover/checkpoint.

    Incomplete files remain labelled on failure. Publish by exclusive hard-link,
    never overwrite a destination. All operations are explicitly requested.
    """
    from relttk.storage import ledger
    from relttk.storage import ledger_migrations as migrations
    from relttk import runtime_paths as paths
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 60:
        raise ValueError('Invalid backup timeout')
    source = paths.contained(db_path, private=True)
    paths.inspect_path(source.parent, private=True)
    dest = paths.contained(destination, must_exist=False, private=True)
    paths.inspect_path(dest.parent, private=True)
    if not source.is_file() or dest.exists() or dest == source or str(dest) in (str(source)+s for s in ('-wal','-shm','-journal')):
        raise ValueError('Backup destination must be new')
    for suffix in ('-wal','-shm','-journal'):
        paths.inspect_path(Path(str(source)+suffix), private=True, must_exist=False)
    # SQLite may checkpoint/delete WAL on the last writer close. Disable that
    # behavior explicitly, or refuse WAL BEFORE opening a mutable connection.
    no_checkpoint = getattr(sqlite3, 'SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE', None)
    with source.open('rb') as stream:
        wal_mode = stream.read(20)[18:20] == b'\x02\x02'
    if wal_mode and (no_checkpoint is None or not hasattr(sqlite3.Connection, 'setconfig')):
        raise ValueError('WAL_BACKUP_REQUIRES_NO_CKPT_ON_CLOSE')
    staging = Path(str(dest)+'.incomplete')
    manifest = Path(str(dest)+'.manifest.json')
    if manifest.exists():
        raise ValueError('Backup manifest already exists')
    deadline = time.monotonic()+timeout
    def progress(*_):
        if time.monotonic() >= deadline:
            raise TimeoutError('Backup deadline')
    with ledger.RunLock(str(source.parent/'run.lock')):
        with closing(sqlite3.connect(source.as_uri()+'?mode=rw', uri=True, timeout=timeout, isolation_level=None)) as writer:
            if no_checkpoint is not None:
                writer.setconfig(no_checkpoint, True)
            writer.execute('BEGIN IMMEDIATE')
            try:
                migrations.validate_schema(writer)
                expected = _history_counts(writer)
                fd = os.open(staging, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
                with closing(sqlite3.connect(source.as_uri()+'?mode=ro', uri=True, timeout=timeout)) as reader, \
                     closing(sqlite3.connect(staging)) as target:
                    if no_checkpoint is not None:
                        reader.setconfig(no_checkpoint, True)
                    reader.backup(target, pages=64, progress=progress, sleep=0.01)
                    progress()
                    migrations.validate_schema(target)
                    if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or target.execute('PRAGMA foreign_key_check').fetchone():
                        raise ValueError('Backup validation failed')
                    if _history_counts(target) != expected:
                        raise ValueError('History mismatch')
                with staging.open('r+b') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest() if hasattr(hashlib,'file_digest') else _digest(stream)
                    os.fsync(stream.fileno())
                details = dict(schema=migrations.VERSION, counts=expected, sha256=digest,
                               snapshot_at_ms=int(time.time()*1000), python=sys.version.split()[0], sqlite=sqlite3.sqlite_version)
                with os.fdopen(os.open(manifest, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w', encoding='utf-8') as stream:
                    json.dump(details, stream, separators=(',', ':')); stream.flush(); os.fsync(stream.fileno())
                os.link(staging, dest)  # EEXIST is safe even after the initial check.
                staging.unlink()
                if os.name == 'posix':
                    fd = os.open(dest.parent, os.O_RDONLY | os.O_DIRECTORY)
                    try: os.fsync(fd)
                    finally: os.close(fd)
            finally:
                writer.rollback()
    return dict(state='BACKUP_COMPLETE', reason='BACKUP_COMPLETE', requests=expected['send_requests'])


def _digest(stream):
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(65536), b''):
        digest.update(chunk)
    return digest.hexdigest()


def _history_counts(conn):
    # Preserve every table, not just request counters; no new durable state.
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
    result = {name: conn.execute('SELECT count(*) FROM "'+name.replace('"','""')+'"').fetchone()[0] for (name,) in tables}
    result['markers'] = conn.execute('SELECT coalesce(sum(transmitted),0) FROM send_requests').fetchone()[0]
    return result
