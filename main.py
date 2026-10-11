"""CLI entrypoint for ReLttk Daily Streak.

Default behavior is a one-shot offline DRY-RUN using only Python standard library.
Network transmission requires explicit --send opt-in.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from typing import Tuple, Optional

# Lazy imports for optional modules
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
if _PKG_DIR not in sys.path:
    sys.path.insert(0, _PKG_DIR)

DEFAULT_CONFIG_FILE = "streak.json"


def get_ho_chi_minh_date() -> str:
    """Return current date formatted for Asia/Ho_Chi_Minh timezone using stdlib."""
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("Asia/Ho_Chi_Minh")
    except Exception:
        from datetime import timezone, timedelta
        tz = timezone(timedelta(hours=7))
    return datetime.now(tz).strftime("%Y-%m-%d")


def validate_config(cfg: object) -> Tuple[bool, list[str], list[dict]]:
    """Validate streak configuration using stdlib only.

    Returns (is_valid, error_messages, parsed_targets).
    """
    errors = []
    parsed_targets = []

    if not isinstance(cfg, dict):
        return False, ["Configuration file must contain a JSON object."], []

    session = cfg.get("session")
    if session is None or not isinstance(session, str):
        errors.append("Field 'session' must be a string.")
    elif not session.strip():
        errors.append("Field 'session' is empty. Specify the session name configured via 'python main.py login'.")
    else:
        session_str = session.strip()
        if "/" in session_str or "\\" in session_str or ".." in session_str or "\0" in session_str or not re.match(r'^[a-zA-Z0-9_\.-]+$', session_str):
            errors.append(f"Field 'session' has unsafe name {session_str!r}. Path traversal characters are disallowed.")

    import rotation
    try:
        rotation.catalog(cfg)
    except (ValueError, UnicodeError) as exc:
        errors.append(str(exc))

    from ledger_requests import settings_from_config
    try:
        settings_from_config(cfg)
    except ValueError as exc:
        errors.append(str(exc))

    raw_targets = cfg.get("targets")
    if raw_targets is None or not isinstance(raw_targets, list):
        errors.append("Field 'targets' must be a list of target objects.")
    elif len(raw_targets) == 0:
        errors.append("Field 'targets' is empty. At least one conversation target is required.")
    else:
        seen_ids = set()
        for i, t in enumerate(raw_targets):
            prefix = f"targets[{i}]"
            if not isinstance(t, dict):
                errors.append(f"{prefix} must be a JSON object with conv_id, conv_short_id, conv_type.")
                continue

            conv_id = t.get("conv_id")
            if not conv_id or not isinstance(conv_id, str) or not conv_id.strip():
                errors.append(f"{prefix}.conv_id must be a non-empty conversation identifier string.")
            else:
                conv_id = conv_id.strip()
                if conv_id in seen_ids:
                    errors.append(f"Duplicate conversation ID detected: '{conv_id}'. Each target must be unique.")
                seen_ids.add(conv_id)

            raw_short_id = t.get("conv_short_id")
            if isinstance(raw_short_id, bool) or isinstance(raw_short_id, float):
                errors.append(
                    f"{prefix}.conv_short_id must be a positive integer (> 0). Got {raw_short_id!r}."
                )
                short_id = 0
            else:
                try:
                    short_id = int(raw_short_id)
                    if short_id <= 0:
                        errors.append(
                            f"{prefix}.conv_short_id must be a positive integer (> 0). Got {raw_short_id!r}."
                        )
                        short_id = 0
                    elif short_id > 0xFFFFFFFFFFFFFFFF:
                        errors.append(
                            f"{prefix}.conv_short_id overflows 64-bit integer range. Got {raw_short_id!r}."
                        )
                        short_id = 0
                except (ValueError, TypeError):
                    errors.append(
                        f"{prefix}.conv_short_id must be a positive integer (> 0). "
                        f"Got {raw_short_id!r}. Use 'python main.py list-conversations' to obtain short IDs."
                    )
                    short_id = 0

            raw_type = t.get("conv_type", 1)
            if isinstance(raw_type, bool) or isinstance(raw_type, float):
                errors.append(f"{prefix}.conv_type must be 1 (Direct) or 2 (Group). Got {raw_type!r}.")
                conv_type = 1
            else:
                try:
                    conv_type = int(raw_type)
                    if conv_type not in (1, 2):
                        raise ValueError()
                except (ValueError, TypeError):
                    errors.append(f"{prefix}.conv_type must be 1 (Direct) or 2 (Group). Got {raw_type!r}.")
                    conv_type = 1

            parsed_targets.append({
                "conv_id": conv_id or f"target_{i}",
                "conv_short_id": short_id,
                "conv_type": conv_type,
            })

    return len(errors) == 0, errors, parsed_targets


def validate_config_data(cfg: object) -> Tuple[bool, str, list[dict]]:
    """Single strict configuration validator shared across main and oneshot."""
    valid, errors, targets = validate_config(cfg)
    return valid, "; ".join(errors), targets


def cmd_dry_run(config_path: str = DEFAULT_CONFIG_FILE) -> int:
    """Execute stdlib-only dry run display."""
    today = get_ho_chi_minh_date()

    print("=" * 64)
    print(" ReLttk Daily Streak Bot - Plan (OFFLINE DRY-RUN)")
    print("=" * 64)
    print(f" Target Date:      {today} (Asia/Ho_Chi_Minh)")
    print(f" Config File:      {os.path.abspath(config_path)}")

    if not os.path.exists(config_path):
        print(f"\n[!] Config file '{config_path}' does not exist.")
        print("    Create it with the following structure:")
        print(json.dumps({
            "session": "my_account",
            "message": "Daily streak message",
            "targets": [
                {"conv_id": "0:1:12345:67890", "conv_short_id": 1234567890, "conv_type": 1}
            ]
        }, indent=2))
        return 1

    try:
        with open(config_path, "r", encoding="utf-8-sig") as f:
            cfg = json.load(f)
    except Exception:
        print(f"\n[!] Error parsing JSON in '{config_path}'.")
        return 1

    if not isinstance(cfg, dict):
        print(f"\n[!] Configuration file '{config_path}' must contain a JSON object.")
        return 1

    is_valid, errors, targets = validate_config(cfg)

    session_name = cfg.get("session") or "<none>"
    message_text = cfg.get("message") or "<none>"

    print(f" Session Name:     {session_name}")
    print(f" Message Text:     {message_text!r}")
    print("-" * 64)

    if not is_valid:
        print("[!] Configuration Validation Issues:")
        for err in errors:
            print(f"    - {err}")
        print("\n[NOTE] Dry-run stopped due to configuration errors.")
        print("       Edit streak.json to correct these fields before sending.")
        return 1

    if "rotation" in cfg:
        print(json.dumps(cfg['rotation'], ensure_ascii=True, indent=2))
        print("Rotation preview: selection requires ledger state; no choice or state change made.")
    print(f" Planned Targets ({len(targets)} total):")
    for idx, t in enumerate(targets, 1):
        type_label = "Direct (1)" if t["conv_type"] == 1 else "Group (2)"
        print(f"   {idx}. Conv ID:       {t['conv_id']}")
        print(f"      Short ID:      {t['conv_short_id']}")
        print(f"      Type:          {type_label}")
        print(f"      Ledger Status: Quota not checked offline (requires authenticated session)")

    print("=" * 64)
    print(" [DRY-RUN COMPLETE]")
    print(" - Zero network calls were made.")
    print(" - No session credentials or cookies were accessed.")
    print(" - No SQLite database files were created or modified.")
    print(" - Quota not checked offline (evaluated during live authenticated send).")
    print(" - To transmit messages for real, use explicit opt-in:")
    print(f"       python main.py --send --config {config_path}")
    print("=" * 64)
    return 0


def cmd_send(config_path: str = DEFAULT_CONFIG_FILE, idempotency_key: str | None = None, db_path: str | None = None,
             *, request_id=None, confirm_request=None) -> int:
    """Execute one-shot live transmission with explicit opt-in."""
    print("=" * 64)
    print(" ReLttk Daily Streak Bot - Executing One-Shot Send")
    print("=" * 64)

    try:
        import ledger
        import asyncio
        from services import send_plan, send_result_completed
        options = {"db_path": db_path} if db_path is not None else {}
        if request_id:
            options['request_id'] = request_id
        if confirm_request:
            options['confirm_request'] = confirm_request
        result = asyncio.run(send_plan(config_path, idempotency_key=idempotency_key, **options))
        print("\nTransmission Summary:")
        print(f" Canonical UID: {result.get('canonical_uid')}")
        print(f" Date:          {result.get('date')}")
        results_list = result.get("results", [])
        for r in results_list:
            st = r.get("status")
            cid = r.get("conv_id")
            if st == "confirmed":
                print(f"  [+] {cid}: CONFIRMED (Server Msg ID: {r.get('server_msg_id')})")
            elif st == "skipped":
                stored = r.get('existing_status', 'unspecified')
                print(f"  [-] {cid}: SKIPPED; request={stored.upper()} ({r.get('detail') or r.get('reason')})")
            else:
                label = st.upper() if isinstance(st, str) else 'INVALID_RESULT'
                print(f"  [x] {cid}: {label} ({r.get('detail') or r.get('reason')})")
        if not results_list or not all(send_result_completed(r) for r in results_list):
            return 1
        return 0
    except Exception as e:
        if not _report_ws_rejection(e):
            print(f"\n[!] Send execution failed: {type(e).__name__}")
            if isinstance(e, ledger.LedgerError):
                print(str(e))
        return 1


def _report_ws_rejection(e: Exception) -> bool:
    """Print a status-only summary for a rejected WS upgrade; return False if e is something else."""
    if type(e).__name__ != "InvalidStatus":
        return False
    status = getattr(getattr(e, "response", None), "status_code", None)
    label = f"HTTP {status}" if type(status) is int and 100 <= status <= 599 else "HTTP status unavailable"
    print(f"\n[!] WebSocket upgrade rejected ({label}). No message was transmitted.")
    print("    See the 'WS handshake rejected' diagnostics above. If ttwid is missing, re-run 'python main.py login'.")
    return True


def cmd_ws_probe(session_name: str, host: Optional[str] = None) -> int:
    """Handshake-only WebSocket check; never sends any frame or message."""
    session_name = (session_name or "").strip()
    if not session_name or not re.match(r'^[a-zA-Z0-9_\.-]+$', session_name) or ".." in session_name:
        print("[!] Invalid session name.")
        return 1
    try:
        import asyncio
        import oneshot
        asyncio.run(oneshot.probe_ws_handshake(session_name, host=host))
        print("\n[+] WebSocket handshake succeeded. No message was transmitted.")
        return 0
    except Exception as e:
        if not _report_ws_rejection(e):
            print(f"\n[!] WebSocket probe failed: {type(e).__name__}")
        return 1


def cmd_login() -> int:
    """Interactive QR code login for future user use."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        print("[!] Interactive QR login requires both stdin and stdout to be interactive TTY terminals.")
        return 1

    print("Starting interactive QR login...")
    try:
        import qrlogin
        qrlogin.run()
        return 0
    except Exception as e:
        print(f"[!] Login error: {type(e).__name__}")
        return 1


