import json
import unittest

from core.self_identity import (
    extract_self_uid_candidate,
    verify_authenticated_self,
)
from relttk.identity.circuit_breaker import ProtocolFailure


def make_html(uid, *, path_valid=True):
    scope = (
        {"webapp.app-context": {
            "odinId": uid,
            "user": {
                "uid": uid,
                "secUid": "TEST_SEC_UID"
            }
        }}
        if path_valid
        else {"other-context": {"odinId": uid}}
    )
    payload = json.dumps({"__DEFAULT_SCOPE__": scope})
    return (
        '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">'
        + payload
        + '</script>'
    )


class SelfIdentityParserTests(unittest.TestCase):

    def test_valid_uid(self):
        self.assertEqual(
            extract_self_uid_candidate(make_html("123456789")),
            "123456789",
        )

    def test_invalid_uid(self):
        for uid in ("", "0", -1, 123456789, None):
            with self.subTest(uid=uid):
                with self.assertRaises(ProtocolFailure):
                    extract_self_uid_candidate(make_html(uid))

    def test_missing_script(self):
        with self.assertRaises(ProtocolFailure):
            extract_self_uid_candidate("<html></html>")

    def test_wrong_json_path(self):
        with self.assertRaises(ProtocolFailure):
            extract_self_uid_candidate(
                make_html("123456789", path_valid=False)
            )

    def test_duplicate_scripts(self):
        content = make_html("123456789")
        with self.assertRaises(ProtocolFailure):
            extract_self_uid_candidate(content + content)

    def test_consistent_candidate_is_not_verified_identity(self):
        with self.assertRaisesRegex(ProtocolFailure, 'CONTRACT_UNVERIFIED'):
            verify_authenticated_self(make_html("123456789"))


if __name__ == "__main__":
    unittest.main()

class SelfIdentityMismatchTests(unittest.TestCase):

    def test_uid_mismatch(self):
        html = make_html("123456789")
        html = html.replace(
            '"uid": "123456789"',
            '"uid": "987654321"'
        )
        with self.assertRaises(ProtocolFailure):
            extract_self_uid_candidate(html)

    def test_missing_secuid(self):
        html = make_html("123456789")
        html = html.replace(
            '"secUid": "TEST_SEC_UID"',
            '"secUid": ""'
        )
        with self.assertRaises(ProtocolFailure):
            extract_self_uid_candidate(html)
