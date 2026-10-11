# Phase5D — Cohesive source layout design

TASK_ID: phase5d-source-layout-design  
STATE: PLAN / REPORT — implementation is not approved  
Date: 2026-10-11  
Baseline: accepted local dev worktree, HEAD e771161f416249cf0e16d64e20048b434ecf540d plus uncommitted Phase5A/B/C-Lite/final-docs-tidy.

## 1. Goal and recommendation

The Owner wants a cohesive source layout, not documentation-only cleanup. Recommend one canonical relttk package, two stable root command entrypoints, and explicit legacy import compatibility outside root. This is a refinement of Phase5B option C with staged checkpoints; it does not claim that file moves remove architectural coupling.

The [audit](PHASE5B_ARCHITECTURE_PLAN.md), [current module guide](../architecture/MODULES.md) and [accepted documentation report](PHASE5C_LITE.md) remain unchanged. This document describes **proposed** paths only. Existing safety behavior, data layout and identity refusal remain the acceptance contract.

Debian 13 is the sole future staging target. Identity Contract remains BLOCKED. No database migration, live TikTok/session access, Git writes, deployment or source/test edits are part of this planning task. Accepted suite baseline is **390 total, 387 PASS, 3 SKIP, 0 FAIL/ERROR**; no suite rerun is performed or claimed.

### Important compatibility decision

A clean root and automatic fresh-process bare imports cannot both be preserved without a root shim, environment setup or import hook. Do not claim otherwise. Proposed compromise:
- Official entrypoints and the guarded test runner explicitly enable the small legacy compatibility search directory.
- External callers use canonical imports, or explicitly enable legacy compatibility before old bare imports.
- Do not add sitecustomize, a global meta_path hook, startup network logic or automatic dependency installation.
- If Owner requires fresh-process import client to work with only root on sys.path and no bootstrap, keep client.py as a root alias. This reduces the achievable root reduction and requires approving the exact retained names.

This public import bootstrap requirement must be approved before implementation.

## 2. Target tree and exact mapping

```text
root/
  main.py                       # stable CLI/validation anchor
  operational_entry.py          # mute before imports
  __init__.py                   # retained legacy package export
  browsercookies.py             # REVIEW-only; keep for now
  test_ws_capture.py            # REVIEW-only; keep for now
  README.md / LICENSE / .gitignore / requirements*.txt / streak.json
  relttk/
    __init__.py                 # inert
    config.py
    log.py
    runtime_paths.py
    operations.py
    application/               # inert __init__.py
      cli.py / services.py / tui.py
    transport/                 # inert __init__.py
      client.py / oneshot.py / qrlogin.py / ws_auth_capture.py
    storage/                   # inert __init__.py
      ledger.py / ledger_requests.py / ledger_migrations.py / queue_service.py
    runtime/                   # inert __init__.py
      worker.py / scheduling.py / rotation.py / unknown_resolution.py
    identity/                  # inert __init__.py
      circuit_breaker.py / identity_service.py / readiness.py
    compat/
      __init__.py               # stdlib-only explicit enable function
      legacy/                   # 22 alias files, no duplicate implementations
  core/ / signers/ / plugins/ / deploy/ / tests/ / docs/
```

