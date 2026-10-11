# Phase5D G0 — Scanner and compatibility foundation

Task: phase5d-g0-scanner-compat-foundation  
Status: IMPLEMENT / OFFLINE TEST / REPORT complete; STOP before G1  
Date: 2026-10-11  
Local dev HEAD: e771161f416249cf0e16d64e20048b434ecf540d

## Scope and exact changed files

| File | Change |
| --- | --- |
| tests/test_ws_auth_boundary.py | Delegate its unchanged AST assertions to an approved-root scanner, including future relttk recursively |
| tests/test_legacy_send_closure.py | Require actual class implementation source before applying all existing AST refusal/sink assertions |
| tests/source_checks.py | New test-only source enumerator, preserved WS assertions and canonical implementation locator |
| tests/test_scanner_coverage.py | New eight scanner/canonical-source fixture cases |
| tests/test_source_layout.py | New ten fresh-process compatibility/path/output cases |
| docs/phases/PHASE5D_G0.md | This report |

No real relttk package or production alias was added. No Python production module was moved, renamed, deleted or edited. tests/run_offline.py was unchanged; its existing discovery and guard suffice. Requirements, schemas/migrations, samples, templates, deployment commands and accepted documentation remain unchanged.

Related approved design: [Phase5D source layout plan](PHASE5D_SOURCE_LAYOUT_PLAN.md). The Owner selected canonical relttk names and explicit legacy bootstrap; fresh external bare imports are not guaranteed automatically.

## Baseline and preservation

Initial guarded execution before G0 test edits:
390 total, 387 PASS, 3 SKIP, 0 FAIL/ERROR; 41.020 seconds, exit 0.

106 existing reviewed files were frozen. After G0, **104 remain byte-identical**. The only existing changed files are the two explicitly approved tests above. All 42 existing production Python files, 26 other existing test/support files, four requirements, two templates, sample JSON, LICENSE, .gitignore and 27 accepted Markdown documents are unchanged.

Every original WS AST assertion was transferred without semantic change: AST comparison of the complete original inner loop versus the helper loop PASS after renaming self to case. All legacy refusal, fail-before-WebSocket and raw-sink assertions remain. Production source unchanged includes identity, auth, Worker, FIFO/queue, quota/budget, consent and UNKNOWN logic.

SHA256 manifest and exact pre-edit bytes of the two edited tests are retained in ignored work/phase5d-g0-evidence/. These are reviewed test/source-hash evidence, not credentials or runtime artifacts.

HEAD and dev branch were verified through read-only metadata; no Git mutation. Existing uncommitted Phase5A/B/C-Lite/final-docs-tidy/Phase5D design remains intact.

## Scanner coverage

Explicit allowlist:
- Root *.py.
- core/, signers/, plugins/, deploy/, tests/, and future relttk/ recursively.

Private/ignored directories such as sesion, sessions, state, work, browser-profile(s), .git, .venv, venv and __pycache__ are pruned. Unknown top-level directories are excluded. Source-root or source-file symlinks are refused; nested symlink directories are not followed. No private JSON/session/browser/DB is read.

All 70 existing Python files remain in scanner discovery, plus the three new Python test/support files: **73 current paths**. There is no production relttk folder yet. Coverage does not depend on that directory appearing: fixture tests always create disposable nested canonical and alias paths and verify that harmless forbidden AST assignments are detected. No real or dummy credential value is added.

Canonical implementation selection:
- Current layout: repository/client.py.
- Once a relttk/transport directory exists: relttk/transport/client.py is required.
- inspect.getsourcefile(LttkClient) and module.__file__ must identify that exact path.
- The file must exist, be non-symlink and be enumerated by the scanner.
- A root wrapper cannot substitute for class-source inspection.

Existing AST checks then inspect the actual class methods with every original refusal/raw-sink assertion. This does not certify every possible secret pattern; it preserves the existing detection rules and expands their locations.

## New cases and meaningful coverage

| Module | Cases | Coverage |
| --- | --- | --- |
| test_scanner_coverage | 8 | Nested canonical canary; nested alias canary; old roots with absent future package; excluded private/unknown paths; future actual class source; wrapper substitution refusal; missing canonical source refusal; excluded canonical source refusal |
| test_source_layout | 10 | Alias-first identity/monkeypatch; canonical-first reload/class identity; single import execution; explicit/idempotent bootstrap; conflict refusal without overwrite; real pre-move file roots/environment capture; alternate-cwd synthetic dry-run; static resource consumers; corrupt future operational import; missing future operational import |

