import json
import unittest
from unittest.mock import patch

from core import api
from relttk.identity.circuit_breaker import ProtocolFailure


def response(uid):
    data = {
        "__DEFAULT_SCOPE__": {
            "webapp.app-context": {
                "odinId": uid,
                "user": {
                    "uid": uid,
                    "secUid": "synthetic-secuid",
                },
            }
        }
    }
    html = (
        '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">'
        + json.dumps(data)
        + '</script>'
    )

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return html.encode("utf-8")

    return FakeResponse()


class CookieConsistencyTests(unittest.TestCase):
    def test_matching_responses(self):
        with patch.object(
            api.urllib.request,
            "urlopen",
            side_effect=[response("111"), response("111")],
        ) as request:
            with self.assertRaisesRegex(ProtocolFailure, 'CONTRACT_UNVERIFIED'):
                api.get_own_user_id({"sessionid": "synthetic"}, use_cache=False)
        request.assert_not_called()

    def test_conflicting_responses(self):
        with patch.object(
            api.urllib.request,
            "urlopen",
            side_effect=[response("111"), response("222")],
        ):
            with self.assertRaises(ProtocolFailure):
                api.get_own_user_id(
                    {"sessionid": "synthetic"},
                    use_cache=False,
                )


if __name__ == "__main__":
    unittest.main()
