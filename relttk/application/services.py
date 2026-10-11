"""Safe, testable service layer for TikTok Streak Manager TUI v0.2.

Network access occurs only through explicit fetch_inbox() or send_plan() calls.
Importing this module performs no network or runtime-data access.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from relttk.runtime_paths import REPO

ROOT = REPO
_RUNTIME_BASE = Path(os.environ.get('TIKTOK_RUNTIME_DIR', str(ROOT)))
CONFIG_PATH = _RUNTIME_BASE / "streak.local.json"
PREFS_PATH = _RUNTIME_BASE / "work" / "tui-settings.local.json"
SESSION_DIR = ROOT / "sesion"  # spelling used by the upstream project
SESSION_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+$")
TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def runtime_preflight(runtime_dir, db_path, config_path, *, check_credentials=False):
    from relttk.identity.readiness import report
    return report(runtime_dir, db_path, config_path, check_credentials=check_credentials)


def identity_preview(session, *, db_path):
    from relttk.identity.identity_service import preview
    return preview(session, db_path=db_path)


def schedule_preview(config_path, schedule_id, *, db_path, **bounds):
    from relttk.runtime.scheduling import preview
    return preview(config_path, schedule_id, db_path=db_path, **bounds)


def schedule_authorize(review, reason, *, db_path):
    from relttk.runtime.scheduling import authorize
    return authorize(review, reason, db_path=db_path)


def schedule_status(grant_id, *, db_path):
    from relttk.runtime import scheduling
    result = scheduling.status(grant_id, db_path=db_path)
    with scheduling.readonly(db_path) as conn:
        uid = result['consent']['uid']
        cfg = result['consent']['policy']
        from relttk.storage import ledger, ledger_requests as requests, queue_service as queue
        result['recipients'] = []
        for target in result['consent']['policy']['targets']:
            rows = [dict(row) for row in conn.execute(
                'SELECT request_id,status,transmitted,date,reason_code,server_msg_id FROM send_requests WHERE canonical_uid=? AND conv_id=? ORDER BY rowid DESC LIMIT 50',
                (uid, target['conv_id']))]
            admission = []
            for pending in conn.execute("SELECT * FROM send_requests WHERE canonical_uid=? AND conv_id=? AND status='queued' ORDER BY rowid", (uid, target['conv_id'])):
                try:
                    queue.check_fifo(conn, pending)
                    requests.check_admission(conn, pending, requests.settings_from_config(cfg), rotation_config=cfg,
                        session_name=cfg['session'], policy_reference=result['consent']['policy_reference'], policy_config=cfg)
                except ledger.LedgerError as exc:
                    admission.append(exc.result() if hasattr(exc, 'result') else {'request_id':pending['request_id'], 'reason':getattr(exc,'code',type(exc).__name__)})
            result['recipients'].append({'target': target, 'requests': rows, 'admission_holds':admission,
                'success_definition': 'Correlated server echo; receipt/read/streak unverified'})
    return result


def schedule_list(session, *, db_path):
    """Explicit read-only UI action; no database creation or credential access."""
    from relttk.runtime import scheduling
    with scheduling.readonly(db_path) as conn:
        return [scheduling._state(conn, row['grant_id']) for row in
                conn.execute('SELECT grant_id FROM recurring_grants ORDER BY created_at_ms')
                if scheduling._load(conn, row['grant_id'])[0]['session'] == session]


def schedule_action_challenge(action, review):
    if action == 'AUTHORIZE':
        return 'AUTHORIZE ' + review['fingerprint']
    if action not in ('ACTIVATED', 'PAUSED', 'REVOKED'):
        raise ValueError('UNSUPPORTED_SCHEDULE_ACTION')
    verb = {'ACTIVATED': 'ACTIVATE', 'PAUSED': 'PAUSE', 'REVOKED': 'REVOKE'}[action]
    return f"{verb} {review['grant_id']} {review['fingerprint']} {review['event']['version']}"


def schedule_confirm(action, review, reason, challenge, *, db_path):
    if challenge != schedule_action_challenge(action, review):
        raise ValueError('CONFIRMATION_MISMATCH')
    if action == 'AUTHORIZE':
        return schedule_authorize(review, reason, db_path=db_path)
    return schedule_change(review['grant_id'], review, action, reason, db_path=db_path)


def schedule_change(grant_id, preview, action, reason, *, db_path):
    from relttk.runtime.scheduling import change
    return change(grant_id, preview, action, reason, db_path=db_path)


async def schedule_tick(grant_id, fingerprint=None, *, db_path, **options):
    from relttk.runtime.scheduling import tick
    return await tick(grant_id, fingerprint, db_path=db_path, **options)


def identity_verify(session, *, db_path):
    from relttk.identity.identity_service import verify
    return verify(session, db_path=db_path)


def identity_apply(review, reason, *, db_path):
    from relttk.identity.identity_service import apply
    return apply(review, reason, db_path=db_path)


@dataclass(frozen=True)
class Conversation:
    conv_id: str
    conv_short_id: int
    conv_type: int
    name: str

    def target(self) -> dict[str, Any]:
        return {
            "conv_id": self.conv_id,
            "conv_short_id": self.conv_short_id,
            "conv_type": self.conv_type,
        }


def valid_session_name(name: str) -> bool:
    return bool(
        isinstance(name, str)
        and name
        and name not in (".", "..")
        and ".." not in name
        and SESSION_PATTERN.fullmatch(name)
    )


def list_sessions(directory: Path = None) -> list[str]:
    from relttk.runtime_paths import session_dir, contained
    directory = contained(directory) if directory is not None else session_dir(SESSION_DIR)
    if not directory.is_dir():
        return []
    return sorted(
        (p.stem for p in directory.glob("*.json")
         if p.is_file() and not p.is_symlink() and p.suffix.lower() == ".json"
         and valid_session_name(p.stem)),
        key=str.casefold,
    )


def read_json_object(path: Path) -> dict[str, Any]:
    from relttk.runtime_paths import contained
    contained(path, must_exist=False, private=True)
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    """Do not corrupt the existing JSON on an interrupted write."""
    from relttk.runtime_paths import contained
    contained(path, must_exist=False, private=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".tui-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.chmod(temp_name, 0o600)
        except OSError:
            pass
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def parse_inbox(raw: object) -> list[Conversation]:
    """Normalize ONLY IDs confirmed by the server response; never synthesize IDs."""
    if not isinstance(raw, list):
        raise ValueError("Unexpected inbox response type")
    output: list[Conversation] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        conv_id = item.get("conv_id")
        short = item.get("conv_short_id")
        typ = item.get("conv_type")
        if not isinstance(conv_id, str) or not conv_id.strip():
            continue
        conv_id = conv_id.strip()
        if isinstance(short, bool) or isinstance(typ, bool):
            continue
        try:
            if isinstance(short, float) or isinstance(typ, float):
                continue
            short_id = int(short)
            conv_type = int(typ)
        except (ValueError, TypeError):
            continue
        if not 0 < short_id <= 0xFFFFFFFFFFFFFFFF or conv_type not in (1, 2):
            continue
        if conv_id in seen:
            continue
        seen.add(conv_id)
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            name = "(Chưa có tên)"
        name = " ".join(name.split())[:100]
        output.append(Conversation(conv_id, short_id, conv_type, name))
    return output


def fetch_inbox(session_name: str) -> list[Conversation]:
    """Live read-only TikTok inbox call. Invoke from a background worker only."""
    if not valid_session_name(session_name) or session_name not in list_sessions():
        raise ValueError("Choose an existing saved session")

    from relttk.transport import qrlogin
    from relttk import config
    import core.api as api

    cookies = qrlogin.load_session(session_name)
    if not isinstance(cookies, dict) or not cookies.get("sessionid"):
        raise ValueError("Session is missing sessionid; log in again")
    from relttk.transport.bounded_inbox import fetch
    response = fetch(cookies, config.DEVICE_ID)
    return parse_inbox(response)


def matching_selected_ids(
    previous_targets: object,
    conversations: list[Conversation],
) -> set[str]:
    """Restore selection only if ID + short ID + type all match."""
    if not isinstance(previous_targets, list):
        return set()
    old = set()
    for item in previous_targets:
        if not isinstance(item, dict):
            continue
        try:
            old.add((item["conv_id"], int(item["conv_short_id"]), int(item["conv_type"])))
        except (KeyError, ValueError, TypeError):
            continue
    return {
        c.conv_id for c in conversations
        if (c.conv_id, c.conv_short_id, c.conv_type) in old
    }


def save_plan(
    session: str,
    message: str,
    recipients: list[Conversation],
    path: Path = CONFIG_PATH,
    *, allow_repeat_same_day: bool | None = None,
) -> dict[str, Any]:
    if not valid_session_name(session):
        raise ValueError("Invalid session name")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("Message must not be empty")
    if not recipients:
        raise ValueError("Select at least one conversation")
    if len({c.conv_id for c in recipients}) != len(recipients):
        raise ValueError("Duplicate conversation detected")
    current = read_json_object(path)
    if 'rotation' in current:
        raise ValueError('Rotation plan is managed through CLI/config; TUI cannot overwrite templates')
    current.update({
        "session": session,
        "message": message,
        "targets": [c.target() for c in recipients],
    })
    if allow_repeat_same_day is not None:
        current["allow_repeat_same_day"] = allow_repeat_same_day
    from relttk.storage.ledger_requests import DEFAULT_SETTINGS
    for name, default in DEFAULT_SETTINGS.items():
        current.setdefault(name, default)
    from main import validate_config
    valid, errors, _ = validate_config(current)
    if not valid:
        raise ValueError(f"Config validation failed ({len(errors)} issue(s))")
    atomic_write_json(path, current)
    return current


def save_preferences(
    send_time: str,
    enabled: bool,
    path: Path = PREFS_PATH,
    skip_if_sent: bool = True,
) -> dict[str, Any]:
    if not TIME_PATTERN.fullmatch(send_time):
        raise ValueError("Time must be HH:MM (24-hour format)")
    data = {
        "time": send_time,
        "enabled": bool(enabled),
        "skip_if_sent": bool(skip_if_sent),
        "timezone": "Asia/Ho_Chi_Minh",
    }
    atomic_write_json(path, data)
    return data


def scheduled_run_key(prefs: dict, now, last_run: str) -> str | None:
    """One in-memory trigger per scheduled day; the durable ledger guards restarts."""
    from zoneinfo import ZoneInfo
    local = now.astimezone(ZoneInfo("Asia/Ho_Chi_Minh"))
    if prefs.get("enabled") is not True or local.strftime("%H:%M") != prefs.get("time"):
        return None
    key = local.strftime("%Y-%m-%d %H:%M")
    return key if key != last_run else None


def summarize_results(result: dict) -> tuple[int, int, int]:
    rows = result.get("results", [])
    if not rows:
        raise ValueError("No send results returned")
    confirmed = sum(r.get("status") == "confirmed" for r in rows)
    skipped = sum(r.get("status") == "skipped" for r in rows)
    return confirmed, skipped, len(rows) - confirmed - skipped


def send_result_completed(row: dict) -> bool:
    """A skipped operation is complete only when its durable request is confirmed."""
    return row.get('status') == 'confirmed' or (
        row.get('status') == 'skipped' and row.get('existing_status') == 'confirmed')


def save_fixed_message(message: str, path=CONFIG_PATH):
    from relttk.runtime import rotation
    from relttk.storage.ledger_requests import settings_from_config
    cfg = read_json_object(Path(path))
    if 'rotation' in cfg:
        raise ValueError('Plan uses rotation; edit rotation.templates in the configuration instead')
    cfg['message'] = message
    rotation.catalog(cfg)
    settings_from_config(cfg)
    atomic_write_json(Path(path), cfg)
    return cfg


async def send_plan(config_path=CONFIG_PATH, *, idempotency_key=None, **options):
    """Shared CLI/TUI send entry. Repeat policy comes from the plan, never deletion."""
    from relttk.transport.oneshot import run_oneshot_send
    return await run_oneshot_send(config_path=str(config_path), idempotency_key=idempotency_key, **options)


def request_preview(request_id, *, db_path, config_path=None):
    from relttk.storage import ledger
    from relttk.storage import ledger_requests as requests
    ledger.check_ready(db_path)
    row = requests.get_request(request_id, db_path=db_path)
    preview = {'request': row, 'payload': json.loads(row['payload_json'])}
    if row['campaign_id'] is not None and config_path:
        from relttk.runtime import rotation
        cfg = read_json_object(Path(config_path))
        preview['review'] = requests.snapshot_review(row, cfg)
        preview['current_catalog'] = rotation.catalog(cfg)
        preview['configuration_changed'] = (preview['review']['config_fingerprint'] !=
                                            json.loads(row['snapshot_json'])['fingerprint'])
    return preview


def cancel_request(request_id, reason, *, db_path):
    from relttk.storage.ledger_requests import cancel_request as cancel
    return cancel(request_id, reason, db_path=db_path)


def approve_request_snapshot(request_id, preview, reason, *, db_path, config_path):
    from relttk.storage.ledger_requests import approve_snapshot
    return approve_snapshot(request_id, read_json_object(Path(config_path)), preview['review'], reason, db_path=db_path)


def rotation_skip_preview(scope, *, db_path):
    from relttk.storage.ledger_requests import preview_skip
    return preview_skip(scope, db_path=db_path)


def rotation_skip(scope, preview, reason, *, db_path):
    from relttk.storage.ledger_requests import skip_selection
    return skip_selection(scope, preview, reason, db_path=db_path)


def save_send_settings(allow_repeat_same_day, max_sends_per_conversation_per_day, path=CONFIG_PATH, **limits):
    from relttk.storage.ledger_requests import settings_from_config, DEFAULT_SETTINGS
    if set(limits) - DEFAULT_SETTINGS.keys():
        raise ValueError("Unknown rate-limit setting")
    cfg = read_json_object(path)
    cfg.update(allow_repeat_same_day=allow_repeat_same_day,
               max_sends_per_conversation_per_day=max_sends_per_conversation_per_day, **limits)
    cfg.update(settings_from_config(cfg))
    atomic_write_json(path, cfg)
    return cfg


def breaker_status(*, db_path, account=None, session=None, history=False):
    from relttk.identity import circuit_breaker
    return circuit_breaker.inspect(db_path=db_path, uid=account, session=session, history=history)


def breaker_reset(scope_type, scope_key, preview, reason, *, db_path):
    from relttk.identity import circuit_breaker
    return circuit_breaker.reset(scope_type, scope_key, preview, reason, db_path=db_path)


def queue_enqueue(config_path, key, *, db_path, apply=False):
    from relttk.storage import queue_service
    cfg = queue_service.read_policy(config_path)
    uid = queue_service.verified_uid(cfg['session'], db_path=db_path)
    if not apply:
        return {'preview_only': True, 'account': uid, 'session': cfg['session'], 'config': cfg,
                'warning': 'Template selection is committed only on explicit enqueue; no message sent'}
    return queue_service.enqueue(cfg, config_path, key, db_path=db_path)


def queue_list(*, db_path, session=None):
    from relttk.storage.queue_service import list_queue
    return list_queue(db_path=db_path, session=session)


def queue_run_preview(*, db_path, session):
    from relttk.storage.queue_service import preview_run
    return preview_run(db_path=db_path, session=session)


async def queue_run_once(*, db_path, session, max_jobs=1, confirm_request=None):
    from relttk.storage.queue_service import run_once
    return await run_once(db_path=db_path, session=session, max_jobs=max_jobs, confirm_request=confirm_request)


def queue_bind_preview(request_id, config_path, *, db_path):
    from relttk.storage import queue_service
    return queue_service.preview_bind(request_id, queue_service.read_policy(config_path), config_path, db_path=db_path)


def queue_bind(request_id, config_path, preview, reason, *, db_path):
    from relttk.storage import queue_service
    return queue_service.bind_request(request_id, queue_service.read_policy(config_path), config_path, preview, reason, db_path=db_path)


def unknown_preview(request_id, *, db_path):
    from relttk.runtime.unknown_resolution import preview
    result = preview(request_id, db_path=db_path)
    route = result['route']
    if route['policy_reference']:
        from relttk.storage import queue_service
        from relttk.storage.ledger_requests import settings_from_config
        try:
            cfg = queue_service.read_policy(route['policy_reference'])
            result['current_settings'] = settings_from_config(cfg)
            result['quota_warning'] = 'UNKNOWN retains its transmission quota; repeat/limits/cooldown/circuits can hold any replacement'
        except (OSError, ValueError):
            result['policy_warning'] = 'Policy unavailable/invalid; replacement cannot execute before review'
    return result


def unknown_resolve(request_id, action, preview, reason, evidence, *, db_path):
    from relttk.runtime.unknown_resolution import resolve
    # Display-only policy diagnostics do not replace the transactional decision preview.
    core = {k: v for k, v in preview.items() if k not in ('current_settings', 'quota_warning', 'policy_warning')}
    return resolve(request_id, action, core, reason, evidence, db_path=db_path)


def worker_preview(session, ids, *, db_path, **bounds):
    from relttk.runtime.worker import preview
    return preview(session, ids, db_path=db_path, **bounds)


def worker_authorize(preview, reason, *, db_path):
    from relttk.runtime.worker import authorize
    return authorize(preview, reason, db_path=db_path)


def worker_status(run_id, *, db_path):
    from relttk.runtime.worker import status
    return status(run_id, db_path=db_path)


def worker_revoke(run_id, preview, reason, *, db_path):
    from relttk.runtime.worker import revoke
    return revoke(run_id, preview, reason, db_path=db_path)


async def worker_run(run_id, fingerprint, *, db_path, stop_event=None):
    from relttk.runtime.worker import run
    return await run(run_id, fingerprint, db_path=db_path, stop_event=stop_event)


def operational_status(grant_id, *, db_path):
    from relttk.operations import status
    return status(grant_id, db_path=db_path)


def ledger_backup(db_path, destination):
    from relttk.operations import backup
    return backup(db_path, destination)