The compatibility package exists only inside disposable temporary directories in fresh guarded subprocesses. It demonstrates standard-library alias substitution with one canonical module object, cli.CONFIG_PATH and services/oneshot consumer patches, shared singleton state and class identity. Reload intentionally re-executes canonical code and creates a new class; both names still identify the same updated module. Conflict cases retain the existing sys.modules object. No sitecustomize, meta_path hook or process-global application import injection is installed.

Fresh subprocesses explicitly run the existing offline audit guard before application imports. Compatibility search-path changes are confined to those subprocess fixtures. Production main/operational_entry bytes are unchanged.

Path evidence:
- Real current runtime_paths.REPO and services.ROOT still point to the repository from an alternate cwd.
- Disposable TIKTOK_RUNTIME_DIR controls config/preferences/ledger/lock defaults; later environment changes do not replace captured defaults.
- QR session directory and client plugin discovery retain current repository anchors.
- Synthetic cwd streak.json is read by default dry-run; validation exit 1 is expected, no state directory created.
- Client legacy auth/state expressions, TUI ROOT/main.py/cwd and renderer anchor/operational entry are checked statically without accessing their private resources.
- Copied actual operational_entry mutes before a synthetic operations module prints and imports a missing/corrupt future package. Both fail with status 3 and empty stdout/stderr.
- Existing operations tests still cover metadata allowlists and copied-bootstrap missing-module cases.

## Verification results

Command: `./work/verify-venv/Scripts/python.exe -B tests/run_offline.py`

```text
Ran 408 tests in 42.232s
OK (skipped=3)
Offline guard: external network and real runtime files blocked.
```

**408 total, 405 PASS, 3 SKIP, 0 FAIL/ERROR; exit 0.**
Exactly 18 additional cases reconcile 390 -> 408; no former case removed.

The same three skips remain: POSIX permission checking on Windows, and two operations WAL tests requiring SQLite setconfig/no-checkpoint-on-close capability missing from this Python 3.10 build. No added test skips and no weakened guards/assertions.

| Additional check | Result |
| --- | --- |
| Focused scanner/layout/WS/legacy closure | 32 tests, all PASS; no SKIP; 2.342 seconds |
| AST Python 3.10.11 | All 73 Python files PASS |
| AST Python 3.13.3 | All 73 Python files PASS |
| Guarded imports | 14 modules PASS, including new source_checks |
| Help-only smoke | main --help, worker-run --help, schedule-tick --help, ws-probe --help: 4 PASS |
| Original WS assertion loop comparison | Equivalent AST PASS |
| Source discovery preservation | All 70 previous Python paths included; 73 current scanned paths |
| Existing frozen hashes | 104/106 unchanged; only approved two tests differ |

Guarded imports: main, services, oneshot, ledger, ledger_requests, ledger_migrations, queue_service, worker, scheduling, identity_service, readiness, operations, deploy.render_units, source_checks. Import/help checks install the existing guard first and suppress captured output. Asyncio slow-task diagnostics occurred during full runs but no failure.

Full Python 3.13 dependency/suite certification is not claimed; only AST checks were requested/run on that interpreter.

## Limits and mandatory G1 follow-up

These fixtures prove a proposed mechanism in isolation and pre-move contracts, **not that actual future relocation works**.
- G1 must preserve repository anchors and default/environment evaluation using real moved config/log/runtime_paths.
- Later groups must prove canonical/legacy module identity for real services/transport, optional dependencies, all public consumers and fresh external bootstrap.
- Client auth/state, TUI child paths and renderer resources have static G0 coverage plus unchanged existing regression coverage; their real relocated path resolution/missing-resource behavior needs focused runtime fixtures before those groups are accepted.
- If relttk/transport exists without client.py, closure checks fail deliberately. Stage creation must not create a partial transport group and then bypass this failure.
- No actual alias bootstrap is implemented now; simultaneous import/reload edge cases on real modules and the proposed future packaging remain implementation acceptance work.
- Debian 13 permissions, locking, native dependencies and SQLite WAL capability need separate Owner fixture evidence.
- Identity Contract remains BLOCKED; unofficial TikTok API/real server echo/streak recognition are unverified.

No blocker occurred within G0. G1 is neither started nor implicitly approved by this PASS.

## Rollback

Owner-approved rollback restores only tests/test_ws_auth_boundary.py and tests/test_legacy_send_closure.py from work/phase5d-g0-evidence/ before bytes, and removes only the three new test/support files and this new report after checking exact workspace-contained paths and expected hashes. Keep every prior Phase5 change. Do not use Git reset/clean or touch production/runtime data. Re-run the original guarded baseline afterward. No rollback was executed.

Sanitized initial/final test trailers are retained locally and published through C2C execution evidence; raw transcript/private material is excluded.

STOP REPORT. Await independent Technical Owner review and explicit Owner approval before G1 or any production source relocation. No Git/SSH/VPS/systemd/live TikTok action.