def cmd_capture_ws_auth(session_name: str) -> int:
    """Explicit Windows browser setup; a handshake probe never sends a DM."""
    if sys.platform != "win32":
        print("[!] Capture browser auth on Windows; see TERMUX.md for transfer instructions.")
        return 1
    try:
        from ws_auth_capture import capture_session_auth
        capture_session_auth(session_name)
        return 0
    except Exception as exc:
        print(f"[!] Browser auth setup failed: {type(exc).__name__}.")
        print("    Check optional requirements-auth-windows.txt and Chromium installation, then retry manually.")
        return 1


def cmd_list_conversations(session_name: str) -> int:
    """Fetch and display server conversation metadata for config preparation."""
    if not session_name or not session_name.strip():
        print("[!] --session is required for list-conversations.")
        return 1
    session_name = session_name.strip()
    if "/" in session_name or "\\" in session_name or ".." in session_name or "\0" in session_name:
        print("[!] Invalid session name: path traversal characters are disallowed.")
        return 1

    try:
        import qrlogin
        import core.api as api
        import config

        cookies = qrlogin.load_session(session_name)
        if not cookies.get("sessionid"):
            print(f"[!] Session '{session_name}' contains no valid sessionid.")
            return 1

        print("Fetching conversations from TikTok server inbox...")
        convs = api.get_conversations(cookies=cookies, device_id=config.DEVICE_ID)
        if not convs:
            print("No conversations found in server inbox.")
            return 0

        print(f"\nFound {len(convs)} conversations:")
        print(f"{'#':<3} {'Conv ID':<36} {'Short ID':<22} {'Type':<8} {'Name'}")
        print("-" * 85)
        for i, c in enumerate(convs, 1):
            type_str = "Group" if c.get("is_group") else "Direct"
            name_str = c.get('name', '')
            try:
                name_str.encode(sys.stdout.encoding or 'utf-8')
            except UnicodeEncodeError:
                name_str = name_str.encode('ascii', 'replace').decode('ascii')

            print(
                f"{i:<3} {c.get('conv_id', ''):<36} "
                f"{str(c.get('conv_short_id', 0)):<22} "
                f"{type_str:<8} "
                f"{name_str}"
            )
        print("\nUse the Conv ID and Short ID above in your streak.json config targets.")
        return 0
    except Exception as e:
        print(f"[!] Error fetching conversations: {type(e).__name__}")
        return 1


