"""H0B refusal/candidate regressions replacing H0A's permissive observations.

The original H0A evidence remains in its report, not an acceptance guarantee.
All response bodies, session strings and metadata below are synthetic.
"""
from contextlib import closing
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core import api
from core.self_identity import verify_authenticated_self
from relttk import config
from relttk.identity import identity_service
from relttk.identity.circuit_breaker import ProtocolFailure
from relttk.storage import ledger_migrations


def body(uid='111', *, logged_in=None, challenge=False):
    ctx = {'odinId': uid, 'user': {'uid': uid, 'secUid': 'synthetic'}}
    if logged_in is not None:
        ctx['isLogin'] = logged_in
    return ('<div>challenge</div>' if challenge else '') + \
        '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">' + \
        json.dumps({'__DEFAULT_SCOPE__': {'webapp.app-context': ctx}}) + '</script>'


class Response:
    def __init__(self, html, url='https://www.tiktok.com/messages', content_type='text/html', status=200):
        self.html = html
        self.url = url
        self.headers = {'Content-Type': content_type}
        self.status = status
        self.origin_checked = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.html.encode('utf-8')

    def geturl(self):
        self.origin_checked = True
        return self.url


class IdentityEvidenceTests(unittest.TestCase):
    # H0A observations are recorded in its report. H0B closes verified promotion.
    def test_matching_context_is_not_authenticated_authority(self):
        with self.assertRaisesRegex(ProtocolFailure, 'CONTRACT_UNVERIFIED'):
            verify_authenticated_self(body())

    def test_guest_candidate_does_not_verify(self):
        with self.assertRaises(ProtocolFailure): verify_authenticated_self(body(logged_in=False))

    def test_challenge_candidate_does_not_verify(self):
        with self.assertRaises(ProtocolFailure): verify_authenticated_self(body(challenge=True))

    def test_plain_guest_challenge_without_candidate_are_rejected(self):
        for html in ('guest', 'challenge', '{"odinId":"111"}'):
            with self.subTest(html=html), self.assertRaises(ProtocolFailure): verify_authenticated_self(html)

    def test_ascii_candidate_is_preserved_and_malformed_uid_is_rejected(self):
        from core.self_identity import extract_self_uid_candidate
        self.assertEqual(extract_self_uid_candidate(body('12345')), '12345')
        for uid in (' 111', '111 ', '1e2', '0', '-1', '', '01', '1'*21):
            with self.subTest(uid=uid), self.assertRaises(ProtocolFailure): extract_self_uid_candidate(body(uid))

    def test_non_ascii_candidate_refused(self):
        from core.self_identity import extract_self_uid_candidate
        with self.assertRaises(ProtocolFailure): extract_self_uid_candidate(body('\u0661'))

    def test_full_and_isolated_contexts_cannot_promote_candidate(self):
        self.refused({'sessionid':'synthetic', 'extra':'synthetic-extra'})

    def test_conflict_cannot_be_hidden_by_cached_identity(self):
        self.refused({'sessionid':'synthetic'})

    def test_no_response_origin_can_promote_unverified_contract(self):
        for response in [Response(body(), url='https://fixture.invalid/login', content_type='text/plain', status=403), Response(body())]:
            with patch.object(api.urllib.request, 'urlopen', return_value=response) as transport:
                with self.assertRaises(ProtocolFailure): api.get_own_user_id({'sessionid':'synthetic'},use_cache=False)
                transport.assert_not_called()

    def refused(self, cookies, code='CONTRACT_UNVERIFIED'):
        with patch.object(api.urllib.request,'urlopen') as transport, patch('builtins.open') as cache:
            with self.assertRaisesRegex(ProtocolFailure, code): api.get_own_user_id(cookies,use_cache=False)
            transport.assert_not_called(); cache.assert_not_called()

    def test_missing_session_before_transport(self): self.refused({}, 'AUTHENTICATED_SESSION_REQUIRED')
    def test_invalid_session_typed_protocol_refusal(self): self.refused({'sessionid':123}, 'AUTHENTICATED_SESSION_REQUIRED')
    def test_empty_explicit_cookie_does_not_fall_back_to_config(self):
        with patch.object(config,'COOKIES',{'sessionid':'synthetic-global'}): self.refused({},'AUTHENTICATED_SESSION_REQUIRED')


class IdentityCallerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.base.chmod(0o700)
        self.db = self.base / 'fixture.db'
        ledger_migrations.initialize(self.db)
        (self.base / 'sesion').mkdir(mode=0o700)
        self.session = self.base / 'sesion/fixture.json'
        self.save({'sessionid': 'synthetic'})
        env = patch.dict(os.environ, {'TIKTOK_RUNTIME_DIR': str(self.base)})
        env.start()
        self.addCleanup(env.stop)

    def save(self, value):
        self.session.write_text(json.dumps(value), encoding='utf-8')
        self.session.chmod(0o600)

    def test_identity_service_missing_session_stops_before_identity_transport(self):
        self.save({})
        with patch.object(api, 'get_own_user_id', side_effect=AssertionError('transport')):
            with self.assertRaisesRegex(ValueError, 'AUTHENTICATED_SESSION_REQUIRED'):
                identity_service.verify('fixture', db_path=self.db)
        with closing(identity_service.readiness.open_quiescent(self.db)) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM breaker_events').fetchone()[0], 0)

    def test_changed_session_generation_prevents_binding(self):
        with patch.object(api, 'get_own_user_id', return_value='111'):
            review = identity_service.verify('fixture', db_path=self.db)
        self.save({'sessionid': 'synthetic-changed'})
        with self.assertRaisesRegex(ValueError, 'STALE_CREDENTIAL_GENERATION'):
            identity_service.apply(review, 'fixture reason', db_path=self.db)
        with closing(identity_service.readiness.open_quiescent(self.db)) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM breaker_events').fetchone()[0], 0)
