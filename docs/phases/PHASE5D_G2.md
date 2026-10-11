# Phase5D G2 — Application relocation

Task: phase5d-g2-application; date 2026-10-11. IMPLEMENT / OFFLINE TEST / REPORT complete. STOP before G3. Accepted starting baseline: 414 total, 411 PASS, 3 SKIP, 0 FAIL/ERROR.

## Exact file scope

| Before | Current canonical implementation | Change |
| --- | --- | --- |
| cli.py | relttk/application/cli.py | Canonical services imports only; all other AST unchanged. |
| services.py | relttk/application/services.py | ROOT now uses relttk.runtime_paths.REPO; all other bytes unchanged. |
| tiktok_tui.py | relttk/application/tui.py | Canonical services imports; module docstring points to retained main.py tui command. All other AST unchanged. |

All three root implementations are absent. No other implementation moved. Added inert relttk/application/__init__.py and three fixed-target aliases in relttk/compat/legacy/: cli.py, services.py, tiktok_tui.py.

Other edited files:

- relttk/compat/__init__.py: add the three canonical alias targets to the existing explicit bootstrap.
- main.py: canonical services and TUI imports only; non-import AST unchanged. Root entry remains supported.
- tests/test_source_layout.py: inspect canonical TUI source; isolate G0 toy imports from both the real root and compatibility directory. All original assertions retained.
- tests/test_ledger_v2.py: apply existing destructive-repeat and send-plan assertions to canonical application source, preserving all assertions.
- tests/test_tui_services.py: apply the existing no-send-CLI-flag assertion to canonical TUI source.
- tests/test_application_layout.py: nine focused actual-module regressions, listed below.
- docs/architecture/MODULES.md: actual paths, imports, counts and compatibility notes.
- docs/phases/PHASE5D_G2.md: this report.

operational_entry.py, tests/run_offline.py, G1 foundations/aliases, all transport/auth/queue/ledger/worker/scheduling/identity/UNKNOWN/rotation implementation, requirements, templates, schemas/migrations, samples and historical reports are unchanged. Identity Contract remains BLOCKED.

## Dependency and compatibility evidence

| Consumer | Eager internal imports | Lazy application/delegate imports |
| --- | --- | --- |
| main | relttk.compat | Canonical services/TUI in existing command branches; all dispatch behavior retained. |
| relttk.application.cli | main, oneshot, ledger, canonical services | Existing services administration/send imports now canonical. |
| relttk.application.services | relttk.runtime_paths | Existing wrappers retain their root-module imports inside functions. |
| relttk.application.tui | canonical services; optional external Textual | Existing send-plan imports now canonical. |

The normalized AST eager graph covers 44 existing non-test implementation/support modules. The only added edge is services -> runtime_paths to retain the repository anchor. That edge has no return path and creates no eager cycle. Relative/dynamic imports are not exhaustively inferred by this static graph; guarded fresh-process imports supplement it. Package initializers export/import nothing eagerly.

Aliases substitute the canonical module object in sys.modules. Actual legacy-first/canonical-first subprocess tests prove identical modules, shared globals, cli.CONFIG_PATH patches, a services function patch observed through the CLI consumer, TUI patch behavior, Conversation identity and canonical serialization. A profile records exactly one execution of the services module across both names and CLI import. Existing G0 synthetic exception-identity assertions remain; G2 introduces no custom exception class.

The cli alias temporarily removes its own provisional shim before importing canonical CLI. CLI imports main, whose repeated compatibility bootstrap would otherwise refuse the provisional shim. If canonical import fails, the shim is restored and the exception propagated; successful import installs only the canonical module. No import hook, permissive conflict fallback or changes to main's conflict checks. Cached unrelated legacy modules remain refused.

External code uses canonical names, or explicitly calls relttk.compat.enable() before bare cli/services/tiktok_tui imports. Existing main/operational entry/guarded runner bootstrap remains. Imported function/default-argument bindings keep normal Python semantics; alias identity does not retroactively update previously copied from-import bindings when a module is reloaded or patched.

services.ROOT is the same repository root; SESSION_DIR stays root/sesion. Runtime/config/preferences environment capture remains at first import. No private resource was moved or accessed. Both TUI subprocess functions were exercised with synthetic mocks: argv uses root/main.py and cwd is the repository root. Optional Textual absence leaves CLI help/dry-run available and main.py tui reports its existing dependency error; installed Textual mounts and retains the disabled legacy scheduler through existing guarded UI tests.

Supported commands remain root `python -B main.py --help` and `python -B main.py tui`. From repository root, canonical presentation CLI help is `python -B -m relttk.application.cli --help`. The removed root cli.py/tiktok_tui.py files can no longer be executed directly; they are import aliases in the explicit compatibility directory, not standalone launch scripts.

Scanner discovery includes all three implementations, initializer and aliases. Existing source-based tests now read canonical implementations rather than thin alias files. Actual root client refusal/sink assertions remain unchanged. operational_entry.py is byte-identical and still mutes native/Python streams before imports; missing/corrupt-import silence and operational guard tests pass.

