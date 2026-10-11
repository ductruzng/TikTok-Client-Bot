import asyncio
import json
import os
import re
import ssl
import sys
import time
import uuid
from contextlib import nullcontext, closing
from typing import Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

from relttk import config
from relttk.storage import ledger
from relttk.storage import ledger_requests
from relttk.identity import circuit_breaker as breaker
from relttk.storage import queue_service
from relttk import log as _log
from relttk.transport.client import LttkClient, apply_ws_auth, build_ws_url, load_ws_auth
from core.api import get_conversations, get_own_user_id
from core.proto import build_ws_packet
from main import validate_config_data
from relttk.transport.qrlogin import load_session


def describe_ws_rejection(exc, url: str, headers: list[tuple[str, str]], cookies: dict) -> list[str]:
    """Log structural diagnostics only; never server-controlled text or credential values."""
    from urllib.parse import parse_qsl
    parts = urlsplit(url)
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    return [
        f"endpoint: {parts.hostname}{parts.path}",
        "query params: " + ", ".join(k for k, _ in parse_qsl(parts.query)),
        f"ttwid present: {bool(cookies.get('ttwid'))}, msToken present: {bool(cookies.get('msToken'))}",
        f"response: {status if type(status) is int else 'unavailable'}",
    ]


def validate_against_server_inbox(cookies: dict, targets: list[dict], device_id: str | None = None) -> None:
    """Validate configured conversation targets against actual server inbox metadata.

    Ensures that conversation exists and configured conv_short_id and conv_type
    match the server-reported metadata before any send attempt.
    """
    _log.info("oneshot", "Validating targets against server conversation inbox...")
    from relttk.transport.bounded_inbox import fetch
    inbox_convs = fetch(cookies, device_id)
    server_map = {c["conv_id"]: c for c in inbox_convs}

    for t in targets:
        cid = t["conv_id"]
        if cid not in server_map:
            raise ValueError(
                f"Target conversation '{cid}' was not found in TikTok server inbox. "
                f"Ensure the account has an existing conversation with this target."
            )
        srv = server_map[cid]
        srv_short_id = srv.get("conv_short_id", 0)
        srv_type = srv.get("conv_type", 1)

        if t["conv_short_id"] != srv_short_id:
            raise ValueError(
                f"Target '{cid}' metadata mismatch: configured conv_short_id is {t['conv_short_id']}, "
                f"but server inbox reports {srv_short_id}. Aborting send."
            )
        if t["conv_type"] != srv_type:
            raise ValueError(
                f"Target '{cid}' type mismatch: configured conv_type is {t['conv_type']}, "
                f"but server inbox reports {srv_type}. Aborting send."
            )
    _log.ok("oneshot", f"All {len(targets)} targets successfully validated against server inbox.")


