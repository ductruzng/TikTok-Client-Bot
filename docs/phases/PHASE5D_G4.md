# Phase5D G4 — Safety, storage and runtime relocation

Status: IMPLEMENT → OFFLINE TEST → REPORT complete; independent Owner review pending.
G5/G6 are not implemented. This report does not authorize deployment or sending.

## Scope and file changes

Eleven implementations moved as one group:

| Previous root module | Canonical implementation |
|---|---|
| ledger.py | relttk/storage/ledger.py |
| ledger_requests.py | relttk/storage/ledger_requests.py |
| ledger_migrations.py | relttk/storage/ledger_migrations.py |
| queue_service.py | relttk/storage/queue_service.py |
| worker.py | relttk/runtime/worker.py |
| scheduling.py | relttk/runtime/scheduling.py |
| rotation.py | relttk/runtime/rotation.py |
| unknown_resolution.py | relttk/runtime/unknown_resolution.py |
| circuit_breaker.py | relttk/identity/circuit_breaker.py |
| identity_service.py | relttk/identity/identity_service.py |
| readiness.py | relttk/identity/readiness.py |

Three package initializers are inert. Eleven fixed-target aliases were added under
relttk/compat/legacy, with eleven entries in relttk/compat/__init__.py. Explicit
compatibility bootstrap gives old and canonical imports the same module object,
globals, exception classes and monkeypatch targets. There are now 21 aliases total.

Canonical import updates affect the moved implementations except rotation.py,
plus core/api.py, core/self_identity.py, main.py, operations.py,
deploy/render_units.py, relttk/application/cli.py,
relttk/application/services.py and relttk/transport/oneshot.py: 18 files in total.
rotation.py is a byte-identical relocation. operations.py remains at root.
Ledger's repository anchor now uses relttk.runtime_paths.REPO; its captured
environment/default state, ledger and lock paths preserve first-import semantics.
Other production edits are imports only, retaining their eager/lazy positions.

tests/test_ledger_v2.py now inspects canonical source paths. Its crash subprocess
installs the existing offline audit guard and compatibility bootstrap before
imports; original crash assertions remain. tests/test_safety_layout.py adds ten
regressions. docs/architecture/MODULES.md reflects the actual layout.

## Preconditions and preservation

Before editing, all 130 files in the accepted G3 reviewed manifest matched their
SHA-256 hashes, the three destination packages were absent, and the existing
recursive source scanner discovered synthetic G4 package/alias paths.
A byte-for-byte rollback snapshot was saved in the ignored local directory
work/phase5d-g4-evidence/before, with before-hashes.json and moves.json.
Only reviewed files were read; real sessions, credentials and runtime databases
were not accessed. The snapshot is source evidence, not a database backup.

No schema, migration, transaction, queue, FIFO, quota, cooldown, snapshot,
idempotency, UNKNOWN, budget, circuit-version, identity, recurring-consent or
wait/admission algorithm changed. Schema version remains 8. Official entrypoints,
the operational import-muting boundary and the guarded suite runner remain.
Identity Contract remains BLOCKED. No Git writes, deployment, systemd operations,
live TikTok traffic or production migrations were performed.

The normalized static eager-import graph contains 49 modules. Its sole additional
edge is ledger → runtime_paths for the repository anchor, without a return path
or new eager cycle. Static analysis does not cover all dynamic/plugin imports;
guarded fresh imports supplement it.

## Verification

Full guarded suite: **443 total, 440 PASS, 3 SKIP, 0 FAIL/ERROR**, exit 0,
52.784 seconds. Accepted G3 baseline: 433 total, 430 PASS, 3 SKIP, 0 FAIL/ERROR.
The ten additional cases account for the increase.

Focused suite: **243 total, 241 PASS, 2 SKIP, 0 FAIL/ERROR**, exit 0,
33.620 seconds. The initial focused invocation had two nonexistent module labels
and three crash-subtest failures caused by the missing compatibility bootstrap in
the existing subprocess. Correcting the invocation and installing the existing
guard before subprocess imports resolved these harness issues; no product
algorithm or original assertion was changed.

Additional checks:

- All 105 Python files parse on Python 3.10.11 and 3.13.3.
- 30 guarded fresh-process import smoke checks and ten CLI help checks pass.
- Non-import AST equivalence passes for all 18 changed implementation/consumer
  files, allowing only the ledger repository-anchor expression described above.
- New tests cover both import orders for all eleven aliases, exactly one module
  initialization, exception identity/serialization/inheritance, patch visibility,
  alternate cwd and captured defaults, scanner coverage, disposable WAL
  commit/rollback, legacy RunLock recognition, UNKNOWN crash recovery,
  idempotency and missing-database refusal.
- Existing guarded regressions continue to cover FIFO/atomic claims, consent,
  budget, circuit versions, wait gates and fail-closed identity/admission.

Sanitized execution summary, manifests and verification metadata are stored under
work/phase5d-g4-evidence. Raw execution output is not published through C2C.

## Rollback and limits

Rollback must restore the entire G4 group together: restore the eleven root
implementations and changed consumers from the verified G3 snapshot, remove only
the explicit new G4 paths, and restore compatibility mappings and documentation.
Do not use broad cleanup/reset operations or touch runtime data. Restart Python
processes and rerun the guarded G3 baseline before accepting rollback. This is a
source rollback; no runtime database rollback is needed or authorized.

The full suite ran on Windows/Python 3.10. Python 3.13 AST validation is not a full
runtime compatibility claim. Native Debian/POSIX behavior and live authentication
remain unverified. Existing skips remain; low-level legacy helpers outside the
managed Safety Layer remain a previously documented risk. The bot uses unofficial
TikTok internal APIs. A correlated server echo does not prove recipient delivery
or that TikTok credits a streak.

STOP at REPORT. Independent Owner review is required before G5/G6.
