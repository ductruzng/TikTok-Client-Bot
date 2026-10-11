"""Read-only source enumeration and implementation checks for offline reviews."""
import ast
import inspect
import os
from pathlib import Path
import re

SOURCE_ROOTS = ('core', 'signers', 'plugins', 'deploy', 'tests', 'relttk', 'tools')
PRIVATE_DIRS = frozenset(('sesion', 'sessions', 'state', 'work', '.git', '.venv',
                         'venv', '__pycache__', 'browser-profile', 'browser-profiles'))


def source_paths(root):
    root = Path(root).resolve()
    paths = list(root.glob('*.py'))
    for name in SOURCE_ROOTS:
        directory = root / name
        if directory.is_symlink():
            raise AssertionError('Source root must not be a symlink')
        if not directory.exists():
            continue
        for base, dirs, files in os.walk(directory, followlinks=False):
            dirs[:] = [d for d in dirs if d not in PRIVATE_DIRS and
                       not (Path(base) / d).is_symlink()]
            paths.extend(Path(base) / f for f in files if f.endswith('.py'))
    if any(p.is_symlink() for p in paths):
        raise AssertionError('Source file must not be a symlink')
    return sorted(set(paths))


def assert_ws_sources(case, paths):
    # Keep every original WS AST assertion, including URL literals in tests.
    for path in paths:
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            names = []
            value = None
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                names = [t.id for t in targets if isinstance(t, ast.Name)]
                value = node.value
            if any(n.upper() == 'WS_ACCESS_KEY' for n in names):
                case.fail(f'Forbidden WS default assignment: {path.name}:{node.lineno}')
            if path.parent.name != 'tests' and any(n.lower() == 'access_key' for n in names) and isinstance(value, ast.Constant):
                case.assertFalse(bool(value.value), f'Embedded key: {path.name}:{node.lineno}')
            if path.parent.name != 'tests' and isinstance(node, ast.Dict):
                for k, v in zip(node.keys, node.values):
                    if isinstance(k, ast.Constant) and k.value == 'access_key' and isinstance(v, ast.Constant):
                        case.assertFalse(bool(v.value), f'Embedded key: {path.name}:{node.lineno}')
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                case.assertIsNone(re.search(r'access_key=[0-9a-fA-F]{32}(?:&|$)', node.value),
                                  f'Embedded URL key: {path.name}:{node.lineno}')


def client_implementation(root, module):
    """Require the actual class source at the current or future canonical path."""
    root = Path(root).resolve()
    future = root / 'relttk' / 'transport' / 'client.py'
    expected = future if (root / 'relttk' / 'transport').exists() else root / 'client.py'
    actual = Path(inspect.getsourcefile(module.LttkClient)).resolve()
    if actual != expected or Path(module.__file__).resolve() != expected:
        raise AssertionError('Client inspection does not reach canonical implementation')
    if not expected.is_file() or expected.is_symlink():
        raise AssertionError('Canonical client source unavailable')
    if expected not in source_paths(root):
        raise AssertionError('Canonical client excluded from scanner')
    return expected