async def _send_target_oneshot(
    ws,
    canonical_uid: str,
    target: dict,
    message_text: str,
    timeout_seconds: float = 20.0,
    db_path: str = ledger._DEFAULT_LEDGER_PATH,
    device_id: str | None = None,
    *, idempotency_key: str | None = None,
    allow_repeat_same_day: bool = False,
    max_sends_per_conversation_per_day: int = 1,
    max_sends_per_account_per_day: int = 20,
    min_send_interval_seconds: int = 60,
    max_sends_per_window: int = 5,
    window_seconds: int = 300,
    rotation_config=None, existing_request=None, config_loader=None, confirm_request=None, session_name=None,
    policy_reference=None, policy_config=None, worker_context=None,
) -> dict:
    """Execute durable reservation, transmission, and correlated echo confirmation for one target."""
    conv_id = target["conv_id"]
    conv_short_id = target["conv_short_id"]
    conv_type = target["conv_type"]

    # Recompute Ho Chi Minh date immediately before reservation
    send_date = ledger.get_current_ho_chi_minh_date()
    client_msg_id = str(uuid.uuid4())

    ledger_requests.validate_settings(allow_repeat_same_day, max_sends_per_conversation_per_day,
        max_sends_per_account_per_day=max_sends_per_account_per_day,
        min_send_interval_seconds=min_send_interval_seconds,
        max_sends_per_window=max_sends_per_window, window_seconds=window_seconds)
    key = f"daily:{send_date}:{conv_id}" if idempotency_key is None else idempotency_key
    payload = {"target": {"conv_id": conv_id, "conv_short_id": conv_short_id, "conv_type": conv_type},
               "message": message_text}
    if existing_request is None:
        request, created = ledger_requests.create_request(
            str(canonical_uid), conv_id, key, payload, db_path=db_path, client_msg_id=client_msg_id,
            rotation_config=rotation_config, session_name=session_name,
            policy_reference=policy_reference, policy_config=policy_config)
    else:
        request = ledger_requests.get_request(existing_request, db_path=db_path)
        if request['canonical_uid'] != str(canonical_uid) or request['conv_id'] != conv_id:
            raise ledger.LedgerError('Request account/conversation does not match authenticated target')
    snapshot_payload = json.loads(request['payload_json'])
    message_text = snapshot_payload['message']
    if snapshot_payload['target'] != payload['target']:
        raise ledger.LedgerError('Request target metadata differs; refusing transmission')
    client_msg_id = request['client_msg_id']
    request_id = request['request_id']
    if request['status'] != 'queued':
        return {"conv_id": conv_id, "request_id": request_id, "status": "skipped",
                "reason": f"already_{request['status']}", "existing_status": request['status'],
                "server_msg_id": request['server_msg_id']}
    if confirm_request is not None and not confirm_request(request):
        return {"conv_id": conv_id, "request_id": request_id, "status": "skipped", "existing_status": "queued", "reason": "confirmation_declined"}
    try:
        packet, msg_type, _ = build_ws_packet(
            conv_id=conv_id, short_id=conv_short_id, text=message_text,
            device_id=device_id or config.DEVICE_ID, sdk_ms_token=config.MSG_SDK_MS_TOKEN,
            tt_public_key=config.TT_PUBLIC_KEY, tt_client_data=config.TT_CLIENT_DATA,
            conv_type=conv_type, client_id=client_msg_id,
        )
    except Exception:
        ledger_requests.fail_pretransmit(request_id, db_path=db_path)
        return {"conv_id": conv_id, "request_id": request_id, "status": "failed_pretransmit",
                "reason": ledger.REASON_CLIENT_EXCEPTION}
    try:
        current_config = config_loader() if config_loader else policy_config
        started = ledger_requests.start_transmission(
            request_id, db_path=db_path,
            allow_repeat_same_day=allow_repeat_same_day,
            max_sends_per_conversation_per_day=max_sends_per_conversation_per_day,
            max_sends_per_account_per_day=max_sends_per_account_per_day,
            min_send_interval_seconds=min_send_interval_seconds,
            max_sends_per_window=max_sends_per_window, window_seconds=window_seconds,
            rotation_config=current_config if config_loader else rotation_config, session_name=session_name,
            policy_reference=policy_reference, policy_config=current_config, worker_context=worker_context)
        if not started:
            stored = ledger_requests.get_request(request_id, db_path=db_path)
            return {"conv_id": conv_id, "request_id": request_id, "status": "skipped",
                    "existing_status": stored['status'], "server_msg_id": stored['server_msg_id'],
                    "reason": "request_already_started"}
    except breaker.CircuitOpen as exc:
        return {"conv_id": conv_id, "request_id": request_id, "status": "skipped",
                "existing_status": "queued", **exc.result()}
    except ledger.QuotaExceededError as exc:
        _log.warn("oneshot", str(exc))
        return {"conv_id": conv_id, "request_id": request_id, "status": "skipped",
                "existing_status": "queued",
                "reason": "quota_claimed", "detail": str(exc),
                **(exc.result() if isinstance(exc, ledger_requests.RateLimitError) else {})}

    except ledger.LedgerError as exc:
        return {"conv_id": conv_id, "request_id": request_id, "status": "skipped", "existing_status": "queued", "reason": getattr(exc, 'code', 'snapshot_held'), "detail": str(exc)}

    send_date = ledger_requests.get_request(request_id, db_path=db_path)['date']
    start_monotonic = time.monotonic()
    deadline = start_monotonic + timeout_seconds

    # Transmit over WebSocket with bounded timeout
    try:
        remaining_send = max(0.1, deadline - time.monotonic())
        await asyncio.wait_for(ws.send(packet), timeout=min(5.0, remaining_send))
    except asyncio.CancelledError:
        ledger.mark_failed_unknown(canonical_uid, conv_id, send_date, client_msg_id,
            db_path=db_path, failure=breaker.Failure('UNKNOWN', 'send', 'cancelled'))
        raise
    except Exception as exc:
        _log.error("oneshot", f"[{conv_id}] WebSocket transmit failed ({ledger.REASON_WS_ERROR})")
        ledger.mark_failed_unknown(
            canonical_uid, conv_id, send_date, client_msg_id,
            reason_code=ledger.REASON_WS_ERROR, db_path=db_path,
            failure=breaker.classify(exc, "send")
        )
        return {"conv_id": conv_id, "request_id": request_id, "status": ledger.STATUS_FAILED_UNKNOWN, "reason": ledger.REASON_WS_ERROR}

    # Wait for correlated server echo with finite monotonic timeout
    confirmed = False
    server_msg_id = None
    failure_reason = ledger.REASON_CORRELATION_TIMEOUT
    failure = breaker.Failure("UNKNOWN", "echo", "deadline")

    try:
        while time.monotonic() < deadline:
            remaining = max(0.1, deadline - time.monotonic())
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
            except asyncio.TimeoutError:
                break

            if not isinstance(raw, bytes):
                continue

            candidates = LttkClient.decode_echo_frame(raw)
            for cand in candidates:
                is_match, reason, sid = LttkClient.check_echo_correlation(
                    cand,
                    expected_client_msg_id=client_msg_id,
                    expected_conv_id=conv_id,
                    own_user_id=canonical_uid,
                    expected_text=message_text,
                )
                if is_match and sid:
                    confirmed = True
                    server_msg_id = str(sid)
                    break

            if confirmed:
                break

    except asyncio.CancelledError:
        ledger.mark_failed_unknown(canonical_uid, conv_id, send_date, client_msg_id,
            db_path=db_path, failure=breaker.Failure('UNKNOWN', 'echo', 'cancelled'))
        raise
    except Exception as exc:
        failure = breaker.classify(exc, "echo") or breaker.Failure("UNKNOWN", "echo", "client")
        _log.error("oneshot", f"[{conv_id}] Exception while awaiting server echo ({ledger.REASON_CLIENT_EXCEPTION})")
        failure_reason = ledger.REASON_CLIENT_EXCEPTION

    if confirmed and server_msg_id:
        confirm_date = ledger.get_current_ho_chi_minh_date()
        ledger.confirm_send(
            canonical_uid, conv_id, send_date, client_msg_id,
            server_msg_id, confirm_date=confirm_date, db_path=db_path
        )
        _log.ok("oneshot", f"[{conv_id}] Confirmed server echo received: server_msg_id={server_msg_id}")
        return {"conv_id": conv_id, "request_id": request_id, "status": ledger.STATUS_CONFIRMED, "server_msg_id": server_msg_id}
    else:
        _log.warn("oneshot", f"[{conv_id}] Send unconfirmed; recorded as failed_unknown ({failure_reason}). Blocked until Owner review, including future days.")
        ledger.mark_failed_unknown(
            canonical_uid, conv_id, send_date, client_msg_id,
            reason_code=failure_reason, db_path=db_path, failure=failure
        )
        return {"conv_id": conv_id, "request_id": request_id, "status": ledger.STATUS_FAILED_UNKNOWN, "reason": failure_reason}