def cmd_status(config_path: str = DEFAULT_CONFIG_FILE, db_path: str | None = None) -> int:
    """Readonly inspection of the SQLite ledger."""
    today = get_ho_chi_minh_date()
    print(f"Ledger Status for {today} (Asia/Ho_Chi_Minh):")
    try:
        import ledger
        db_path = db_path or ledger._DEFAULT_LEDGER_PATH
        if not os.path.exists(db_path):
            print("  Ledger database file does not exist yet (clean state).")
            return 0

        conn = ledger._get_readonly_connection(db_path)
        if conn is None:
            print("  Ledger database file not accessible.")
            return 0
        try:
            cur = conn.cursor()
            if conn.execute("PRAGMA user_version").fetchone()[0] in (2, 3, 4, 5, 6, 7):
                for row in conn.execute("SELECT request_id,date,status,conv_id,transmitted FROM send_requests ORDER BY created_at DESC LIMIT 20"):
                    print(f"  Request {row[0]} | {row[1] or '-'} | {row[2]} | {row[3]} | transmitted={row[4]}")
                return 0
            cur.execute(
                "SELECT canonical_uid, conv_id, date, status, attempt_time, server_msg_id, reason_code "
                "FROM daily_ledger ORDER BY date DESC, attempt_time DESC LIMIT 20"
            )
            rows = cur.fetchall()
            if not rows:
                print("  No records found in daily ledger.")
                return 0
            print(f"{'Date':<12} {'Status':<16} {'Conv ID':<32} {'Server Msg ID':<16} {'Reason'}")
            print("-" * 90)
            for r in rows:
                print(f"{r[2]:<12} {r[3]:<16} {r[1]:<32} {str(r[5] or ''):<16} {str(r[6] or '')}")
            return 0
        finally:
            conn.close()
    except Exception as e:
        print(f"[!] Error reading ledger: {type(e).__name__}")
        return 1


