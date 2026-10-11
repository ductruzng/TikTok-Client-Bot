"""Explicit runtime paths and non-mutating private reads (stdlib only)."""
import json
import os
from pathlib import Path
import re
import stat

REPO = Path(__file__).resolve().parent


class UnsafeRuntime(ValueError):
    pass


def inspect_path(path, *, private=False, must_exist=True):
    path = Path(path)
    if not path.is_absolute():
        raise UnsafeRuntime('ABSOLUTE_PATH_REQUIRED')
    if '..' in path.parts:
        raise UnsafeRuntime('PATH_TRAVERSAL')
    for part in reversed((path, *path.parents)):
        if part.is_symlink():
            raise UnsafeRuntime('SYMLINK_PATH')
        if part.exists() and os.name == 'posix':
            info = part.stat()
            if info.st_uid not in (0, os.getuid()):
                raise UnsafeRuntime('UNSAFE_OWNER')
            if info.st_mode & 0o022 and not (part != path and stat.S_ISDIR(info.st_mode)
                    and info.st_uid == 0 and info.st_mode & stat.S_ISVTX):
                raise UnsafeRuntime('UNSAFE_PARENT_PERMISSIONS')
    if must_exist and not path.exists():
        raise UnsafeRuntime('PATH_MISSING')
    if private and path.exists() and os.name == 'posix':
        info = path.stat()
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise UnsafeRuntime('PRIVATE_PERMISSIONS_REQUIRED')
    return path


def root(explicit=None):
    value = explicit if explicit is not None else os.environ.get('TIKTOK_RUNTIME_DIR')
    if value is None:
        return None
    if not value:
        raise UnsafeRuntime('RUNTIME_ROOT_EMPTY')
    path = inspect_path(value, private=True)
    if not path.is_dir():
        raise UnsafeRuntime('RUNTIME_ROOT_NOT_DIRECTORY')
    return path


def contained(path, base=None, *, must_exist=True, private=False):
    base = base or root()
    if base is None:
        return Path(path)
    path = inspect_path(path, private=private, must_exist=must_exist)
    if path != base and base not in path.parents:
        raise UnsafeRuntime('OUTSIDE_RUNTIME_ROOT')
    return path


def session_dir(legacy=None):
    base = root()
    return contained(base/'sesion', base, must_exist=False, private=True) if base else Path(legacy or REPO/'sesion')


def credential_path(session, *, auth=False, base=None):
    if not isinstance(session, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', session) or '..' in session or session == '.':
        raise UnsafeRuntime('SESSION_NAME_INVALID')
    directory = base/'sesion' if base else session_dir()
    return inspect_path(directory/('ws-auth' if auth else '')/(session+'.json'), private=True)


def read_private_json(path):
    path = inspect_path(path, private=True)
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'r', encoding='utf-8-sig') as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise UnsafeRuntime('CREDENTIAL_FORMAT')
    return value
