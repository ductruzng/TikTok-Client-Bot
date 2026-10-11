"""Explicit identity administration, never messaging or implicit setup."""
from contextlib import closing
import hashlib
from dataclasses import dataclass

from relttk.identity import circuit_breaker as cb
from relttk.storage import ledger
from relttk.identity import readiness
from relttk import runtime_paths as paths


@dataclass(frozen=True)
class VerifiedIdentity:
    session: str
    uid: str
    versions: dict
    generation: str

    def public(self):
        return dict(session=self.session, uid=self.uid, versions=self.versions,
                    verified=True, method='AUTHENTICATED_SELF')


def _versions(conn, session, verified_uid=None):
    row = conn.execute("SELECT canonical_uid,version FROM breaker_state WHERE scope_type='session' AND scope_key=?", (session,)).fetchone()
    uid, version = (row[0], row[1]) if row else (None, 0)
    account = conn.execute("SELECT version FROM breaker_state WHERE scope_type='account' AND scope_key=?", (uid,)).fetchone() if uid else None
    cb.check(conn, uid, session)
    result = dict(uid=uid, session_version=version, account_version=account[0] if account else 0)
    if verified_uid is not None:
        cb.check(conn, verified_uid, session)
        row = conn.execute("SELECT version FROM breaker_state WHERE scope_type='account' AND scope_key=?", (verified_uid,)).fetchone()
        result['verified_account_version'] = row[0] if row else 0
    return result


def preview(session, *, db_path):
    paths.contained(db_path)
    with closing(readiness.open_quiescent(db_path)) as conn:
        conn.row_factory = __import__('sqlite3').Row
        from relttk.storage.ledger_migrations import validate_schema
        validate_schema(conn)
        return dict(session=session, versions=_versions(conn, session), verified=False)


def verify(session, *, db_path):
    review = preview(session, db_path=db_path)
    path = paths.credential_path(session)
    cookies = paths.read_private_json(path)
    if not isinstance(cookies.get('sessionid'), str) or not cookies['sessionid']:
        raise ValueError('AUTHENTICATED_SESSION_REQUIRED')
    from core.api import get_own_user_id
    try:
        uid = get_own_user_id(cookies=cookies, use_cache=False)
    except Exception as exc:
        failure = cb.classify(exc, 'identity')
        if failure:
            cb.record_failure(failure, db_path=db_path, session=session)
        raise
    if not isinstance(uid, str) or not uid.isdecimal() or int(uid) <= 0:
        raise cb.ProtocolFailure('INVALID_SELF_UID')
    with closing(readiness.open_quiescent(db_path)) as conn:
        conn.row_factory = __import__('sqlite3').Row
        versions = _versions(conn, session, uid)
        if {k:v for k,v in versions.items() if k != 'verified_account_version'} != review['versions']:
            raise ValueError('STALE_IDENTITY_PREVIEW')
    return VerifiedIdentity(session, uid, versions,
                            hashlib.sha256(cookies['sessionid'].encode()).hexdigest())


def apply(review, reason, *, db_path):
    from relttk.storage.ledger_requests import require_reason
    require_reason(reason)
    if not isinstance(review, VerifiedIdentity):
        raise ValueError('VERIFIED_SELF_REQUIRED')
    paths.contained(db_path)
    with ledger.RunLock(str(__import__('pathlib').Path(db_path).parent/'run.lock')):
        cookies = paths.read_private_json(paths.credential_path(review.session))
        if hashlib.sha256(cookies.get('sessionid', '').encode()).hexdigest() != review.generation:
            raise ValueError('STALE_CREDENTIAL_GENERATION')
        cb.bind_session(review.uid, review.session, db_path=db_path,
                        expected_versions=review.versions, reason=reason)
