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
    # A matching candidate (even in two cookie contexts) is not an authority.
    # No reviewed authenticated-self protocol evidence is available in source.
    raise ProtocolFailure("AUTHENTICATED_SELF_CONTRACT_UNVERIFIED")

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
        context = data["__DEFAULT_SCOPE__"]["webapp.app-context"]
        uid = context["odinId"]
        user = context["user"]

        if not isinstance(user, dict):
            raise ProtocolFailure("SELF_USER_INVALID")

        user_uid = user.get("uid")
        sec_uid = user.get("secUid")

        if (
            not isinstance(user_uid, str)
            or user_uid != uid
            or not isinstance(sec_uid, str)
            or not sec_uid.strip()
        ):
            raise ProtocolFailure("SELF_IDENTITY_MISMATCH")
    except (ValueError, TypeError, KeyError):
        raise ProtocolFailure("SELF_DATA_INVALID") from None

    if (
        not isinstance(uid, str)
        or not re.fullmatch(r"[1-9][0-9]{0,19}", uid)
        or int(uid) <= 0
    ):
        raise ProtocolFailure("SELF_UID_INVALID")

    return uid