_RE_TIKTOK_WS_HOST = re.compile(r"^im-ws(?:-[a-z0-9]+)?\.tiktok\.com$")


def with_ws_host(url: str, host: str) -> str:
    """Swap the WS host; only im-ws*.tiktok.com is allowed so cookies never go elsewhere."""
    host = (host or "").strip().lower()
    if not _RE_TIKTOK_WS_HOST.match(host):
        raise ValueError(f"Refusing WebSocket host {host!r}: must look like im-ws-<region>.tiktok.com")
    parts = urlsplit(url)
    return urlunsplit(parts._replace(netloc=host))


def _prepare_ws(cookies: dict, session_name: str, ws_auth: dict | None = None) -> tuple[dict, str]:
    """Use only auth bound to this saved session, or an explicit in-memory capture candidate."""
    if ws_auth is None:
        ws_auth = load_ws_auth(session_name=session_name, cookies=cookies)
    if not ws_auth:
        _log.error("oneshot", "Missing session-bound auth. Run capture-ws-auth on Windows; see TERMUX.md.")
        raise ValueError("Missing session-bound WS auth; run capture-ws-auth on Windows (see TERMUX.md)")
    ws_cookies = apply_ws_auth(cookies, ws_auth)
    return ws_cookies, build_ws_url(ws_cookies, access_key=ws_auth["access_key"])


