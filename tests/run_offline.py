"""Reviewer runner: prohibit external networking and real runtime-data access."""
import contextlib
from contextvars import ContextVar
from functools import lru_cache
import io
import os
from pathlib import Path
import sys
import stat
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
protected = [ROOT / p for p in (
    'sesion', 'sessions', 'state', 'ws_auth.local.json', 'streak.local.json',
    '.uid_cache.json', 'work/tiktok-browser-profile', 'work/ws_auth.candidate.local.json',
    'work/tui-settings.local.json',
)]
if __name__ == '__main__':
    # Spawned test children inherit the original protected root, not a test's
    # temporary TIKTOK_RUNTIME_DIR override.
    os.environ['TIKTOK_REVIEW_PROTECTED_RUNTIME'] = os.environ.get('TIKTOK_RUNTIME_DIR', '')
protected_runtime = os.environ.get('TIKTOK_REVIEW_PROTECTED_RUNTIME', os.environ.get('TIKTOK_RUNTIME_DIR', ''))
if protected_runtime:
    protected.append(Path(protected_runtime).absolute())

# CPython's open audit event omits dir_fd. Keep the actual os.open call unchanged,
# supplying its descriptor-relative path to the hook only for that audited call.
_open_context = ContextVar('review_open_path', default=None)
_original_open = os.open


@lru_cache(maxsize=256)
def protected_path(path):
    return path.resolve()


def open_path(path, dir_fd=None):
    raw = os.fsdecode(path)
    if os.path.isabs(raw) or dir_fd is None:
        return Path(raw).absolute().resolve()
    if not stat.S_ISDIR(os.fstat(dir_fd).st_mode):
        raise RuntimeError('Review cannot resolve directory descriptor')
    try:
        base = os.readlink('/proc/self/fd/' + str(dir_fd))
    except OSError:
        raise RuntimeError('Review cannot resolve directory descriptor') from None
    if not os.path.isabs(base) or base.endswith(' (deleted)'):
        raise RuntimeError('Review cannot resolve directory descriptor')
    return (Path(base) / raw).resolve()


def guarded_open(path, flags, mode=0o777, *, dir_fd=None):
    resolved = open_path(path, dir_fd)
    token = _open_context.set((os.fsdecode(path), resolved))
    try:
        return _original_open(path, flags, mode, dir_fd=dir_fd)
    finally:
        _open_context.reset(token)


def guard(event, args):
    if event == 'socket.getaddrinfo':
        raise RuntimeError('Review blocked external DNS')
    if event == 'socket.connect' and args[1][0] not in ('127.0.0.1', '::1'):
        raise RuntimeError('Review blocked external connection')
    if event in ('open', 'sqlite3.connect') and isinstance(args[0], (str, bytes, os.PathLike)):
        raw = os.fsdecode(args[0])
        if raw.startswith('file:'):
            from urllib.parse import unquote, urlsplit
            raw = unquote(urlsplit(raw).path)
            if os.name == 'nt' and len(raw) > 2 and raw[0] == '/' and raw[2] == ':':
                raw = raw[1:]
        pending = _open_context.get()
        if (event == 'open' and args[1] is None and not os.path.isabs(raw)
                and (pending is None or raw != pending[0])):
            # Cached/C-level low-level opens do not expose dir_fd in the event.
            # Refuse ambiguous relative paths rather than assuming the cwd.
            raise RuntimeError('Review cannot resolve low-level relative open')
        path = (pending[1] if event == 'open' and pending is not None
                and raw == pending[0]
                else Path(raw).absolute().resolve())
        lexical = (pending[1] if event == 'open' and pending is not None
                   and raw == pending[0] else Path(raw).absolute())
        if any(lexical == p or p in lexical.parents or path == protected_path(p)
               or protected_path(p) in path.parents for p in protected):
            raise RuntimeError('Review blocked real runtime data')

os.open = guarded_open
sys.addaudithook(guard)
from relttk.compat import enable
enable()
if __name__ == '__main__':
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    print('Offline guard: external network and real runtime files blocked.')
    raise SystemExit(not result.wasSuccessful())