def cmd_ledger_admin(command, db_path):
    import ledger_migrations
    try:
        if command == "ledger-initialize":
            ledger_migrations.initialize(db_path)
            print(f"Initialized schema V{ledger_migrations.VERSION}. No TikTok access.")
            return 0
        report = ledger_migrations.preflight(db_path)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if report['errors']:
            return 1
        if command == "ledger-migrate":
            backup = ledger_migrations.migrate(db_path)
            print(f"Schema V{ledger_migrations.VERSION} ready. Backup: {backup or 'unchanged'}")
        return 0
    except Exception as exc:
        print(f"Ledger administration failed: {type(exc).__name__}: {exc}")
        return 1


def confirm_snapshot(row):
    print('Request:', row['request_id'])
    print('Exact payload:', row['payload_json'])
    if row['snapshot_json']:
        print('Rotation snapshot:', row['snapshot_json'])
    return input('Type SEND to transmit this request: ') == 'SEND'


def cmd_request_admin(args):
    import services
    import ledger
    try:
        if args.command == 'rotation-skip-selection':
            if not (sys.stdin.isatty() and sys.stdout.isatty()):
                raise ValueError('Selection skip requires an interactive terminal; --yes is insufficient')
            scope = (args.account, args.conversation, args.campaign)
            preview = services.rotation_skip_preview(scope, db_path=args.db)
        else:
            preview = services.request_preview(args.request_id, db_path=args.db,
                config_path=args.config if args.command == 'request-approve-snapshot' else None)
        print(json.dumps(preview, ensure_ascii=True, indent=2))
        if args.command == 'request-show':
            return 0
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            raise ValueError('This administration command requires interactive preview and confirmation')
        reason = input('Required reason: ')
        if input(f'Type {args.command} to confirm: ') != args.command:
            print('No changes made.')
            return 1
        if args.command == 'rotation-skip-selection':
            services.rotation_skip(scope, preview, reason, db_path=args.db)
        elif args.command == 'request-cancel':
            services.cancel_request(args.request_id, reason, db_path=args.db)
        else:
            services.approve_request_snapshot(args.request_id, preview, reason, db_path=args.db, config_path=args.config)
        print('Recorded. No message sent.')
        return 0
    except (ValueError, RuntimeError, ledger.LedgerError) as exc:
        print(f'Administration blocked: {exc}')
        return 1


def cmd_breaker_admin(args):
    import ledger
    import services
    try:
        rows = services.breaker_status(db_path=args.db, account=args.account, session=args.session,
                                       history=args.command == 'breaker-history')
        print(json.dumps(rows, ensure_ascii=True, indent=2))
        if args.command != 'breaker-reset':
            return 0
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            raise ValueError('Reset requires interactive preview and separate confirmation')
        if len(rows) != 1:
            raise ValueError('Select exactly one existing circuit to reset')
        reason = input('Required reason (do not enter credentials): ')
        if input('Type RESET to confirm: ') != 'RESET':
            return 1
        row = rows[0]
        services.breaker_reset(row['scope_type'], row['scope_key'], row, reason, db_path=args.db)
        print('Reset recorded. Other scope barriers remain. No message sent.')
        return 0
    except (ValueError, ledger.LedgerError) as exc:
        print(f'Breaker administration blocked: {exc}')
        return 1


def cmd_queue_admin(args):
    import asyncio
    import ledger
    import services
    try:
        if args.command == 'queue-enqueue':
            result = services.queue_enqueue(args.config, args.idempotency_key, db_path=args.db, apply=args.apply)
        elif args.command == 'queue-list':
            result = services.queue_list(db_path=args.db, session=args.session)
        elif args.command == 'queue-bind':
            result = services.queue_bind_preview(args.request_id, args.config, db_path=args.db)
            print(json.dumps(result, ensure_ascii=True, indent=2))
            if not (sys.stdin.isatty() and sys.stdout.isatty()):
                raise ValueError('Queue binding requires interactive preview and confirmation')
            reason = input('Required reason (no credentials): ')
            if input('Type BIND to confirm: ') != 'BIND':
                return 1
            services.queue_bind(args.request_id, args.config, result, reason, db_path=args.db)
            print('Binding recorded. No message sent. Snapshot approval remains separate.')
            return 0
        else:
            result = services.queue_run_preview(db_path=args.db, session=args.session)
            print(json.dumps(result, ensure_ascii=True, indent=2))
            if not args.execute:
                return 0
            if not (sys.stdin.isatty() and sys.stdout.isatty()):
                raise ValueError('Queue run-once execution is interactive only; --yes does not authorize it')
            if input('Type RUN to review and execute this finite queue run: ') != 'RUN':
                return 1
            result = asyncio.run(services.queue_run_once(db_path=args.db, session=args.session,
                max_jobs=args.max_jobs, confirm_request=confirm_snapshot))
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 0 if args.command != 'queue-run-once' or all(services.send_result_completed(r) for r in result['results']) else 1
    except (ValueError, OSError, ledger.LedgerError) as exc:
        print(f'Queue operation blocked: {exc}')
        return 1