| Existing implementation | Proposed canonical path | Group |
| --- | --- | --- |
| `cli.py` | `relttk/application/cli.py` | G2 |
| `services.py` | `relttk/application/services.py` | G2 |
| `tiktok_tui.py` | `relttk/application/tui.py` | G2 |
| `config.py` | `relttk/config.py` | G1 |
| `log.py` | `relttk/log.py` | G1 |
| `runtime_paths.py` | `relttk/runtime_paths.py` | G1 |
| `client.py` | `relttk/transport/client.py` | G3 |
| `oneshot.py` | `relttk/transport/oneshot.py` | G3 |
| `qrlogin.py` | `relttk/transport/qrlogin.py` | G3 |
| `ws_auth_capture.py` | `relttk/transport/ws_auth_capture.py` | G3 |
| `ledger.py` | `relttk/storage/ledger.py` | G4 |
| `ledger_requests.py` | `relttk/storage/ledger_requests.py` | G4 |
| `ledger_migrations.py` | `relttk/storage/ledger_migrations.py` | G4 |
| `queue_service.py` | `relttk/storage/queue_service.py` | G4 |
| `worker.py` | `relttk/runtime/worker.py` | G4 |
| `scheduling.py` | `relttk/runtime/scheduling.py` | G4 |
| `rotation.py` | `relttk/runtime/rotation.py` | G4 |
| `unknown_resolution.py` | `relttk/runtime/unknown_resolution.py` | G4 |
| `circuit_breaker.py` | `relttk/identity/circuit_breaker.py` | G4 |
| `identity_service.py` | `relttk/identity/identity_service.py` | G4 |
| `readiness.py` | `relttk/identity/readiness.py` | G4 |
| `operations.py` | `relttk/operations.py` | G5 |

For **each** of the 22 rows, an additional compatibility file is proposed at relttk/compat/legacy/<original basename>.py. Its target is exactly the canonical path in that row converted to a dotted module name. For example tiktok_tui.py aliases relttk.application.tui; ledger.py aliases relttk.storage.ledger. No mapping is inferred dynamically from arbitrary filenames.

All remaining 48 existing Python paths stay in place:
- Root main.py, operational_entry.py, __init__.py, browsercookies.py, test_ws_capture.py.
- All five core/, three signers/, six plugins/, 28 tests/ and deploy/render_units.py.
- Requirements, samples, unit templates, private runtime locations and existing phase records stay in place.
New test files, scanner/consumer edits and documentation updates are separately listed below.

### Honest file-count benefit

Root Python count: **27 -> 5**, reduction 22 (about 81%). The two manual tools remain visibly REVIEW-only until an independently approved relocation; no deletion is proposed. Only two root files are command entrypoints; main retains its implementation/validation for now rather than expanding scope to extract it.

There is no total-file or code-size reduction claim. Moving 22 implementations, adding seven package initializers (including compat bootstrap) and 22 alias modules changes Python count from 70 to **99 before new regression files**. Compatibility increases file count while grouping it away from root. Owner may choose canonical-only imports and separately approve removing compatibility later; that is not part of this plan.

Benefits: predictable domain namespaces, clearer ownership/navigation and fewer mixed runtime files at root. Costs: more compatibility files, consumer/import updates, path-review burden and retained lazy coupling. No new third-party dependency, packaging system or generic plugin framework is required.

## 3. Canonical module identity model

Canonical application imports always use fully qualified relttk names. Existing core/signers/plugin namespaces remain unchanged; their references to moved root modules must use canonical names. Do not import relttk.transport.client under a second parent package name.

Each compatibility alias uses standard importlib to import its fixed canonical target and replaces its own sys.modules entry with that module object. It does not copy attributes, execute a second source copy, subclass errors or use import *. This is a proposed implementation pattern requiring isolated fixture proof before use.

Required invariants:
- import cli after compatibility enable and import relttk.application.cli return the same object.
- cli.CONFIG_PATH patches affect menu functions' canonical globals.
- services.send_plan and oneshot packet/auth patches affect all aliases and canonical callers.
- Class/exception identities match; __module__, __spec__, __file__ and reload refer to the canonical implementation, not an alias file.
- Alias-first and canonical-first orders work in separate fresh interpreters; concurrent imports do not create two canonical instances.
- Existing conflicting sys.modules aliases are refused/reported, never overwritten silently.
- Canonical package initializers remain inert. Enabling compatibility adds only the checked local compatibility directory, not eager imports of all 22 modules.
- Alias filenames are exact approved legacy names; no unrestricted discovery, attacker-selected module target or general import interception.
- Compatibility is module-import compatibility. Direct execution of an old moved module filename is not silently promised; main.py and operational_entry.py remain the supported command surfaces.

