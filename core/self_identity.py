"""Shared fail-closed authenticated-self evidence boundary.

The repository contains no authenticated-self response fixture with established
provenance. A generic odinId anywhere in HTML cannot establish the logged-in
account. Do not add an acceptance rule without separately reviewed evidence.
"""
import json
import re
from html import unescape
from relttk.identity.circuit_breaker import ProtocolFailure


def verify_authenticated_self(html):
    # Deliberately no guessed HTML schema, manually supplied UID or config bypass.
    raise ProtocolFailure('AUTHENTICATED_SELF_CONTRACT_UNVERIFIED')

def extract_self_uid_candidate(html: str) -> str:
    matches = re.findall(
        r'<script\b[^>]*\bid=["\']__UNIVERSAL_DATA_FOR_REHYDRATION__["\'][^>]*>(.*?)</script\s*>',
        html,
        re.IGNORECASE | re.DOTALL,
    )

    if len(matches) != 1:
        raise ProtocolFailure("SELF_DATA_SCRIPT_INVALID")

    try:
        data = json.loads(unescape(matches[0]))
        uid = data["__DEFAULT_SCOPE__"]["webapp.app-context"]["odinId"]
    except (ValueError, TypeError, KeyError):
        raise ProtocolFailure("SELF_DATA_INVALID") from None

    if (
        not isinstance(uid, str)
        or not uid.isdecimal()
        or int(uid) <= 0
    ):
        raise ProtocolFailure("SELF_UID_INVALID")

    return uid