## Tests and deviations

Nine new G2 cases explain 414 -> 423:

1. Legacy-first CLI/services identity and CONFIG_PATH patch through CLI dry-run consumer.
2. Canonical-first services globals/functions, consumer patch, class serialization/reload identity.
3. Inert package/bootstrap, idempotent enable and refusal of a conflicting services module.
4. Actual services module executes once across both names and CLI import.
5. CLI dispatch/help without Textual; optional-TUI failure remains clear.
6. Actual CLI dry-run from a disposable alternate cwd, without state creation.
7. Legacy-first TUI identity and patch through its saved-plan consumer.
8. Canonical-first TUI identity and mocked subprocess argv/cwd for login and dry-run.
9. Actual implementation/alias scanner discovery and canonical module origins.

Two optional Textual cases use the existing installation condition; both PASS in this fixture, so no additional full-suite skips.

Initial focused execution: 120 tests, 3 FAIL, 2 ERROR, 2 SKIP. It exposed the provisional cli alias conflict, a Windows UTF-8 capture mismatch and an unsuitable stdin harness for multiprocessing spawn. The alias was fixed within G2 compatibility scope, new child capture explicitly uses UTF-8, and focused execution uses `python -c` instead of stdin. No guard or existing assertions weakened. Final combined focused execution: 120 total, 118 PASS, 2 SKIP, 0 FAIL/ERROR; 13.309s. This predates the ninth single-initialization case.

That new case initially failed twice because a dataclass spy counted unrelated dependency decorations, then failed to support frozen=True. It was replaced by a direct module-execution profile. Final actual G2 execution: 9 tests, 9 PASS, 0 SKIP/FAIL/ERROR; 3.058s. No production behavior changed for these test-instrumentation fixes.

An initial graph equality assertion flagged the intentional services -> runtime_paths edge. Final verification permits exactly this anchor dependency, checks there is no return path/new cycle, and refuses any other added/removed eager edge. No application source change followed the successful full suite.

Final full guarded command:

```text
./work/verify-venv/Scripts/python.exe -B tests/run_offline.py
Ran 423 tests in 46.348s
OK (skipped=3)
Offline guard: external network and real runtime files blocked.
```

**423 total, 420 PASS, 3 SKIP, 0 FAIL/ERROR; exit 0**, Windows/Python 3.10.11. Same three accepted platform skips: POSIX permission check on Windows and two SQLite setconfig/no-checkpoint-on-close WAL capability cases. No new skip. All requests, DBs, sessions/auth and WS responses in tests are disposable synthetic fixtures; no real TikTok connection.

Additional validation: AST all 84 Python files PASS with Python 3.10.11 and 3.13.3; 16 guarded fresh-process import checks PASS; five guarded help checks PASS (main, worker-run, schedule-tick, ws-probe, canonical application CLI). Documentation relative paths/anchors checked separately, with results in links.json. Full Python 3.13 regression suite and native Debian 13 behavior have not been certified.

## Preservation and rollback

117 reviewed current files were frozen against the accepted G1 after-hash manifest before any G2 change. At mapped destinations, 108 remain byte-identical; nine deliberate existing-file changes are the three moved implementations, main, compat bootstrap, three path/isolation tests and MODULES. Six new files comprise the initializer, three aliases, focused test and report. Total reviewed after manifest: 123 files. Total Python inventory: 84 (root 21, core 5, signers 3, plugins 6, deploy 1, tests 33, relttk 15).

Move map, before/after SHA256 manifests, exact before snapshots, preservation list, eager import graph, smoke results and sanitized completion evidence reside under ignored work/phase5d-g2-evidence/. main/CLI/TUI non-import AST equivalence PASS (TUI docstring separately normalized). Services exact root-anchor-only byte transformation PASS. All accepted G1 historical outputs and unrelated files remain unchanged.

Owner-authorized rollback must restore the three original root implementations and every deliberately edited consumer/compat/test/MODULES file from the frozen G1 snapshot together. Remove only G2-added files after verifying workspace containment and expected hashes. Preserve G1 and earlier accepted work, do not reset/clean Git or touch runtime data. Restart interpreters, rerun the guarded 414-test baseline and validate source paths/import identity after rollback. No rollback executed.

## Remaining limits and STOP

Debian native dependency builds, permissions/locking/WAL and deployment remain Owner-operated future fixture work. Package relocation does not resolve Identity Contract BLOCKED or authorize credentials, runtime migration, auth probes, recurring activation or sending. API is unofficial; server echo is not recipient delivery/read confirmation, and TikTok streak credit remains unverified. Git history may still retain the previously removed upstream key; no key reproduced or history rewritten.

No Git mutation, real credentials/session/DB access, live TikTok, SSH/VPS/systemd operations or G3/G4/G5 relocation. STOP REPORT for independent Technical Owner review; do not begin G3.