def cmd_unknown_admin(args):
    import ledger
    import services
    import unknown_resolution
    try:
        preview = services.unknown_preview(args.request_id, db_path=args.db)
        print(json.dumps(preview, ensure_ascii=True, indent=2))
        if args.command == 'unknown-show':
            return 0
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            raise ValueError('UNKNOWN resolution requires interactive evidence review and separate confirmation')
        action = args.action or input('Action (KEEP_BLOCKED / CLOSE_WITHOUT_RESEND / AUTHORIZE_REPLACEMENT): ')
        if action not in unknown_resolution.ACTIONS:
            raise ValueError('Invalid decision')
        reason = input('Required reason (no credentials): ')
        evidence = input('Required observation/reference (no credentials or raw logs): ')
        challenge = action + ' ' + args.request_id + ' ' + preview['fingerprint']
        if input('Type ' + challenge + ' to confirm: ') != challenge:
            return 1
        result = services.unknown_resolve(args.request_id, action, preview, reason, evidence, db_path=args.db)
        print(json.dumps(result, indent=2))
        if result['replacement_request_id']:
            print('Replacement queued; UNKNOWN quota retained. Review queue limits and reset circuits separately. No message sent.')
        return 0
    except (ValueError, OSError, ledger.LedgerError) as exc:
        print(f'UNKNOWN review blocked: {exc}')
        return 1


def cmd_readiness_admin(args):
    import services
    try:
        if args.command == 'runtime-preflight':
            result = services.runtime_preflight(args.runtime_dir, args.db, args.config,
                                               check_credentials=args.check_credentials)
            print(json.dumps(result, ensure_ascii=True, indent=2))
            return 2 if result['state'] == 'BLOCKED' else 1
        if args.apply and not args.live:
            raise ValueError('Explicit --live is required before identity apply')
        if not args.live:
            result = services.identity_preview(args.session, db_path=args.db)
            print(json.dumps(result, ensure_ascii=True, indent=2))
            return 0
        review = services.identity_verify(args.session, db_path=args.db)
        print(json.dumps(review.public(), ensure_ascii=True, indent=2))
        if not args.apply:
            return 0
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            raise ValueError('Interactive identity approval required')
        reason = input('Required identity binding reason (no credentials): ')
        challenge = 'BIND ' + review.session + ' ' + review.uid
        if input('Type ' + challenge + ': ') != challenge:
            return 1
        services.identity_apply(review, reason, db_path=args.db)
        print('Identity bound; no message sent')
        return 0
    except Exception as exc:
        print('Readiness/identity blocked: ' + type(exc).__name__)
        return 2


def cmd_worker_admin(args):
    import asyncio
    import signal
    import services
    import ledger
    try:
        if args.command in ('worker-preview', 'worker-authorize'):
            expires = None
            if args.expires_at:
                from datetime import datetime
                value = datetime.fromisoformat(args.expires_at.replace('Z', '+00:00'))
                if value.tzinfo is None:
                    raise ValueError('Expiry must include a timezone offset')
                expires = int(value.timestamp()*1000)
            review = services.worker_preview(args.session, args.request_id, db_path=args.db,
                max_jobs=args.max_jobs, max_wait=args.max_wait, expires_at_ms=expires)
            print(json.dumps(review, ensure_ascii=True, indent=2))
            if args.command == 'worker-preview' or not args.apply:
                return 0
            if not (sys.stdin.isatty() and sys.stdout.isatty()):
                raise ValueError('Worker consent requires interactive preview and separate confirmation')
            reason = input('Required approval reason (no credentials): ')
            if input('Type APPROVE ' + review['fingerprint'] + ': ') != 'APPROVE ' + review['fingerprint']:
                return 1
            run_id = services.worker_authorize(review, reason, db_path=args.db)
            print('Approved run: ' + run_id + '; no message sent')
            return 0
        current = services.worker_status(args.run_id, db_path=args.db)
        if args.command == 'worker-status' or (args.command == 'worker-run' and not args.execute):
            print(json.dumps(current, ensure_ascii=True, indent=2))
            return 0
        if args.command == 'worker-revoke':
            print(json.dumps(current, ensure_ascii=True, indent=2))
            if not (sys.stdin.isatty() and sys.stdout.isatty()):
                raise ValueError('Worker revocation requires interactive review')
            reason = input('Required revocation reason: ')
            challenge = 'REVOKE ' + args.run_id + ' ' + current['fingerprint']
            if input('Type ' + challenge + ': ') != challenge:
                return 1
            services.worker_revoke(args.run_id, current, reason, db_path=args.db)
            return 0
        if not args.yes or not args.manifest_fingerprint:
            raise ValueError('Worker execution requires --yes and the exact approved manifest fingerprint')
        async def execute():
            stop = asyncio.Event()
            previous = {}
            try:
                for sig in (signal.SIGINT, signal.SIGTERM):
                    previous[sig] = signal.signal(sig, lambda *_: stop.set())
                return await services.worker_run(args.run_id, args.manifest_fingerprint, db_path=args.db, stop_event=stop)
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
        result = asyncio.run(execute())
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return {'COMPLETE': 0, 'HELD': 1, 'WAIT_LIMIT': 2, 'NEEDS_OWNER_REVIEW': 3, 'BUSY': 4, 'STOPPED': 130}.get(result['state'], 3)
    except (ValueError, OSError, ledger.LedgerError) as exc:
        # No raw policy content, network response or credentials in operational diagnostics.
        print('Worker operation blocked: ' + getattr(exc, 'code', type(exc).__name__))
        return 3