async def _open_ws(cookies: dict, ws_url: str):
    """Perform the verified-TLS WS handshake; log safe diagnostics if the server rejects it."""
    import websockets
    from websockets.exceptions import InvalidStatus

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = True
    ssl_ctx.verify_mode = ssl.CERT_REQUIRED

    cookie_hdr = "; ".join(f"{k}={v}" for k, v in cookies.items())
    headers = [
        ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"),
        ("Origin", "https://www.tiktok.com"),
        ("Cookie", cookie_hdr),
        ("Pragma", "no-cache"),
        ("Cache-Control", "no-cache"),
    ]
    ws_kw = "additional_headers" if tuple(int(x) for x in websockets.__version__.split(".")[:2]) >= (14, 0) else "extra_headers"

    if not cookies.get("ttwid"):
        _log.warn("oneshot", "Session has no ttwid cookie; the WebSocket gateway may reject the upgrade. "
                             "Re-run 'python main.py login' to refresh the session.")

    _log.info("oneshot", f"Connecting to TikTok WebSocket ({urlsplit(ws_url).hostname}) with verified TLS...")
    try:
        return await websockets.connect(
            ws_url,
            **{ws_kw: headers},
            subprotocols=["binary", "base64", "pbbp2"],
            ssl=ssl_ctx,
            ping_interval=20,
            ping_timeout=10,
            open_timeout=15,
            close_timeout=5,
        )
    except InvalidStatus as e:
        for line in describe_ws_rejection(e, ws_url, headers, cookies):
            _log.error("oneshot", f"WS handshake rejected - {line}")
        raise


async def probe_ws_handshake(session_name: str, host: str | None = None, *, ws_auth: dict | None = None) -> None:
    """Handshake-only diagnostic: connect, then close immediately.

    Sends no frames at all (not even the "hi" ping), touches no ledger and reads no
    streak config, so it can never transmit a message.
    """
    cookies = load_session(session_name)
    if not cookies or not cookies.get("sessionid"):
        raise ValueError(f"Session '{session_name}' not found or missing sessionid cookie.")
    ws_cookies, ws_url = _prepare_ws(cookies, session_name, ws_auth)
    if host:
        ws_url = with_ws_host(ws_url, host)
    connection = await _open_ws(ws_cookies, ws_url)
    await connection.close()
    _log.ok("oneshot", f"Handshake OK on {urlsplit(ws_url).hostname}; connection closed without sending any frame.")


