"""Shared fail-closed authenticated-self evidence boundary.

The repository contains no authenticated-self response fixture with established
provenance. A generic odinId anywhere in HTML cannot establish the logged-in
account. Do not add an acceptance rule without separately reviewed evidence.
"""
from circuit_breaker import ProtocolFailure


def verify_authenticated_self(html):
    # Deliberately no guessed HTML schema, manually supplied UID or config bypass.
    raise ProtocolFailure('AUTHENTICATED_SELF_CONTRACT_UNVERIFIED')