def cmd_schedule_admin(args):
    import asyncio
    import signal
    import services
    import ledger
    try:
        if args.command in ('schedule-preview', 'schedule-authorize'):
            review = services.schedule_preview(args.config, args.schedule_id, db_path=args.db,
                **{k:getattr(args,k) for k in ('time','valid_from','valid_through','window_minutes','daily_budget','total_budget','max_wait')})
            print(json.dumps(review, ensure_ascii=True, indent=2))
            if args.command == 'schedule-preview' or not args.apply:
                return 0
            if not (sys.stdin.isatty() and sys.stdout.isatty()):
                raise ValueError('Interactive recurring authorization required')
            reason = input('Required reason (no credentials): ')
            challenge = 'AUTHORIZE ' + review['fingerprint']
            if input('Type ' + challenge + ': ') != challenge:
                return 1
            gid = services.schedule_authorize(review,reason,db_path=args.db)
            print('Authorized grant: '+gid+'; inactive; no message sent')
            return 0
        if args.command == 'schedule-tick':
            if args.execute and not args.yes:
                raise ValueError('Execution requires --execute --yes and grant fingerprint')
            async def execute():
                stop = asyncio.Event()
                previous = {}
                try:
                    if args.execute:
                        for sig in (signal.SIGINT,signal.SIGTERM):
                            previous[sig] = signal.signal(sig,lambda *_: stop.set())
                    return await services.schedule_tick(args.grant_id,args.grant_fingerprint,db_path=args.db,
                        execute=args.execute,enqueue_only=args.enqueue,stop_event=stop)
                finally:
                    for sig,handler in previous.items(): signal.signal(sig,handler)
            result=asyncio.run(execute())
            if args.operational_output:
                import operations
                operations.note(result)
            print(json.dumps(result,ensure_ascii=True,indent=2))
            state=result.get('worker',result).get('state')
            return 0 if state in ('DUE','ENQUEUED','EXISTING','COMPLETE','NOT_DUE') else 2
        current = services.schedule_status(args.grant_id,db_path=args.db)
        print(json.dumps(current,ensure_ascii=True,indent=2))
        if args.command == 'schedule-status': return 0
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            raise ValueError('Interactive recurring administration required')
        action = {'schedule-activate':'ACTIVATED','schedule-pause':'PAUSED','schedule-revoke':'REVOKED'}[args.command]
        reason=input('Required reason (no credentials): ')
        challenge=args.command.removeprefix('schedule-').upper()+' '+args.grant_id+' '+current['fingerprint']+' '+str(current['event']['version'])
        if input('Type '+challenge+': ') != challenge: return 1
        services.schedule_change(args.grant_id,current,action,reason,db_path=args.db)
        print(action+'; no message sent')
        return 0
    except (ValueError, OSError, ledger.LedgerError) as exc:
        print('Schedule operation blocked: '+getattr(exc,'code',type(exc).__name__))
        return 3


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ReLttk Daily Streak Bot - Safe One-Shot CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config", "-c",
        default=DEFAULT_CONFIG_FILE,
        help="Path to JSON configuration file (default: streak.json)",
    )

    parser.add_argument("--db", help="Existing ledger path for send/status; never created by sending")
    parser.add_argument("--idempotency-key", help="Stable task key; reuse for the same task, new key for intentional repeat")
    parser.add_argument('--yes', action='store_true', help='Noninteractive send consent; never approves changed snapshots or selection skip')
    parser.add_argument('--request-id', help='Resume this existing request without selecting a new template')
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--send",
        action="store_true",
        help="Explicit opt-in to execute live message transmission (default is offline dry-run)",
    )
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicit dry-run mode (default)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Additional commands")
    ready = subparsers.add_parser('runtime-preflight', help='Non-mutating local runtime readiness; no network')
    ready.add_argument('--runtime-dir', required=True)
    ready.add_argument('--db', required=True)
    ready.add_argument('--config', required=True)
    ready.add_argument('--check-credentials', action='store_true')
    identity = subparsers.add_parser('identity-verify', help='Explicit authenticated-self bootstrap; default local preview')
    identity.add_argument('--db', required=True)
    identity.add_argument('--session', required=True)
    identity.add_argument('--live', action='store_true')
    identity.add_argument('--apply', action='store_true')
    for command in ('schedule-preview','schedule-authorize','schedule-activate','schedule-status','schedule-pause','schedule-revoke','schedule-tick'):
        admin=subparsers.add_parser(command,help='Bounded recurring authority; disabled until explicit activation')
        admin.add_argument('--db',required=True)
        if command in ('schedule-preview','schedule-authorize'):
            admin.add_argument('--config',required=True)
            admin.add_argument('--schedule-id',required=True)
            admin.add_argument('--time',default='08:00')
            admin.add_argument('--valid-from')
            admin.add_argument('--valid-through')
            admin.add_argument('--window-minutes',type=int,default=60)
            admin.add_argument('--daily-budget',type=int)
            admin.add_argument('--total-budget',type=int)
            admin.add_argument('--max-wait',type=int,default=300)
            if command=='schedule-authorize': admin.add_argument('--apply',action='store_true')
        else:
            admin.add_argument('--grant-id',required=True)
        if command=='schedule-tick':
            admin.add_argument('--operational-output',action='store_true',help='Bounded allowlist metadata; suppress raw stdout/stderr')
            admin.add_argument('--grant-fingerprint')
            modes=admin.add_mutually_exclusive_group()
            modes.add_argument('--enqueue',action='store_true')
            modes.add_argument('--execute',action='store_true')
            admin.add_argument('--yes',action='store_true')
    for command in ('worker-preview', 'worker-authorize', 'worker-run', 'worker-status', 'worker-revoke'):
        admin = subparsers.add_parser(command, help='Explicit finite worker authority; no enqueue or scheduler')
        admin.add_argument('--db', required=True)
        if command in ('worker-preview', 'worker-authorize'):
            admin.add_argument('--session', required=True)
            admin.add_argument('--request-id', action='append', required=True)
            admin.add_argument('--max-jobs', type=int, default=1)
            admin.add_argument('--max-wait', type=int, default=300)
            admin.add_argument('--expires-at', help='ISO timestamp with timezone; default next local midnight')
        else:
            admin.add_argument('--run-id', required=True)
        if command == 'worker-authorize':
            admin.add_argument('--apply', action='store_true', help='Interactive consent; default preview only')
        if command == 'worker-run':
            admin.add_argument('--manifest-fingerprint')
            admin.add_argument('--yes', action='store_true')
            admin.add_argument('--execute', action='store_true', help='Execute existing approved run; default read-only status')
    for command in ('queue-enqueue', 'queue-list', 'queue-run-once', 'queue-bind'):
        admin = subparsers.add_parser(command, help='Managed durable queue; preview by default')
        admin.add_argument('--db', required=True)
        if command in ('queue-enqueue', 'queue-bind'):
            admin.add_argument('--config', required=True)
        if command == 'queue-enqueue':
            admin.add_argument('--idempotency-key', required=True)
            admin.add_argument('--apply', action='store_true', help='Explicitly enqueue; never sends')
        if command == 'queue-bind':
            admin.add_argument('--request-id', required=True)
        if command in ('queue-list', 'queue-run-once'):
            admin.add_argument('--session', required=command == 'queue-run-once')
        if command == 'queue-run-once':
            admin.add_argument('--execute', action='store_true', help='Interactive bounded execution; default is offline preview')
            admin.add_argument('--max-jobs', type=int, default=1)
    for command in ('unknown-show', 'unknown-resolve'):
        admin = subparsers.add_parser(command, help='Offline Owner review; no automatic resend')
        admin.add_argument('--db', required=True)
        admin.add_argument('--request-id', required=True)
        if command == 'unknown-resolve':
            admin.add_argument('--action', choices=('KEEP_BLOCKED', 'CLOSE_WITHOUT_RESEND', 'AUTHORIZE_REPLACEMENT'))
    for command in ('request-show', 'request-cancel', 'request-approve-snapshot', 'rotation-skip-selection'):
        admin = subparsers.add_parser(command, help='Explicit request/rotation administration; no TikTok access')
        admin.add_argument('--db', required=True)
        if command == 'rotation-skip-selection':
            for field in ('account', 'conversation', 'campaign'):
                admin.add_argument('--' + field, required=True)
        else:
            admin.add_argument('--request-id', required=True)
        if command == 'request-approve-snapshot':
            admin.add_argument('--config', required=True)

    for command in ('breaker-status', 'breaker-history', 'breaker-reset'):
        admin = subparsers.add_parser(command, help='Offline circuit administration')
        admin.add_argument('--db', required=True)
        scope = admin.add_mutually_exclusive_group(required=True)
        scope.add_argument('--account')
        scope.add_argument('--session')

    for command in ("ledger-preflight", "ledger-initialize", "ledger-migrate"):
        admin = subparsers.add_parser(command, help="Explicit offline ledger administration")
        admin.add_argument("--db", required=True, help="Exact database path (no implicit default)")

    health = subparsers.add_parser('operational-status', help='Quiescent-only metadata status; no credentials/network')
    health.add_argument('--db', required=True)
    health.add_argument('--grant-id', required=True)
    health.add_argument('--operational-output', action='store_true')
    backup = subparsers.add_parser('ledger-backup', help='Explicit SQLite Backup API; never restore')
    backup.add_argument('--db', required=True)
    backup.add_argument('--destination', required=True)
    backup.add_argument('--operational-output', action='store_true')
    subparsers.add_parser("login", help="Interactive QR login to save a session")

    list_parser = subparsers.add_parser(
        "list-conversations",
        help="List conversations with Conv ID and Short ID from TikTok server",
    )
    list_parser.add_argument(
        "--session", "-s",
        required=True,
        help="Session name to use (required)",
    )

    subparsers.add_parser("status", help="Inspect local SQLite ledger records in readonly mode")

    probe_parser = subparsers.add_parser(
        "ws-probe",
        help="Handshake-only WebSocket check (connects and closes; never sends a message)",
    )
    probe_parser.add_argument("--session", "-s", required=True, help="Session name to use (required)")
    probe_parser.add_argument("--host", help="Override WS host, e.g. im-ws-sg.tiktok.com (im-ws*.tiktok.com only)")

    subparsers.add_parser("tui", help="Launch the Textual Terminal User Interface")
    capture_parser = subparsers.add_parser("capture-ws-auth", help="Windows-only browser auth setup for a saved session")
    capture_parser.add_argument("--session", "-s", required=True)

    args = parser.parse_args()

    # Reject mode flags with subcommands before any network activity
    if args.command is not None and (args.send or args.dry_run):
        parser.error("Mode flags (--send, --dry-run) cannot be combined with subcommands.")

    if args.command in ('operational-status', 'ledger-backup'):
        try:
            import services
            if args.command == 'operational-status':
                result = services.operational_status(args.grant_id, db_path=args.db)
            else:
                result = services.ledger_backup(args.db, args.destination)
            import operations
            operations.note(result)
            print(json.dumps(operations.metadata(result), separators=(',', ':')))
            return 0 if result['state'] == 'BACKUP_COMPLETE' else 2
        except Exception as exc:
            import operations
            reason = str(exc)
            result = dict(state='BLOCKED', reason=reason if reason in operations.REASONS else 'OPERATION_FAILED')
            operations.note(result)
            print(json.dumps(result))
            return 3
    if args.command in ('runtime-preflight', 'identity-verify'):
        return cmd_readiness_admin(args)
    if args.command and args.command.startswith('schedule-'):
        return cmd_schedule_admin(args)
    if args.command and args.command.startswith('worker-'):
        return cmd_worker_admin(args)

    if args.command in ('queue-enqueue', 'queue-list', 'queue-run-once', 'queue-bind'):
        return cmd_queue_admin(args)
    if args.command in ('unknown-show', 'unknown-resolve'):
        return cmd_unknown_admin(args)

    if args.command in ('breaker-status', 'breaker-history', 'breaker-reset'):
        return cmd_breaker_admin(args)
    if args.command in ("ledger-preflight", "ledger-initialize", "ledger-migrate"):
        return cmd_ledger_admin(args.command, args.db)
    if args.command in ('request-show', 'request-cancel', 'request-approve-snapshot', 'rotation-skip-selection'):
        return cmd_request_admin(args)
    if args.command == "login":
        return cmd_login()
    elif args.command == "list-conversations":
        return cmd_list_conversations(session_name=args.session)
    elif args.command == "status":
        return cmd_status(config_path=args.config, db_path=args.db)
    elif args.command == "ws-probe":
        return cmd_ws_probe(session_name=args.session, host=args.host)
    elif args.command == "tui":
        try:
            from tiktok_tui import TikTokTUI
        except ModuleNotFoundError:
            print("[!] Optional TUI dependencies missing: install requirements-tui.txt.")
            return 1
        TikTokTUI().run()
        return 0
    elif args.command == "capture-ws-auth":
        return cmd_capture_ws_auth(args.session)

    if args.send:
        interactive = sys.stdin.isatty() and sys.stdout.isatty()
        if not interactive and (not args.yes or not args.idempotency_key):
            parser.error('Noninteractive send requires --yes and an explicit --idempotency-key')
        return cmd_send(config_path=args.config, idempotency_key=args.idempotency_key,
                        request_id=args.request_id, confirm_request=confirm_snapshot if interactive else None,
                        **({"db_path": args.db} if args.db else {}))
    else:
        # Default behavior: offline dry-run
        return cmd_dry_run(config_path=args.config)


if __name__ == "__main__":
    if '--operational-output' in sys.argv:
        from operations import cli_entry
        sys.exit(cli_entry(main))
    sys.exit(main())
