"""Local readiness report; never opens SQLite in a mode that creates sidecars."""
from contextlib import closing
import importlib.metadata
import json
import os
from pathlib import Path
import sqlite3
import sys
from zoneinfo import ZoneInfo

from relttk import runtime_paths as paths


def _stamp(db):
    return tuple((p.name, p.stat().st_size, p.stat().st_mtime_ns) if p.exists() else (p.name, None)
                 for p in (db, Path(str(db)+'-wal'), Path(str(db)+'-shm'), Path(str(db)+'-journal')))


def open_quiescent(db):
    """Immutable SQLite ignores WAL, so refuse any nonempty WAL/journal first.

    Only a quiescent main-file snapshot is inspected. Never claim live-WAL readiness.
    """
    db = paths.inspect_path(db, private=True)
    for suffix in ('-wal', '-shm', '-journal'):
        sidecar = Path(str(db)+suffix)
        paths.inspect_path(sidecar, must_exist=False, private=True)
        if suffix != '-shm' and sidecar.exists() and sidecar.stat().st_size:
            raise paths.UnsafeRuntime('DATABASE_NOT_QUIESCENT')
    return sqlite3.connect(db.as_uri()+'?mode=ro&immutable=1', uri=True)


def report(runtime_dir, db_path, config_path, *, check_credentials=False):
    checks = []
    def add(name, state, code): checks.append(dict(check=name, state=state, code=code))
    try:
        base = paths.root(runtime_dir)
        if paths.root() is not None and paths.root() != base:
            raise paths.UnsafeRuntime('RUNTIME_ROOT_CONFLICT')
        db = paths.contained(db_path, base, private=True)
        policy = paths.contained(config_path, base, private=True)
        cfg = json.loads(policy.read_text(encoding='utf-8-sig'))
        from relttk.storage.queue_service import policy_fingerprint
        policy_fingerprint(cfg)
        session = cfg['session']
        add('paths_policy', 'PASS', 'EXPLICIT_RUNTIME')
    except (ValueError, OSError, KeyError):
        add('paths_policy', 'BLOCKED', 'RUNTIME_OR_POLICY_INVALID')
        return dict(state='BLOCKED', checks=checks)
    add('python', 'PASS' if sys.version_info >= (3, 10) else 'BLOCKED', 'PYTHON_310_REQUIRED')
    for name in ('websockets', 'lz4', 'qrcode', 'tzdata'):
        try:
            version = importlib.metadata.version(name)
            numbers = tuple(int(x) for x in version.split('.') if x.isdecimal())
            ranges = {'websockets': ((15,0,1),(16,)), 'lz4': ((4,4,5),(5,)),
                      'qrcode': ((8,),(9,)), 'tzdata': ((2024,1),(9999,))}
            low, high = ranges[name]
            add(name, 'PASS' if low <= numbers < high else 'BLOCKED', 'VERSION_'+version)
        except importlib.metadata.PackageNotFoundError:
            add(name, 'BLOCKED', 'DEPENDENCY_MISSING')
    try:
        ZoneInfo('Asia/Ho_Chi_Minh')
        with closing(sqlite3.connect(':memory:')) as conn:
            if conn.execute("SELECT json_valid('{}')").fetchone()[0] != 1:
                raise ValueError()
        add('sqlite_timezone', 'PASS', 'JSON_TZ_AVAILABLE')
    except (ValueError, sqlite3.Error, KeyError):
        add('sqlite_timezone', 'BLOCKED', 'JSON_OR_TZ_MISSING')
    try:
        before = _stamp(db)
        with closing(open_quiescent(db)) as conn:
            conn.row_factory = sqlite3.Row
            from relttk.storage.ledger_migrations import validate_schema
            from relttk.identity import circuit_breaker as cb
            from relttk.storage import queue_service as queue
            validate_schema(conn)
            if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError()
            uid = queue.binding(conn, session)
            cb.check(conn, uid, session)
            if conn.execute("SELECT 1 FROM send_requests WHERE canonical_uid=? AND status='failed_unknown' AND NOT EXISTS (SELECT 1 FROM unknown_resolution_events u WHERE u.request_id=send_requests.request_id AND u.action!='KEEP_BLOCKED')", (uid,)).fetchone():
                raise ValueError('UNKNOWN')
        if before != _stamp(db):
            raise ValueError('DATABASE_CHANGED')
        from relttk.storage.ledger_migrations import VERSION
        add('ledger_binding', 'PASS', f'QUIESCENT_V{VERSION}_BOUND')
    except Exception:
        add('ledger_binding', 'BLOCKED', 'LEDGER_BINDING_OR_CIRCUIT_INVALID')
    try:
        cookie_path = paths.credential_path(session, base=base)
        auth_path = paths.credential_path(session, auth=True, base=base)
        if check_credentials:
            cookies, auth = paths.read_private_json(cookie_path), paths.read_private_json(auth_path)
            from relttk.transport.client import validate_ws_auth
            validate_ws_auth(auth, session_name=session, cookies=cookies)
            add('credentials', 'PASS', 'LOCAL_PAIR_ONLY')
        else:
            add('credentials', 'UNVERIFIED', 'METADATA_ONLY')
    except (ValueError, OSError):
        add('credentials', 'BLOCKED', 'PRIVATE_SESSION_AUTH_REQUIRED')
    add('identity_protocol', 'UNVERIFIED', 'AUTHENTICATED_SELF_CONTRACT_UNVERIFIED')
    add('host_live', 'UNVERIFIED', 'DEBIAN_AND_TIKTOK_NOT_TESTED')
    add('identity_contract', 'UNVERIFIED', 'IDENTITY_CONTRACT_BLOCKED')
    if os.name == 'nt':
        add('ownership', 'UNVERIFIED', 'NTFS_ACL_NOT_CERTIFIED')
    return dict(state='BLOCKED' if any(c['state']=='BLOCKED' for c in checks) else 'UNVERIFIED', checks=checks)
