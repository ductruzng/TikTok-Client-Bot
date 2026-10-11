"""Render review artifacts only. Never installs units or changes grant authority."""
import argparse
from pathlib import Path, PurePosixPath
import os
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def posix_path(value):
    if not isinstance(value, str) or not re.fullmatch(r'/[A-Za-z0-9_./-]+', value):
        raise ValueError('Unsafe deployment path')
    if '..' in value.split('/') or '.' in value.split('/') or '//' in value or value.endswith('/'):
        raise ValueError('Unsafe deployment path')
    return value


def workload(consent):
    """One/two-recipient profile; bounded inbox child and WS deadlines.

    Host startup/termination overhead still requires native Debian validation.
    """
    targets = consent.get('policy', {}).get('targets')
    if not isinstance(targets, list) or len(targets) not in (1, 2) or consent.get('daily_budget') != len(targets):
        raise ValueError('UNSUPPORTED_WORKLOAD')
    wait = consent.get('max_wait')
    if type(wait) is not int or not 0 <= wait <= 300:
        raise ValueError('UNSUPPORTED_WORKLOAD')
    minutes = consent.get('window_minutes')
    minimum = 10 if len(targets) == 1 else 15
    if type(minutes) is not int or minutes < minimum:
        raise ValueError('UNSUPPORTED_WORKLOAD')
    clock = consent.get('time', '')
    if not isinstance(clock, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', clock):
        raise ValueError('UNSUPPORTED_WORKLOAD')
    hour, minute = map(int, clock.split(':'))
    if 1440-hour*60-minute < minimum:
        raise ValueError('UNSUPPORTED_WORKLOAD')
    if len(targets) == 2:
        interval = consent['policy'].get('min_send_interval_seconds', 60)
        window_limit = consent['policy'].get('max_sends_per_window', 5)
        if type(interval) is not int or not 0 <= interval <= wait or type(window_limit) is not int or window_limit < 2:
            raise ValueError('UNSUPPORTED_WORKLOAD')
        return dict(recipients=2, startup_seconds=900, stop_seconds=90,
                    profile_seconds=wait+2*120+90, host_verified=False)
    # Internal wait + conservative setup allowance + one echo + stop grace.
    return dict(recipients=1, startup_seconds=600, stop_seconds=90,
                profile_seconds=wait+120+30+90, host_verified=False)


def unit_text(consent, *, grant_id, fingerprint, python, entry, runtime, db):
    if not isinstance(grant_id, str) or not re.fullmatch(r'[0-9a-f]{32}', grant_id):
        raise ValueError('Unsafe grant selector')
    if not isinstance(fingerprint, str) or not re.fullmatch(r'[0-9a-f]{64}', fingerprint):
        raise ValueError('Unsafe grant fingerprint')
    for value in (python, entry, runtime, db):
        posix_path(value)
    if PurePosixPath(runtime) not in PurePosixPath(db).parents:
        raise ValueError('Database outside runtime')
    profile = workload(consent)
    substitutions = dict(PYTHON=python, ENTRY=entry, RUNTIME=runtime, DB=db,
                         GRANT_ID=grant_id, FINGERPRINT=fingerprint, WORKDIR=str(PurePosixPath(entry).parent))
    result = {}
    for kind in ('service', 'timer'):
        text = (Path(__file__).parent/'systemd'/('relttk.'+kind+'.in')).read_text(encoding='utf-8')
        for name, value in substitutions.items():
            text = text.replace('@'+name+'@', value)
        if kind == 'service':
            text = text.replace('TimeoutStartSec=600', 'TimeoutStartSec='+str(profile['startup_seconds']))
        if '@' in text or '%' in text or '$' in text:
            raise ValueError('Unresolved or unsafe unit expansion')
        result['relttk-'+grant_id+'.'+kind] = text
    return result


def render(*, db, grant_id, fingerprint, python, entry, runtime, output):
    if os.name != 'posix':
        raise ValueError('Actual renderer requires POSIX; Windows unit_text tests are simulations')
    from relttk import runtime_paths as paths
    from relttk.runtime import scheduling
    base = paths.root(runtime)
    if paths.root() != base:
        raise ValueError('Explicit TIKTOK_RUNTIME_DIR required')
    paths.contained(db, base, private=True)
    for value in (python, entry):
        posix_path(value)
        if not paths.inspect_path(value).is_file():
            raise ValueError('Missing release file')
    if not os.access(python, os.X_OK) or not entry.endswith('/operational_entry.py'):
        raise ValueError('Reviewed operational bootstrap required')
    with scheduling.readonly(db) as conn:
        consent, actual, event = scheduling._load(conn, grant_id)
        if actual != fingerprint or event['event_type'] not in ('AUTHORIZED', 'ACTIVATED'):
            raise ValueError('Grant selector/state mismatch')
        from relttk.storage import ledger_requests
        if consent['end_ms'] <= ledger_requests.utc_now_ms():
            raise ValueError('Expired grant')
        scheduling._check_config(conn, grant_id, consent)
        paths.contained(consent['policy_reference'], base, private=True)
        units = unit_text(consent, grant_id=grant_id, fingerprint=fingerprint,
                          python=python, entry=entry, runtime=runtime, db=db)
    directory = paths.inspect_path(output, private=True)
    if not directory.is_dir():
        raise ValueError('Existing private output directory required')
    # Check every collision before writing; still O_EXCL at each creation.
    if any((directory/name).exists() for name in units):
        raise ValueError('Output must be new')
    for name, text in units.items():
        with os.fdopen(os.open(directory/name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(text)
    return tuple(units)


def main():
    parser = argparse.ArgumentParser(description='Offline unit artifacts only; no installation or activation')
    for name in ('db','grant-id','fingerprint','python','entry','runtime','output'):
        parser.add_argument('--'+name, required=True)
    args = vars(parser.parse_args())
    try:
        render(**args)
        print('ARTIFACTS_RENDERED; identity BLOCKED; not installed or activated')
        return 0
    except Exception:
        print('RENDER_REFUSED; verify paths, selector and supported one/two-recipient workload')
        return 3


if __name__ == '__main__':
    sys.exit(main())
