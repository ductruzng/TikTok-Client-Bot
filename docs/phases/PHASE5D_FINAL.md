# Phase5D G6 — Final source-layout verification

Status: REPORT; independent Technical Owner acceptance pending.
G1–G5 were previously accepted. G6 changes documentation only.
Debian 13 is the sole staging target; Termux/Android remains retired.

## Result and exact scope

All 22 approved implementations are present at their canonical relttk locations,
with 22 fixed aliases under relttk/compat/legacy. Their original root filenames
are absent. Both import orders were checked in guarded fresh processes: all 44
canonical/legacy pairs share identity. Aliases contain one fixed import target;
they are not duplicate implementations or generic import hooks.

Only README.md and docs/architecture/MODULES.md changed, and this report was added.
No application, test, dependency, schema or deployment-template file changed.
The current guide corrects stale test-filename references introduced by earlier
documentation path replacement, and distinguishes historical baselines from
current verification. Historical phase reports remain byte-identical.

Before editing, all 149 accepted G5 reviewed files matched SHA-256 hashes. Their
exact bytes were frozen under ignored work/phase5d-g6-evidence/before. Final
preservation must show 147 byte-identical paths, two changed documents and one
new report: 150 reviewed files. This manifest covers reviewed project files,
not private/ignored runtime artifacts or an exhaustive Git inventory. No Git
operations were performed during G6.

## Actual tree and contracts

```text
root/                           5 Python files
  main.py                      supported CLI/default offline plan
  operational_entry.py         mute-before-import operational entry
  __init__.py                  retained legacy client export
  browsercookies.py            REVIEW-only manual Windows tool
  test_ws_capture.py           REVIEW-only manual diagnostic
  relttk/                      51 Python files including aliases/initializers
    config.py / log.py / runtime_paths.py / operations.py
    application/               cli, services, tui
    transport/                 client, oneshot, qrlogin, ws_auth_capture
    storage/                   ledger, ledger_requests, ledger_migrations, queue_service
    runtime/                   worker, scheduling, rotation, unknown_resolution
    identity/                  circuit_breaker, identity_service, readiness
    compat/legacy/             22 fixed aliases
  core/                        5 Python files
  signers/                     3 Python files
  plugins/                     6 Python files
  deploy/                      1 Python renderer and retained templates
  tests/                       36 Python files
  docs/                        architecture, operations, security, evidence, phases, archive
```

Total: 107 Python files. Root Python count fell from 27 to five through G1–G5;
total file count increased for explicit compatibility and regression coverage.
This is organization, not a claim of reduced coupling or removed runtime code.
The two manual tools have not been proved unused and were neither moved nor
deleted. Root source clutter needs no further action within approved Phase5D.

External consumers should use canonical imports with repository root on sys.path.
Bare imports require explicit relttk.compat.enable() in each process. Supported
entrypoints and guarded runner establish compatibility themselves. Old moved
filenames are not standalone scripts. Copied function bindings retain ordinary
Python behavior; aliases do not promise magical patching of copied references.
Canonical initializers remain inert and compatibility rejects conflicting modules.

Managed source has no remaining bare imports of the relocated names. Core,
signers, plugins and deploy remain in place; dynamic/lazy edges remain documented
and are not refactored. Current physical paths are in the module map; conceptual
diagram names and historical phase filenames need not become filesystem paths.

Private roots remain unchanged: runtime_paths.REPO is the repository root;
services.ROOT, QR sesion path, ledger defaults, plugin directory and renderer
template root retain accepted behavior. Ledger/config defaults still capture at
their existing import times. main's configuration path keeps cwd semantics.
No session, auth, state, database/WAL, cache or browser profile was inspected or
relocated. Path and environment behavior is checked on disposable fixtures only.

## Offline verification

Full guarded regression: **451 total, 448 PASS, 3 SKIP, 0 FAIL/ERROR**,
63.052 seconds, exit 0. Count and skips exactly match accepted G5; no test changes.
The three skips are actual POSIX permissions and two SQLite setconfig/no-checkpoint
WAL capability cases unavailable on this Windows/Python 3.10 fixture.

Additional verified checks:

- All 107 Python files parse on Python 3.10.11 and 3.13.3.
- 22 canonical moves and fixed alias targets verified; 44 alias identities pass
  across both import orders in guarded fresh interpreters.
- 25 guarded fresh module imports and 11 CLI help commands pass from alternate cwd.
- Recursive source scanner discovers all 107 Python files, including canonical
  implementations and aliases; existing WS credential/TLS static checks pass.
- AST audit finds zero bare imports of moved names in managed source.
- Existing full-suite regressions retain module single-initialization/patch tests,
  private anchors/import-time capture, operational silent failures, metadata
  allowlists, WAL backup refusal/history, FIFO, concurrency, UNKNOWN, quota,
  identity BLOCKED, budgets, consent ABA and wait/admission gates.
- Current guide test-filename references point to existing files. Markdown local
  link/anchor checks are recorded in work/phase5d-g6-evidence/links.json.

The guarded runner blocks external network and real runtime-file access before
application imports. Synthetic WS frames and temporary SQLite fixtures do not
exercise TikTok. Evidence includes audit.json, mapping.json, preservation.json,
before/after-hashes.json and sanitized-tests.txt in the ignored evidence directory.
Only sanitized execution output is published through C2C.

## Debian staging readiness and remaining blockers

The reviewed tree is ready for Owner-operated **offline fixture evaluation**;
it is not certified for native Debian operation or live sending. Before accepting
Debian 13/Python 3.13, verify dependency installation/builds (including lz4), full
guarded coverage with required optional test dependencies, actual POSIX ownership,
permissions/symlink refusal, process locking, and SQLite no-checkpoint WAL backup
capabilities. More optional-dependency skips would not match this baseline.
No package installation, service activation or Debian deployment was performed.

Identity Contract is still BLOCKED: authenticated-self UID provenance remains
unverified. No auth bootstrap, routing guess, identity bypass or live test is
authorized. Existing legacy low-level helpers outside managed Safety Layer,
optional Windows diagnostics and disabled plugin surfaces remain review items;
file relocation does not eliminate them. Static scanners detect particular
patterns, not every possible credential. Previously published Git history may
retain the removed upstream key; history remediation requires separate Owner
authorization and was not attempted.

TikTok APIs are internal/unofficial. Correlated echo supports server acknowledgment,
not recipient delivery/read status or TikTok streak credit. None of these live
outcomes has been verified here.

## Rollback and acceptance boundary

G6 rollback restores just README.md and MODULES.md from the accepted G5 snapshot
and removes only this reviewed new report after checking the exact workspace
path. No source or runtime rollback is required. Earlier source groups must be
rolled back coherently using their individual reports/snapshots, not a mixture of
canonical and root implementations. Preserve unrelated Owner changes; no broad
Git reset/clean or recursive deletion is authorized.

STOP at REPORT. Owner commits/pushes manually after independent review. No
automatic next phase, deployment, systemd activation, migration or live sending.
