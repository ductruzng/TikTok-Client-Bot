# Phase5C-Lite — Architecture documentation

Task: phase5c-lite-architecture-documentation  
Date: 2026-10-11  
Scope: approved documentation-only implementation, existing local dev clone  
Starting HEAD: e771161f416249cf0e16d64e20048b434ecf540d, branch dev

## Deliverables and exact project changes

- CREATE [docs/architecture/MODULES.md](../architecture/MODULES.md): current module map, runtime flow, import/path contracts, safety-test coverage, maintenance and Debian fixture boundaries.
- UPDATE [README.md](../../README.md): one architecture link under Documentation; all previous text preserved.
- CREATE PHASE5C_LITE.md: this implementation, verification and rollback report.

No Python/test/requirements/template/schema/JSON/.gitignore edits. No file moves or deletions. Existing uncommitted Phase5A and Phase5B work is retained. Read-only Git HEAD/branch/status inspection was used to verify the baseline; no Git mutation was performed.

## Architecture summary

The guide documents the current root modules and core/signers/plugins/tests/deploy paths, not the proposed Phase5B packages. It distinguishes CLI/application dispatch, operational output suppression before imports, durable queue/SQLite admission, finite manifests/recurring grants and managed snapshot transport.

The potential 21-module SCC includes lazy/entry imports; there is no module-level internal SCC in the audited graph. Moving files alone would not remove coupling. Existing WS/legacy-send scanners inspect particular directories and actual implementation files; a new namespace requires explicit coverage and canonical module-identity review.

Identity Contract stays BLOCKED. Debian 13 is the sole future staging target. Templates are offline artifacts; neither rendering nor successful fixture tests authorizes activation or live sends. Server echo is a server acknowledgment, not verified recipient delivery or streak credit.

## Verification evidence

SHA256 freeze and final comparison: **102 existing files unchanged**, excluding the explicitly authorized README change. This covers all 70 tracked Python files (including tests), all four requirements, both unit templates, sample JSON/LICENSE, .gitignore, accepted Phase5A/5B documents and security evidence. The per-file manifest is retained locally in work/phase5c-lite-evidence/frozen-hashes.json. Source locations/import names and runtime behavior are unchanged.

README validation proves its only textual delta is the new architecture link; prior accepted text and links remain intact. HEAD/branch remain the starting dev base. No source/test file was changed to make checks pass.

| Check | Result |
| --- | --- |
| AST under Python 3.10.11 | 70 files PASS |
| AST under Python 3.13.3 | 70 files PASS |
| Guarded imports under Python 3.10.11 | 13 modules PASS |
| Guarded CLI help | main --help, worker-run --help, schedule-tick --help, ws-probe --help: 4 PASS |
| Markdown paths/anchors/fences | 26 reviewed Markdown files; 77 local links, including 3 heading anchors and 1 directory target; zero errors |
| Full guarded suite under Windows/Python 3.10.11 | 390 total, 387 PASS, 3 SKIP, 0 FAIL/ERROR; 43.867 seconds; exit 0 |

The 13 imported modules were main, services, oneshot, ledger, ledger_requests, ledger_migrations, queue_service, worker, scheduling, identity_service, readiness, operations and deploy.render_units. The existing tests/run_offline.py audit hook was installed before imports/help; stdout/stderr were captured for these smoke checks. No live commands were executed.

Full-suite command: `./work/verify-venv/Scripts/python.exe -B tests/run_offline.py`

```text
Ran 390 tests in 43.867s
OK (skipped=3)
Offline guard: external network and real runtime files blocked.
```

No count/skip deviation from the accepted baseline. The unchanged three skips are test_runtime_paths POSIX permissions on Windows and test_operations actual WAL no-checkpoint backup/persistent WAL tests requiring sqlite3 setconfig capability absent in this Python 3.10 build. No tests or guards were weakened. Python 3.13 AST success is not a full-suite/dependency certification.

The link checker initially had an escaping defect, causing its README-only-delta assertion to fail; correcting the checker passed without further README changes. This was a validation-script issue, not an application regression. Asyncio slow-task diagnostics appeared in the suite output; the runner completed successfully. Only the sanitized completion trailer is published as execution evidence; no sensitive/raw transcript is included.

Local sanitized test evidence: work/phase5c-lite-evidence/sanitized-tests.txt. Link results: work/phase5c-lite-evidence/links.json. Original Phase4 and Phase5A evidence remains unchanged.

## Remaining risks and REVIEW-only tools

- Debian 13/Python 3.13 native dependencies, permissions, locking and WAL behavior remain unverified on the Windows fixture.
- Unofficial TikTok API behavior and live account identity/transport remain unverified; no real credentials/session/runtime database was read.
- Lazy cross-module coupling, import-time default paths, cwd assumptions, patch targets and dynamic plugin consumers remain unchanged.
- browsercookies.py, test_ws_capture.py and optional requirements/windows.txt workflows remain REVIEW-only. No deletion is authorized. Unsupported fyp2 legacy helper references remain an audit issue.
- Published history may retain the removed upstream key; no literal is reproduced and no history remediation or credential revocation is claimed.

## Rollback

Rollback is documentation-only: restore README bytes from the local reviewed backup work/phase5c-lite-evidence/README.before.md, then remove only docs/architecture/MODULES.md and PHASE5C_LITE.md after explicit Owner authorization. Preserve all pre-existing Phase5A/Phase5B source/documentation changes. Do not use git reset/clean, alter schemas or touch runtime data.

Ignored local verification artifacts are retained under work/phase5c-lite-evidence/. They contain only documentation backup, hashes and sanitized completion evidence; they are not source-package deliverables or sensitive runtime artifacts.

STOP at REPORT. Await Technical Owner and Product Owner review before further source work, Git commit/push or Debian staging.
