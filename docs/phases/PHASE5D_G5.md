# Phase5D G5 — Operations relocation

Status: IMPLEMENT → OFFLINE TEST → REPORT; independent Owner review pending.
Accepted G4 baseline: 443 total, 440 PASS, 3 SKIP, 0 FAIL/ERROR.
G6 is not implemented or authorized by this report.

## Changes and preservation

- operations.py moved to relttk/operations.py, byte-identical to accepted G4.
- relttk/compat/legacy/operations.py is a fixed alias to relttk.operations;
  relttk/compat/__init__.py adds that target, making 22 explicit aliases total.
- main.py, operational_entry.py and relttk/application/services.py replace only
  operations imports with canonical imports, at their original execution points.
- tests/test_operations_layout.py adds eight guarded regressions.
- Two existing negative fixtures in tests/test_source_layout.py now inject their
  synthetic faults at the canonical operations path. Original return-code and
  empty-output assertions are retained.
- docs/architecture/MODULES.md reflects G5, with root 5, core 5, signers 3,
  plugins 6, deploy 1, tests 36 and relttk 51: 107 Python files.

Before editing, all 146 reviewed G4 paths matched their accepted SHA-256 hashes;
canonical and alias destinations were absent. Exact reviewed bytes were saved
under the ignored work/phase5d-g5-evidence/before directory, with before-hashes.json.
No runtime files were included in this source-only rollback snapshot. Final
preservation: 140 byte-identical mapped paths, six changed existing paths and
three new reviewed files; 149 reviewed files in the resulting manifest.

Operations has no module-level project imports or __file__-based root. Its lazy
canonical dependencies, metadata allowlists, captured result, backup/status,
SQLite/WAL capability refusal, writer reservation and run-lock behavior are
unchanged. Non-import AST equivalence passes for the three consumer files.
The relocation adds no eager project dependency or import cycle.

operational_entry still suppresses Python stdout/stderr and native descriptors
before importing compatibility, operations and main. Canonical import failure
returns status 3 silently; normal dispatch emits only its existing bounded
allowlisted envelope. Missing databases are not created by status.

Schema version remains 8. Identity Contract remains BLOCKED. No FIFO, claim,
UNKNOWN, quota, cooldown, circuit, budget, snapshot or consent behavior changed.
No dependency, deployment template, runtime path or schema was modified.

## Offline evidence

Final full-suite results are in the sanitized execution record and
work/phase5d-g5-evidence/sanitized-tests.txt. Verified final full suite: **451 total, 448 PASS, 3 existing SKIP, 0 FAIL/ERROR**,
64.655 seconds, exit 0. The delta is exactly eight new tests.

Focused: 39 total, 37 PASS, 2 SKIP, 0 FAIL/ERROR, 7.220 seconds, exit 0.
All 107 Python files parse on Python 3.10.11 and 3.13.3. Five guarded fresh
imports and four CLI help commands pass from a disposable alternate cwd.

New tests cover alias-first and canonical-first shared identity, one module
initialization, shared monkeypatch/metadata state through application services,
conflict refusal, silent missing/corrupt/noisy canonical imports, missing-database
status without creation, unchanged repository root, explicit disposable backup,
history/integrity preservation, overwrite refusal and recursive source coverage.
Existing operations/deployment/safety regressions remain, including WAL capability
gates, competing backup processes, crash-marker recovery, Identity BLOCKED,
signal handling and refusal of unauthorized operational commands.

Intermediate verification issues were resolved without altering product behavior:

- A focused invocation from stdin could not bootstrap Windows multiprocessing
  children. The corrected focused runner is a guarded file with a main guard.
- Two G0 fixtures still targeted the old root module. They now inject faults into
  the canonical module, retaining the same silence assertions.
- Static equivalence detected accidental default-encoding conversion of a
  services string. The three consumers were restored from verified snapshot bytes
  and edited by import-byte replacement only. The final full suite runs after
  this correction; the earlier run is not the final-source evidence.

No additional skips are permitted. Evidence exposes sanitized results, not raw
logs or sensitive artifacts. Full offline guard blocks real runtime files and
external networking before application imports.

## Rollback and remaining limits

Restore operations.py and the six changed existing files together from the
verified G4 source snapshot; remove only the reviewed new canonical operations,
alias, G5 test and report paths. Inspect exact absolute targets and hashes before
removing anything; preserve unrelated Owner work. Restart Python processes and
rerun accepted G4 guarded tests. No Git reset/clean, database rollback or service
operation is needed or authorized.

Windows/Python 3.10 offline results do not certify native Debian or Python 3.13
runtime behavior. The three existing skips are the POSIX permission case and two
SQLite no-checkpoint/WAL capability cases. No credentials, sessions or runtime
database were accessed; no TikTok traffic, Git writes, SSH/VPS, deployment or
systemd operation occurred. Previously documented unmanaged low-level helpers
remain a risk. TikTok APIs remain unofficial; server echo does not establish
recipient delivery or streak credit.

STOP at REPORT for independent Owner review. Do not proceed automatically to G6.