Enable compatibility only at deliberate consumer boundaries. main.py can establish its unchanged repository root and call stdlib-only compat setup before dispatch. The test runner installs its existing runtime/network guard **before** compatibility setup and discovery. Operational entry mutes native and Python output **before** importing compat, operations or main. The copied-entrypoint missing-module fixture must still fail silently with status 3.

Root __init__.py must preserve the legacy LttkClient export using the single absolute relttk namespace. Review parent-package loading and sys.path setup explicitly; using parentname.relttk alongside relttk would duplicate identities. Existing client relative/absolute fallback imports should become explicit canonical imports only in the approved transport group, with dependency failures still exposed safely.

Compatibility must work during staged migration: only aliases for already moved modules are introduced. Unmoved root implementations remain canonical until their group moves. Do not overwrite or preload a remaining root implementation. Restart interpreters between checkpoints; never hot-swap loaded application modules.

## 4. Path and side-effect inventory

| Current contract | Proposed preservation |
| --- | --- |
| runtime_paths.REPO from root __file__ | After moving to relttk/runtime_paths.py use its parent-parent repository anchor; verify exact old root with fixtures |
| services.ROOT and env-backed config/preferences captured at import | Use the canonical repository anchor, keeping current import-time capture/default semantics and legacy session spelling |
| ledger state/db/run.lock defaults | Same repository/TIKTOK_RUNTIME_DIR values and same bound-default timing; no creation on missing/wrong path |
| qrlogin _SESSION_DIR | Same repository/sesion location; never a relttk/transport/sesion folder |
| client legacy WS auth, plugins and state resources | Resolve from unchanged repository anchor; no copy/move of runtime artifacts |
| core/api parent-parent root/cache | Keep core in place and its existing anchor; replace moved-module imports only |
| main streak.json default | Retain cwd-relative semantics and repository-root documentation |
| TUI child ROOT/main.py and cwd=ROOT | Keep root executable/cwd, argument handling and optional Windows behavior |
| deploy renderer parent-root, adjacent templates | Keep renderer/template locations and operational entry contract |
| operational_entry native suppression before imports | Preserve exact ordering even when importing new namespaces |
| tests/run_offline guard protected roots | Keep runner location/root and guard installed before any application load |
| manual capture root/work profile | Keep root manual tool paths; no access or activation |
| config/log import effects | Preserve configuration evaluation, stdout/NO_COLOR behavior and exception identity |

No config, state, session, browser profile, database, WAL or cache is relocated. Migration refers only to code organization. Use disposable synthetic roots, alternate cwd and env-set-before/after-import fixtures; do not validate against real data. Runtime-path validators, symlink refusal and POSIX permission checks remain unchanged.

## 5. Imports, dynamic loading and atomic groups

