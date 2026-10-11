# Phase5D G3 — Transport relocation

Task: phase5d-g3-transport; date 2026-10-11. IMPLEMENT / OFFLINE TEST / REPORT complete. STOP before G4. Accepted baseline: 423 total, 420 PASS, 3 SKIP, 0 FAIL/ERROR.

## Exact move and file scope

| Before | Canonical implementation |
| --- | --- |
| client.py | relttk/transport/client.py |
| oneshot.py | relttk/transport/oneshot.py |
| qrlogin.py | relttk/transport/qrlogin.py |
| ws_auth_capture.py | relttk/transport/ws_auth_capture.py |

All four root implementations are absent. Added inert relttk/transport/__init__.py and four fixed-target aliases under relttk/compat/legacy/ with the original filenames. No G4/G5 module moved.

The four implementations change only imports and the necessary repository anchors. Client/QR import REPO from relttk.runtime_paths; client global-auth/plugin/message-state paths and QR sesion path use str(REPO) where their old file parent was used. Obsolete relative core references point to existing root core; existing try/except import branches remain. Session/auth/capture sibling imports use canonical transport names. No auth validator, WS URL algorithm, packet, echo, transmission, retry, UNKNOWN, session-write or plugin behavior changed.

Import-only consumers: main.py, root __init__.py public export, relttk/application/cli.py, services.py, tui.py, queue_service.py, worker.py, readiness.py. The latter modules remain at their existing paths and retain all algorithms. No scheduling/ledger/identity implementation changed.

Other edited files: relttk/compat/__init__.py adds four targets; tests/test_source_layout.py inspects canonical client source and the equivalent explicit state anchor; tests/test_ledger_v2.py applies the existing destructive-repeat assertion to canonical oneshot source; docs/architecture/MODULES.md describes actual G3. Added tests/test_transport_layout.py and this report. All original security assertions and guarded runner remain.

## Import and alias evidence

| Canonical module | Eager internal dependencies | Lazy dependencies retained |
| --- | --- | --- |
| transport.client | core, relttk.config, log, runtime_paths | Canonical QR/session helpers at existing call sites. |
| transport.oneshot | client, qrlogin, config/log, core.api/proto, main, ledger, ledger_requests, circuit_breaker, queue_service | Existing managed workflow delegates unchanged. |
| transport.qrlogin | core.api, core.signer_client, config/log, runtime_paths | Canonical capture helper and optional qrcode. |
| transport.ws_auth_capture | None | Canonical QR/oneshot and optional Playwright at explicit capture call sites. |

Root __init__.py exports canonical LttkClient. main/application/queue/worker/readiness consumer imports were changed at their existing eager/lazy points. The normalized eager import graph covers 46 implementation/support modules including the new inert transport package. Only client -> runtime_paths and qrlogin -> runtime_paths edges were added, for repository anchors. Neither has a return path; no new eager cycle. Static graph resolves the root public export, but does not infer all relative/dynamic/plugin edges; guarded actual imports provide additional evidence.

Explicit relttk.compat.enable() provides client/oneshot/qrlogin/ws_auth_capture as the same canonical objects. Tests prove actual legacy-first/canonical-first identity, shared LttkClient and oneshot class reference, public export, UnsupportedSafetyOperation/_BotStop/_BotRestart identity and pickle round-trip, and QR stop-event identity. A module-execution profile verifies exactly one initialization per transport implementation across both name families.

The oneshot alias uses G2 CLI's existing provisional-shim pattern: remove only its own temporary alias while importing canonical oneshot, restore on failure, install the canonical object on success. This avoids main's repeated bootstrap treating an in-progress alias as a conflicting module. G1/G2 aliases/bootstrap conflict refusal remain; no global import hook or permissive fallback introduced. Bare aliases require explicit bootstrap; canonical imports and official entries remain the supported paths. Consumers need the repository root on sys.path. Ordinary copied from-import bindings retain Python semantics, including across monkeypatch/reload.

## Safety and path evidence

Actual session-bound auth preparation is exercised through a legacy oneshot patch and canonical consumer: matching ttwid is used, input cookies are not mutated, session value is absent from the generated URL, and missing/invalid auth refuses before WebSocket. Existing full auth boundary regressions retain wrong-binding, key/ttwid validation and URL/config injection refusal. No upstream key/fallback exists or was reintroduced; no secret literal is reproduced here.

Packet builder patches are visible through both client and oneshot names. QR load_session patches are observed by canonical LttkClient construction with synthetic session data. Existing packet/snapshot/correlated echo tests pass; SUCCESS criteria remain a correlated server echo, not recipient delivery/read proof.

Repository plugins and QR sesion anchors are asserted from a disposable alternate cwd. Synthetic TIKTOK_RUNTIME_DIR tests verify session/auth paths, absence of legacy global-auth fallback with explicit runtime root, and missing synthetic auth. Legacy global-auth and message-DB anchors are tested with existence/SQLite/mkdir mocks, without runtime file access. Existing private-root/traversal/symlink/permission regressions remain unchanged.

Seven existing guarded legacy entrypoints (send_message, send_video, send_reaction, delete_message, delete_message_everyone, remove_reaction, run) continue to refuse before attributes, auth, packet generation or socket effects. Their actual canonical class AST is inspected by the unchanged source_checks.client_implementation helper, which already requires the transport path when that directory exists. Existing sink inventory assertions remain unchanged. Moving modules does not expand Safety Layer coverage to every retained low-level read/mutation/helper API.