async def run_oneshot_send(
    config_path: str = "streak.json",
    timeout_seconds: float = 20.0,
    validate_server: bool = True,
    db_path: str = ledger._DEFAULT_LEDGER_PATH,
    *, idempotency_key: str | None = None,
    allow_repeat_same_day: bool | None = None,
    max_sends_per_conversation_per_day: int | None = None,
    max_sends_per_account_per_day: int | None = None,
    min_send_interval_seconds: int | None = None,
    max_sends_per_window: int | None = None,
    window_seconds: int | None = None,
    request_id: str | None = None,
    confirm_request=None,
    _run_lock=None,
    _expected_session=None,
    _worker_context=None,
) -> dict:
    """Execute one-shot streak transmission workflow."""
    from relttk.runtime_paths import contained
    contained(config_path, private=True)
    ledger.check_ready(db_path)
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8-sig") as f:
        cfg = json.load(f)

    if not isinstance(cfg, dict):
        raise ValueError("Configuration file must contain a JSON object")

    valid, err, targets = validate_config_data(cfg)
    if not valid:
        raise ValueError(f"Configuration validation failed: {err}")

    repeat = cfg.get("allow_repeat_same_day", False) if allow_repeat_same_day is None else allow_repeat_same_day
    limit = cfg.get("max_sends_per_conversation_per_day", 1) if max_sends_per_conversation_per_day is None else max_sends_per_conversation_per_day
    settings = ledger_requests.settings_from_config(cfg)
    overrides = dict(allow_repeat_same_day=repeat, max_sends_per_conversation_per_day=limit,
                     max_sends_per_account_per_day=max_sends_per_account_per_day,
                     min_send_interval_seconds=min_send_interval_seconds,
                     max_sends_per_window=max_sends_per_window, window_seconds=window_seconds)
    settings.update({key: value for key, value in overrides.items() if value is not None})
    settings = ledger_requests.validate_settings(**settings)
    if idempotency_key is not None and (not isinstance(idempotency_key, str) or not idempotency_key.strip()):
        raise ValueError("Idempotency key must be a nonempty string")
    session_name = cfg["session"]
    if _worker_context is not None and (not request_id or confirm_request is not None):
        raise ledger.LedgerError('Worker execution requires an existing manifest request and separate durable consent')
    if _expected_session is not None and session_name != _expected_session:
        raise queue_service.QueueHeld('SESSION_ROUTE_CHANGED', 'Run session differs from the current queue policy; review again')
    message_text = cfg.get("message", "")
    def reload_config():
        with open(config_path, encoding="utf-8-sig") as stream:
            return json.load(stream)

    lock_path = os.path.join(os.path.dirname(os.path.abspath(db_path)), 'run.lock')
    if _run_lock is not None and (not isinstance(_run_lock, ledger.RunLock) or _run_lock._fd is None
            or os.path.abspath(_run_lock.lock_path) != lock_path):
        raise ledger.LockError('Queue execution requires the held database run lock')
    context = nullcontext(_run_lock) if _run_lock is not None else ledger.RunLock(lock_path)
    with context as run_lock:
        try:
            canonical_uid = queue_service.verified_uid(session_name, db_path=db_path)
        except queue_service.QueueHeld:
            breaker.gate(db_path=db_path, session=session_name)
            raise
        replay_rows = []
        if request_id:
            replay = ledger_requests.get_request(request_id, db_path=db_path)
            if replay['canonical_uid'] != canonical_uid or not any(t['conv_id'] == replay['conv_id'] for t in targets):
                raise ledger.LedgerError('Request does not match the verified account and target')
            if idempotency_key is not None and idempotency_key != replay['idempotency_key']:
                raise ledger.LedgerError('Resume requires the exact stored idempotency key')
            replay_rows = [replay]
        else:
            for target in targets:
                key = (queue_service.task_request_key(idempotency_key, target['conv_id']) if idempotency_key else
                       f"daily:{ledger.get_current_ho_chi_minh_date()}:{target['conv_id']}")
                replay_rows.append(ledger_requests.lookup_replay(canonical_uid, target['conv_id'], key,
                    {'target': target, 'message': message_text}, db_path=db_path,
                    rotation_config=cfg if 'rotation' in cfg else None))
        if replay_rows and all(r and r['status'] not in ('queued', 'pending') for r in replay_rows):
            return dict(canonical_uid=canonical_uid, date=ledger.get_current_ho_chi_minh_date(), results=[
                dict(conv_id=r['conv_id'], request_id=r['request_id'], status='skipped', existing_status=r['status'],
                     reason='already_' + r['status'], server_msg_id=r['server_msg_id']) for r in replay_rows])
        ledger_requests.recover_pending(db_path=db_path, run_lock=run_lock)
        breaker.gate(db_path=db_path, session=session_name)
        results = []
        connection = None
        cookies = None
        effective_device_id = None
        stage = 'local'
        try:
            if request_id:
                stored = ledger_requests.get_request(request_id, db_path=db_path)
                if idempotency_key is not None and idempotency_key != stored['idempotency_key']:
                    raise ledger.LedgerError('Resume requires the exact stored idempotency key')
                targets = [t for t in targets if t['conv_id'] == stored['conv_id']]
                if len(targets) != 1 or stored['canonical_uid'] != canonical_uid:
                    raise ledger.LedgerError('Request does not match the verified account and target')
            for target in targets:
                stage = 'local'
                if request_id:
                    row = stored
                else:
                    day = ledger.get_current_ho_chi_minh_date()
                    key = (queue_service.task_request_key(idempotency_key, target['conv_id']) if idempotency_key else
                           f"daily:{day}:{target['conv_id']}")
                    row, _ = ledger_requests.create_request(canonical_uid, target['conv_id'], key,
                        {'target': target, 'message': message_text}, db_path=db_path,
                        rotation_config=cfg if 'rotation' in cfg else None,
                        session_name=session_name, policy_reference=config_path, policy_config=cfg)
                if row['status'] != 'queued':
                    results.append(dict(conv_id=row['conv_id'], request_id=row['request_id'], status='skipped',
                        reason='already_' + row['status'], existing_status=row['status'], server_msg_id=row['server_msg_id']))
                    continue
                # Admission preview before credentials/network. Claim repeats every check atomically.
                try:
                    with closing(ledger._get_readonly_connection(db_path)) as conn:
                        import sqlite3
                        conn.row_factory = sqlite3.Row
                        conn.execute('BEGIN')
                        current = reload_config()
                        if _worker_context is not None:
                            from relttk.runtime.worker import check_authorization
                            check_authorization(conn, row, _worker_context)
                        ledger_requests.check_admission(conn, row, settings, rotation_config=current,
                            session_name=session_name, policy_reference=config_path, policy_config=current)
                except ledger.LedgerError as exc:
                    result = dict(conv_id=row['conv_id'], request_id=row['request_id'], status='skipped',
                        existing_status='queued', reason=getattr(exc, 'code', 'quota_claimed' if isinstance(exc, ledger.QuotaExceededError) else 'snapshot_held'), detail=str(exc))
                    if hasattr(exc, 'result'):
                        result.update(exc.result())
                    results.append(result)
                    continue
                if confirm_request is not None and not confirm_request(row):
                    results.append(dict(conv_id=row['conv_id'], request_id=row['request_id'], status='skipped',
                        existing_status='queued', reason='confirmation_declined'))
                    continue
                if connection is None:
                    cookies = load_session(session_name)
                    if not cookies or not cookies.get('sessionid'):
                        raise ValueError('Saved session is missing; explicit login/setup is required')
                    stage = 'identity'
                    authenticated_uid = get_own_user_id(cookies=cookies, use_cache=False)
                    if not authenticated_uid or str(authenticated_uid) != canonical_uid:
                        raise breaker.ProtocolFailure('Session identity differs from the verified queue binding')
                    breaker.gate(db_path=db_path, uid=canonical_uid, session=session_name)
                    stage = 'local'
                    ws_auth = load_ws_auth(session_name=session_name, cookies=cookies)
                    effective_device_id = ws_auth.get('device_id') if ws_auth else config.DEVICE_ID
                    stage = 'inbox'
                    if validate_server:
                        await asyncio.to_thread(validate_against_server_inbox, cookies, targets, device_id=effective_device_id)
                    stage = 'handshake'
                    connection = await _open_ws(*_prepare_ws(cookies, session_name, ws_auth))
                    await asyncio.wait_for(connection.send('hi'), timeout=5.0)
                    try:
                        await asyncio.wait_for(connection.recv(), timeout=5.0)
                    except asyncio.TimeoutError:
                        pass
                stage = 'local'
                res = await _send_target_oneshot(connection, canonical_uid, target, message_text,
                    timeout_seconds=timeout_seconds, db_path=db_path, device_id=effective_device_id,
                    existing_request=row['request_id'], rotation_config=cfg if 'rotation' in cfg else None,
                    session_name=session_name, policy_reference=config_path, policy_config=cfg,
                    config_loader=reload_config, worker_context=_worker_context, **settings)
                results.append(res)
                if res.get('status') == 'failed_unknown' or res.get('reason') == 'CIRCUIT_OPEN':
                    results.extend(dict(conv_id=t['conv_id'], status='not_attempted', reason='CIRCUIT_OPEN')
                                   for t in targets[len(results):])
                    break
            return dict(canonical_uid=canonical_uid, date=ledger.get_current_ho_chi_minh_date(), results=results)
        except Exception as exc:
            failure = breaker.classify(exc, stage) if stage != 'local' else None
            if failure is not None:
                breaker.record_failure(failure, db_path=db_path, uid=canonical_uid, session=session_name)
                raise breaker.CircuitOpen(breaker.inspect(db_path=db_path, uid=canonical_uid, session=session_name)) from None
            raise
        finally:
            if connection is not None:
                await connection.close()
