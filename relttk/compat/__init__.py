"""Explicit standard-library compatibility for reviewed legacy import names."""
from pathlib import Path
import sys

TARGETS = {'config': 'relttk.config', 'log': 'relttk.log',
           'runtime_paths': 'relttk.runtime_paths',
           'cli': 'relttk.application.cli', 'services': 'relttk.application.services',
           'tiktok_tui': 'relttk.application.tui',
           'client': 'relttk.transport.client', 'oneshot': 'relttk.transport.oneshot',
           'qrlogin': 'relttk.transport.qrlogin',
           'ws_auth_capture': 'relttk.transport.ws_auth_capture',
           'ledger': 'relttk.storage.ledger',
           'ledger_requests': 'relttk.storage.ledger_requests',
           'ledger_migrations': 'relttk.storage.ledger_migrations',
           'queue_service': 'relttk.storage.queue_service',
           'worker': 'relttk.runtime.worker',
           'scheduling': 'relttk.runtime.scheduling',
           'rotation': 'relttk.runtime.rotation',
           'unknown_resolution': 'relttk.runtime.unknown_resolution',
           'circuit_breaker': 'relttk.identity.circuit_breaker',
           'identity_service': 'relttk.identity.identity_service',
           'readiness': 'relttk.identity.readiness',
           'operations': 'relttk.operations'}


def enable():
    for name, target in TARGETS.items():
        old = sys.modules.get(name)
        if old is not None and old is not sys.modules.get(target):
            raise RuntimeError('LEGACY_IMPORT_CONFLICT')
    directory = Path(__file__).resolve().parent / 'legacy'
    if directory.is_symlink() or not directory.is_dir():
        raise RuntimeError('LEGACY_IMPORT_DIRECTORY_INVALID')
    path = str(directory)
    if path not in sys.path:
        sys.path.insert(0, path)