The audited internal module-level graph has no eager SCC. Including lazy and entry edges has one potential 21-module SCC, documented in the [existing guide](../architecture/MODULES.md#import-contracts). This is a deferred dependency graph, not a runtime failure claim.

Verified cross-boundaries:
- oneshot eagerly imports main validation; queue/service consumers import it lazily. main remains a root anchor; do not silently extract validation in this move project.
- ledger/ledger_migrations and worker/scheduling cross-reference lazily.
- ledger_requests executes queue/worker/scheduling/circuit/UNKNOWN gates, so it is not a pure storage layer.
- core/__init__ exports API/proto; root __init__ exports client. New domain initializers must not eagerly re-export them.
- client discovers plugins with spec_from_file_location and the existing bot.plugins names. plugins are not proven unused by the static graph.
- Optional Textual/Playwright/auth imports must stay optional/lazy for default CLI and help paths.

Groups are **implementation checkpoints, not claims of architectural independence**:

| Group | Candidate moves | Atomic consumer scope / stop gate |
| --- | --- | --- |
| G0 coverage first | None | Scanner discovery, canonical AST checks, alias/path fixtures, approved test runner bootstrap; full baseline before any move |
| G1 foundations | config, log, runtime_paths (3) | Root/package export, core and remaining module references plus explicit root/default fixtures; small coherent group |
| G2 application | cli, services, tiktok_tui (3) | Main dispatch, UI/service patch consumers, ROOT/subprocess paths and optional dependencies move together |
| G3 transport | client, oneshot, qrlogin, ws_auth_capture (4) | Session/auth pair, core references, legacy-send AST consumers and plugin root paths update together |
| G4 safety/persistence cluster | storage 4 + runtime 4 + identity 3 (11) | Atomic cross-import/admission update; do not deploy partially mixed source groups |
| G5 operations | operations (1) | operational_entry, main operational dispatch, renderer/test consumers; mute-before-import negative fixtures |
| G6 final review | None | Actual module guide/README, import map, counts, all security checks and rollback evidence |

G1/G2 can be checkpointed separately while old modules use the explicit compatibility surfaces. G3 requires one transport/auth-facing update. G4 is the most coupled group; separate approval after G3 evidence is recommended. Splitting storage from worker/identity without proving every cross-admission route risks bypasses. If fixture/import evidence shows any proposed checkpoint cannot coexist safely, stop for Owner approval to combine/reorder groups rather than improvising.

No stage claims all Core protected merely because files moved. Existing refused legacy sends, binding gates and identity BLOCKED remain tested at every supported entrypoint.

## 6. Scanner expansion BEFORE relocation

Proposed G0 changes:
- Existing test_ws_auth_boundary discovery includes relttk/ recursively **before** implementations move; retain all existing root/core/signers/plugins/deploy/tests coverage and include compatibility files.
- Exact tracked/approved source allowlist prevents scanning private work/session/state directories; no whole-workspace rglob.
- Add synthetic scanner fixtures in temporary directories proving a new nested canonical module and alias directory are inspected. Use harmless forbidden assignment structure, not a real WS key or credential.
- The legacy-send AST proof follows the actual client class implementation, verifies __file__ resolves canonical client, and retains all existing refusal assertions. Do not replace AST evidence with a wrapper check.
- Tests for packet/WS calls and session pairing cover old and canonical public routes; no implicit credential source introduced.
- Operations source/entrypoint inspection stays on actual implementation and stable root bootstrap. Renderer paths and serialized unit output retain their security contract.
- A source enumeration test proves every approved production Python location has static scanner coverage; document AST limitations rather than treating it as exhaustive secret detection.

G0 baseline remains 390 prior cases plus explicitly approved focused additions. Zero assertion removal or guard relaxation. New cases are meaningful negative/identity/path tests, not copied implementation logic.

## 7. Proposed implementation/test/document file scope

Moves and aliases: exactly the mapping above. New package initializers: relttk/__init__.py and application/transport/storage/runtime/identity/compat/__init__.py (seven total). compat/legacy has no package initializer.

Approved future consumer edits would include:
- main.py, operational_entry.py and retained root __init__.py for bootstrap/canonical dispatch/legacy export.
- Moved modules: imports and proven path corrections only; no send/ledger/scheduler algorithm changes.
- core/api.py, core/self_identity.py and other actual cross-module consumers found by the graph; preserve protocol/signers/plugin logic. Resolve imports by explicit graph search, not global textual name replacement.
- tests/run_offline.py compatibility setup after guard; tests/test_ws_auth_boundary.py, test_legacy_send_closure.py, test_operations.py, test_deployment.py, test_runtime_paths.py and relevant existing patch consumers as required. Legacy alias tests remain in addition to canonical smoke coverage.
- Proposed new tests/test_source_layout.py (identity/import/path/entry contracts) and tests/test_scanner_coverage.py (new-directory and implementation coverage).
- README and docs/architecture/MODULES.md updated only after each accepted structure exists; new docs/phases/PHASE5D.md reports actual results. Do not rewrite historical Phase5 records.

Not proposed: new dependencies/requirements, pyproject/build installation, templates changes, JSON samples, schemas/migrations, live auth/bootstrap, business-logic refactor or source deletion. Any need for these is a separate approval issue.

## 8. Focused fixtures and acceptance matrix

| Fixture/check | Required evidence |
| --- | --- |
| Import identity | Alias-first/canonical-first, object/class identity, exception reduce/importability, reload behavior; no duplicate globals |
| Legacy monkeypatch | cli.CONFIG_PATH, services.send_plan, oneshot packet/auth patches affect canonical calls |
| Fresh-process bootstrap | Root CLI, package export, guarded runner, optional external enable; conflict aliases rejected |
| Default offline route | No Textual/Playwright requirement, no DB/session open or network on import/default dry-run/help |
| Roots and environment | Exact repository root, same defaults/cwd/env capture, config/preferences/session/plugin/cache locations |
| Private root refusal | Synthetic outside-root/symlink/permissions rejection; absent schema fails before transport |
| Dynamic plugins | Same discovery path/names; disabled/inert behavior preserved, no automatic plugin activation |
| Session/auth | Explicit key validation, ttwid matching, missing auth refusal before connect; no identity guess |
| Legacy mutation closure | All prohibited class methods still refuse; actual canonical AST body verified |
| Safety state | Idempotency/replay, FIFO/atomic claim, UNKNOWN, quotas/budgets, cancel/skip/snapshot, circuits/consent ABA unchanged |
| Worker lifecycle | No locks/DB/WS while waiting, atomic re-admission, bounded post-marker echo, no retransmit |
| Operational entry | Mute before all imports; missing/corrupt canonical package/parser errors emit no raw data; metadata allowlist only |
| CLI/deployment | Existing main and operational commands/help; renderer keeps exact root entry/cwd; no systemd execution |
| Static coverage | Original roots plus new package/aliases discovered; nested fixture proves scanner does not bypass implementation |
| AST/import graph | Python 3.10/3.13 parse; no new eager SCC; lazy/dynamic edges recorded |
| Full suite | Guarded runner after G0 and each G1–G5, plus new cases; no FAIL/ERROR or unexplained SKIP |
| Documentation | Actual path map/local links/anchors correct; proposals not described as completed |
| Debian fixture | Later Owner-operated Python 3.13 dependency/permission/locking/WAL checks; local AST is not native certification |

Baseline's three Windows skips (POSIX permission and two SQLite setconfig/WAL capability cases) remain explained. New optional-dependency skips must not conceal canonical/legacy compatibility failures. A changed test count must reconcile with approved new tests. Every process exercising imports/transports uses the guard or equivalent fixture protection inherited by children.

## 9. Rollback by group

Before each approved group record exact source/tests/docs hashes, import map, allowlisted before bytes, destination absence and current test evidence in an ignored reviewed backup directory. It must contain no runtime data.

For G0 restore only changed scanners/runner/tests; remove only approved added fixture/test files if authorized. For G1–G5 restore moved original source and every consumer/scanner/entry/document adjustment as one reviewed set; remove that group's new canonical/alias files and unused initializers only after verifying absolute destinations remain inside workspace and hashes match expected generated files. Do not mix earlier/new implementations or delete unrelated Owner work. Restart interpreters after rollback.

Re-run guarded focused/full checks on the restored group. No git reset/clean/rebase, database migration, quota edit, runtime file copy or service restart is part of recovery. Prior accepted docs and earlier group evidence remain intact. If source rollback cannot be completed without touching unknown Owner changes, stop and report the concrete conflict.

## 10. Decisions required and planning evidence

Technical Owner approval must settle:
1. Canonical namespace and exact 22-module mapping.
2. Explicit bootstrap for legacy bare imports; which, if any, names need permanent root aliases for standalone external callers.
3. Retain two manual REVIEW tools and root legacy package export initially (27 -> 5).
4. Compatibility overhead of 29 new Python files before focused tests; no total-size reduction claim.
5. Scanner-first G0 and per-group full-suite gates; G4's atomic 11-module cluster and review checkpoint.
6. Exact permitted consumer/test edits and no validation/API extraction under a relocation label.
7. Owner-operated Debian fixture verification later; no deployment/commit/push authorization.

Existing 105 reviewed source/config/template/document files were frozen for this planning task. Final preservation verification is reported via C2C. Only this new plan is authorized now; no suite rerun is required or claimed.

STOP PLAN / REPORT. Await Technical Owner approval before implementation.

