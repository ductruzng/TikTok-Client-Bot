# Debian 13 offline regression fix

Task: `debian13-offline-regression-fix`. Status: REPORT; independent review required.

## Reported failure and bounded changes

Owner supplied Debian 13 / Python 3.13 staging results: 457 tests,
32 ERROR, 1 FAIL, 5 SKIP. The accepted Windows baseline was 457 tests,
454 PASS, 3 SKIP. Native Debian results below remain unverified locally.

Only the offline harness, fixtures and documentation changed. No application,
authentication, Identity Contract, database schema, migration, queue, worker,
budget, rotation, breaker or sending behavior changed. Requirements remain
unchanged. No actual sessions, credentials or runtime databases were accessed;
no TikTok traffic, Git writes, SSH, VPS or service operations were performed.

## Descriptor-relative cleanup

CPython's `open` audit event omits `dir_fd`. Interpreting a relative child
name against the repository cwd can therefore mistake a temporary fixture's
`state` directory for the protected repository directory during Linux
`shutil.rmtree` cleanup. The supplied traces and synthetic reproduction
support this diagnosis; they do not establish a successful native Linux run.

The runner wraps `os.open` to associate a resolved path with its audit event
using a scoped `ContextVar`. For relative descriptor-based opens it verifies
the descriptor is a directory and resolves `/proc/self/fd/<fd>` on Linux.
It calls the original function with the original path, flags, mode and
descriptor, preserving descriptor-relative filesystem semantics. The context
is reset even when opening fails.

Unresolvable, nonabsolute or deleted descriptor targets fail closed.
Low-level relative audit events without matching context are refused rather
than assumed relative to cwd. Existing private roots, inherited runtime root,
DNS refusal and external connection refusal remain enabled. Private path
checks include lexical and resolved paths; no actual private fixture is read.

This is a bounded reviewer harness, not an operating-system security sandbox.
Descriptor/path replacement races and arbitrary hostile Python execution are
not proven isolated by these tests. A future private-root symlink change could
also invalidate cached root resolution; protected roots must remain fixed
throughout a review run. Native Linux cleanup must be verified in staging.

## Cross-platform and optional TUI fixtures

The cookie-helper import fixture now imports platform-sensitive standard
library modules before mocking `sys.platform='win32'`. This avoids making
Linux `shutil` import Windows-only `_winapi`. Cookie extraction is never called.

Textual remains an optional runtime dependency in `requirements/tui.txt`.
The full acceptance fixture must install that group as well as core
requirements. If Textual is absent, the existing dynamic TUI scheduling test
reports an explicit SKIP; a new AST-only test still checks the scheduler
refusal branch without importing TUI. A core-only run with additional skips
does not establish full TUI regression acceptance. No mandatory UI dependency
was added to the headless application.

Owner-operated disposable Debian fixture preparation and test command:

```bash
python -m pip install -r requirements.txt -r requirements/tui.txt
python -m pip check
python -B tests/run_offline.py
```

Use the existing staging fixture venv and source checkout. Do not run actual
login, sending, migration or service commands for this validation.

## Changed files

| File | Change |
| --- | --- |
| `tests/run_offline.py` | Descriptor-relative audit context; ambiguous opens fail closed |
| `tests/test_offline_guard.py` | Eight synthetic/native regressions |
| `tests/test_root_hygiene.py` | Portable mocked Windows import |
| `tests/test_scheduling.py` | Explicit optional-Textual skip |
| `README.md` | Full-test dependency prerequisite and report link |
| `docs/operations/DEPLOY_DEBIAN.md` | Full-test dependency prerequisite and report link |
| `docs/operations/DEBIAN13_STAGING_FIX.md` | This report |

## Offline evidence

Final-source executions on Windows:

| Check | Result |
| --- | --- |
| Full guarded suite, Python 3.10.11 | 465 total: 461 PASS, 4 SKIP, 0 FAIL/ERROR; 67.776 seconds |
| Guard/root fixtures, Python 3.10.11 | 14 total: 13 PASS, 1 SKIP; 2.330 seconds |
| Guard/root fixtures, Python 3.13.3 | 14 total: 13 PASS, 1 SKIP; 2.701 seconds |
| AST, Python 3.10.11 and 3.13.3 | 110 Python files parse on each interpreter |
| Guarded CLI help, each interpreter | `--help`, `schedule-tick --help`, `operational-status --help` PASS |
| Preservation hashes | 153 reviewed files compared; only five approved existing files changed |

The full-suite delta is eight new tests: seven execute on Windows; the native
Linux descriptor-relative cleanup test skips there. The other three full-suite
skips are existing platform-specific checks. Windows Python 3.13 coverage is
focused tests, AST and CLI help, not a full application suite.

New regressions cover scoped descriptor interpretation, synthetic private
paths and traversal refusal, deleted/unresolvable descriptor refusal,
context reset after failure, retained network denial, ambiguous cached open
refusal, portable Windows import and static scheduler refusal. The native
Linux test uses a disposable directory named `state`, real descriptor-relative
opens and `TemporaryDirectory` cleanup. It also refuses a synthetic private
directory, removing that test-only protection before cleanup.

Local sanitized evidence is under ignored
`work/debian13-staging-fix-evidence/`: `full-final.txt`, `checks310.txt`,
`checks313.txt`, `links.json`, and `sanitized-tests.txt`. Full runner output
captures stderr unittest summary; application stdout remains suppressed.
No raw traceback or credential-bearing artifact is published through C2C.

## Remaining verification and rollback

No native Debian / Linux Python 3.13 environment was available. WSL inventory
contains only Docker Desktop's internal distribution, which was not used.
Owner must rerun the full guarded suite with TUI fixture dependencies on Debian
13 before resuming WAL, POSIX permissions or locking acceptance. Exact Linux
PASS/SKIP counts depend on platform capabilities; inspect every skip reason.
Do not proceed to runtime deployment or activation based on Windows evidence.

Rollback consists of restoring the five changed existing files from the
pre-task copies in `work/debian13-staging-fix-evidence/before/` and removing
only the new test/report through a separately authorized action. No runtime
data, database or schema rollback is required. Restoring the old harness also
restores the reported Linux limitation, so that version must not be represented
as accepted Debian staging.

STOP at REPORT. Independent Technical Owner review and native Debian evidence
are required before any staging progression.