Optional dependency regressions prove missing websockets refuses client import; missing Playwright refuses capture before browser launch; unavailable qrcode follows the existing warning path with synthetic URL. No dependency installed. Existing UI/CLI optional behavior passes as part of full regression.

Scanner discovery includes all four actual implementations, aliases and initializer. It cannot substitute an alias file for the actual LttkClient definition. Synthetic canary, missing canonical source and excluded-source tests remain. operational_entry.py and tests/run_offline.py are byte-identical; operational mute-before-import, missing/corrupt import silence, metadata and admission regressions remain green. Identity Contract stays BLOCKED.

## Tests and validation

Ten added actual G3 tests explain 423 -> 433:

1. Legacy-first identity for four modules, client class/exceptions and QR stop-event.
2. Canonical-first identity and root public LttkClient export.
3. Inert transport/bootstrap and one execution of each implementation across aliases.
4. Auth/packet patches, matching synthetic pair and no WS on missing/invalid auth.
5. QR/session patch observed by canonical client construction.
6. Repository/synthetic private paths from alternate cwd, without legacy fallback.
7. Legacy global-auth/message-DB repository anchors with mocked I/O.
8. Missing optional transport/browser/QR dependencies fail before effects.
9. Existing legacy live-path refusals before auth/packet/socket access.
10. Scanner reaches actual canonical class and every alias.

First focused run: **127 total, 124 PASS, 3 SKIP, 0 FAIL/ERROR**, 16.815s, exit 0. Includes actual G3/G2/G1/G0, WS security, legacy closure, independent review, private runtime paths, safety, operations and ledger-repeat assertions. No intermediate failure or corrective retry in G3.

Final full guarded command:

```text
./work/verify-venv/Scripts/python.exe -B tests/run_offline.py
Ran 433 tests in 50.369s
OK (skipped=3)
Offline guard: external network and real runtime files blocked.
```

**433 total, 430 PASS, 3 SKIP, 0 FAIL/ERROR; exit 0**, Windows/Python 3.10.11. Same accepted skips: POSIX permissions on Windows and two SQLite setconfig/no-checkpoint-on-close capability cases. No new skip, deleted assertion or weaker guard. All network/session/DB inputs are disposable fixtures or mocks; no TikTok traffic.

AST all 90 Python files PASS on Python 3.10.11 and 3.13.3. Guarded fresh-process imports: 20 PASS. Help-only checks: 8 PASS (main, worker-run, schedule-tick, ws-probe, login, capture-ws-auth, canonical application CLI and canonical WS capture). These checks ran from a disposable alternate cwd with the existing audit guard installed before imports. Markdown links/anchors are validated separately in links.json.

Supported root main.py commands remain. Direct execution of removed root client/oneshot/qrlogin/capture files is no longer supported; use root main dispatch, or canonical module help from repository root. Help examples do not authorize real capture/login or traffic. Historical Termux diagnostic wording remains unchanged by this bounded source move; Debian 13 is the sole future staging target.

## Preservation and rollback

123 reviewed current files were frozen against accepted G2 after hashes before mutation. At mapped destinations, **107 remain byte-identical; 16 authorized existing-file changes** are the four implementations, eight import/public consumers, compatibility target list, two source-path tests and MODULES. Seven new files: transport initializer, four aliases, focused test and report. Reviewed final manifest: 130 files. Python inventory: 90 (root 17, core 5, signers 3, plugins 6, deploy 1, tests 34, relttk 24).

Non-import AST equivalence PASS for all 12 changed implementation/import-consumer files, after normalizing only the explicit client/QR anchor expressions. Tests inspecting canonical sources retain every original security assertion. G1/G2 historical reports and unrelated files, requirements, templates, schema/migration/queue/identity/rotation logic and accepted evidence remain untouched. No application source change followed full-suite completion; subsequent edits were documentation/evidence only.

Before/after SHA256 manifests, exact before bytes, move/consumer maps, preservation lists, eager graph, AST/import/help results and sanitized test completion evidence reside under ignored work/phase5d-g3-evidence/. No runtime file is an input to these artifacts.

Owner-authorized rollback must restore the four original root implementations together with all edited consumers, public export, compatibility target list, two tests and MODULES from the frozen accepted G2 snapshot. Remove only G3-added files after verifying workspace containment/hashes; preserve all G1/G2 and earlier work. Restart interpreters, rerun the guarded 423-test baseline and verify roots/scanner/import identities. Do not use Git reset/clean or touch runtime data. No rollback executed.

## Limits and stop

Native Debian 13 dependency builds, permission/locking/WAL behavior and full Python 3.13 regression remain unverified. Import/AST success is not production readiness. No Identity Contract bypass, UID/routing/fingerprint guesses, consent/budget changes, UNKNOWN retransmission or auth bootstrap introduced. Retained low-level legacy helpers are not newly certified safe for live use by this relocation.

TikTok API is unofficial; correlated echo is server acknowledgment and bot streak credit remains unverified. Previously published Git history may retain the old upstream literal; no credential displayed or history rewritten.

No real credentials/cookies/sessions/browser profiles/runtime DB/private captures, live TikTok, Git mutation, SSH/VPS/systemd or G4/G5 execution. STOP REPORT for independent Technical Owner review; do not start G4.
