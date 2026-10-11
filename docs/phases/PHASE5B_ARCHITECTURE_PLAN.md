# Phase5B — Source architecture audit and cleanup plan

Task: phase5b-source-architecture-audit  
Status: PLAN / REPORT ONLY — Phase5C is not approved  
Date: 2026-10-11  
Target: Owner-operated Debian 13 staging; Termux is retired.  
Audited local dev base: e771161f416249cf0e16d64e20048b434ecf540d

## 1. Scope, evidence and recommendation

This audit examines the existing clone and preserves the accepted, uncommitted Phase5A changes. No application/test changes, moves, migrations, runtime database/session access, live TikTok traffic, deployment, or Git writes are authorized or performed.

Recommendation: choose **A, keep runtime modules where they are**, and publish an architecture/module map before considering package moves. There is verified dependency coupling, but moving files alone does not remove it. B is a bounded alternative if clearer namespace ownership is an explicit Owner goal; C is a larger redesign requiring separate approval and staged compatibility evidence.

Verified evidence:
- 70 tracked Python files were parsed and their internal import relationships inspected.
- There is no strongly connected component in the conservative module-level internal import graph.
- Including lazy and entry-guard imports produces one 21-module strongly connected component. This is a potential dependency cycle, not evidence that the current application suffers an eager import failure.
- Source-derived paths, dynamic plugin loading, test patch targets, AST security scanners and deployment entrypoints create significant move risks.
- Accepted baseline: **390 total, 387 PASS, 3 SKIP, 0 FAIL/ERROR**. Phase5B does not rerun that suite or claim a new test execution.
- Python 3.10 and 3.13 AST checks passed during Phase5A. Full dependency/runtime compatibility on Python 3.13 and Debian 13 remains unverified.
- Local dev matches the stated audited base. Official main 6289a3b99baa94fca8fd0bcafbfc0b6660783337 is not locally available for independent tree comparison. No fetch was performed. Local remote naming differs from the currently stated official repository; no remote was changed.

Recommendations are explicitly marked as future work. File relocation, wrapper design and package names below are proposals, not implemented behavior.

## 2. Inventory and import map

Classification: root 27, core 5, signers 3, plugins 6, deploy 1, tests 28 Python files. Tests include runner/support modules, not 28 separately discovered test cases.

The following table inventories every tracked Python file. Dependency names refer to internal modules. Unmarked imports occur at module level; [lazy] occurs inside a function and [entry] inside an entry guard. Optional branches and fallback imports are conservatively retained. External library imports, reflection and filesystem-loaded plugins are assessed separately; the table is not a complete runtime execution graph.

| File | Classification | Internal import dependencies |
| --- | --- | --- |
| `__init__.py` | Runtime/application | `client` |
| `browsercookies.py` | Manual/legacy tool — REVIEW | None detected internally |
| `circuit_breaker.py` | Runtime/application | `identity_service [lazy]`, `ledger`, `ledger_requests [lazy]`, `unknown_resolution [lazy]` |
| `cli.py` | Runtime/application | `ledger`, `ledger_requests [lazy]`, `main`, `oneshot`, `services`, `services [lazy]` |
| `client.py` | Runtime/application | `config`, `core`, `log`, `qrlogin [lazy]`, `runtime_paths [lazy]` |
| `config.py` | Runtime/application | None detected internally |
| `core/__init__.py` | Protocol/API | `core.api`, `core.proto` |
| `core/api.py` | Protocol/API | `circuit_breaker [lazy]`, `config`, `core.self_identity [lazy]`, `core.signer_client [lazy]` |
| `core/proto.py` | Protocol/API | `core.signer_client` |
| `core/self_identity.py` | Protocol/API | `circuit_breaker` |
| `core/signer_client.py` | Protocol/API | `signers.bogus [lazy]`, `signers.xdynosaur [lazy]`, `signers.xgnarly [lazy]` |
| `deploy/render_units.py` | Deployment template renderer | `ledger_requests [lazy]`, `runtime_paths [lazy]`, `scheduling [lazy]` |
| `identity_service.py` | Runtime/application | `circuit_breaker`, `core.api [lazy]`, `ledger`, `ledger_migrations [lazy]`, `ledger_requests [lazy]`, `readiness`, `runtime_paths` |
| `ledger.py` | Runtime/application | `ledger_migrations [lazy]`, `ledger_requests [lazy]`, `runtime_paths [lazy]` |
| `ledger_migrations.py` | Runtime/application | `circuit_breaker [lazy]`, `ledger [lazy]` |
| `ledger_requests.py` | Runtime/application | `circuit_breaker`, `ledger`, `queue_service [lazy]`, `rotation`, `scheduling [lazy]`, `unknown_resolution [lazy]`, `worker [lazy]` |
| `log.py` | Runtime/application | None detected internally |
| `main.py` | Entrypoint | `config [lazy]`, `core.api [lazy]`, `ledger [lazy]`, `ledger_migrations [lazy]`, `ledger_requests [lazy]`, `oneshot [lazy]`, `operations [entry]`, `operations [lazy]`, `qrlogin [lazy]`, `rotation [lazy]`, `services [lazy]`, `tiktok_tui [lazy]`, `unknown_resolution [lazy]`, `ws_auth_capture [lazy]` |
| `oneshot.py` | Runtime/application | `circuit_breaker`, `client`, `config`, `core.api`, `core.proto`, `ledger`, `ledger_requests`, `log`, `main`, `qrlogin`, `queue_service`, `runtime_paths [lazy]`, `worker [lazy]` |
| `operational_entry.py` | Entrypoint | `main [lazy]`, `operations [lazy]` |
| `operations.py` | Runtime/application | `ledger [lazy]`, `ledger_migrations [lazy]`, `ledger_requests [lazy]`, `runtime_paths [lazy]`, `scheduling [lazy]` |
| `plugins/info.py` | Legacy plugin | None detected internally |
| `plugins/menu.py` | Legacy plugin | None detected internally |
| `plugins/ping.py` | Legacy plugin | None detected internally |
| `plugins/react.py` | Legacy plugin | None detected internally |
| `plugins/stickerdl.py` | Legacy plugin | None detected internally |
| `plugins/videodl.py` | Legacy plugin | None detected internally |
| `qrlogin.py` | Runtime/application | `config`, `core`, `core.api`, `core.signer_client`, `log`, `runtime_paths [lazy]`, `ws_auth_capture [lazy]` |
| `queue_service.py` | Runtime/application | `ledger`, `ledger_requests [lazy]`, `main [lazy]`, `oneshot [lazy]`, `rotation`, `runtime_paths [lazy]` |
| `readiness.py` | Runtime/application | `circuit_breaker [lazy]`, `client [lazy]`, `ledger_migrations [lazy]`, `queue_service [lazy]`, `runtime_paths` |
| `rotation.py` | Runtime/application | None detected internally |
| `runtime_paths.py` | Runtime/application | None detected internally |
| `scheduling.py` | Runtime/application | `circuit_breaker`, `ledger`, `ledger_migrations`, `ledger_requests`, `queue_service`, `readiness`, `rotation`, `runtime_paths`, `unknown_resolution [lazy]`, `worker` |
| `services.py` | Runtime/application | `circuit_breaker [lazy]`, `config [lazy]`, `core.api [lazy]`, `identity_service [lazy]`, `ledger [lazy]`, `ledger_requests [lazy]`, `main [lazy]`, `oneshot [lazy]`, `operations [lazy]`, `qrlogin [lazy]`, `queue_service [lazy]`, `readiness [lazy]`, `rotation [lazy]`, `runtime_paths [lazy]`, `scheduling [lazy]`, `unknown_resolution [lazy]`, `worker [lazy]` |
| `signers/bogus.py` | Signing | None detected internally |
| `signers/xdynosaur.py` | Signing | `signers.xgnarly` |
| `signers/xgnarly.py` | Signing | None detected internally |
| `test_ws_capture.py` | Manual/legacy tool — REVIEW | None detected internally |
| `tests/__init__.py` | Guarded test/support | None detected internally |
| `tests/ledger_fixtures.py` | Guarded test/support | `circuit_breaker`, `ledger`, `ledger_migrations`, `ledger_requests`, `oneshot [lazy]`, `queue_service` |
| `tests/run_offline.py` | Guarded test/support | None detected internally |
| `tests/test_api_inbox.py` | Guarded test/support | `core.api` |
| `tests/test_baseline_packets.py` | Guarded test/support | `core`, `core.proto` |
| `tests/test_circuit_breaker.py` | Guarded test/support | `circuit_breaker`, `client [lazy]`, `core [lazy]`, `core.api [lazy]`, `ledger`, `ledger_migrations`, `ledger_requests`, `main`, `oneshot [lazy]`, `tests.ledger_fixtures`, `tests.ledger_fixtures [lazy]`, `tests.test_streak` |
| `tests/test_deployment.py` | Guarded test/support | `deploy.render_units` |
| `tests/test_identity_bootstrap.py` | Guarded test/support | `circuit_breaker`, `core`, `core.api`, `core.self_identity`, `identity_service`, `ledger`, `ledger_migrations`, `main`, `readiness` |
| `tests/test_independent_review.py` | Guarded test/support | `client`, `client [lazy]`, `core.proto`, `ledger`, `log`, `main`, `oneshot`, `qrlogin`, `tests.ledger_fixtures` |
| `tests/test_ledger_v2.py` | Guarded test/support | `ledger`, `ledger_migrations`, `ledger_requests`, `main [lazy]`, `oneshot [lazy]`, `services [lazy]`, `tests.ledger_fixtures` |
| `tests/test_legacy_send_closure.py` | Guarded test/support | `client`, `core.proto [lazy]` |
| `tests/test_operations.py` | Guarded test/support | `circuit_breaker [lazy]`, `ledger [lazy]`, `ledger_migrations`, `ledger_requests [lazy]`, `main [lazy]`, `oneshot [lazy]`, `operations`, `scheduling [lazy]`, `tests.ledger_fixtures [lazy]` |
| `tests/test_phase3b_hardening.py` | Guarded test/support | `cli`, `ledger_migrations`, `ledger_requests`, `main`, `oneshot`, `services`, `tests.ledger_fixtures` |
| `tests/test_queue.py` | Guarded test/support | `circuit_breaker`, `ledger`, `ledger_migrations`, `ledger_requests`, `main`, `oneshot`, `queue_service`, `services` |
| `tests/test_queue_migrations.py` | Guarded test/support | `ledger`, `ledger_migrations` |
| `tests/test_rate_limits.py` | Guarded test/support | `ledger`, `ledger_migrations`, `ledger_requests`, `main`, `oneshot`, `services`, `tests.ledger_fixtures` |
| `tests/test_readiness.py` | Guarded test/support | `circuit_breaker`, `ledger [lazy]`, `ledger_migrations`, `ledger_requests [lazy]`, `readiness`, `services` |
| `tests/test_rotation.py` | Guarded test/support | `ledger`, `ledger_migrations`, `ledger_requests`, `main`, `oneshot`, `rotation`, `services`, `tests.ledger_fixtures` |
| `tests/test_runtime_paths.py` | Guarded test/support | `client`, `qrlogin`, `runtime_paths`, `services` |
| `tests/test_safety_fixes.py` | Guarded test/support | `client`, `ledger`, `main`, `oneshot`, `qrlogin`, `services`, `services [lazy]`, `tests.ledger_fixtures`, `tiktok_tui [lazy]`, `ws_auth_capture` |
| `tests/test_scheduling.py` | Guarded test/support | `circuit_breaker`, `ledger`, `ledger_migrations`, `ledger_requests`, `main`, `oneshot`, `queue_service [lazy]`, `rotation`, `scheduling`, `services`, `tiktok_tui [lazy]`, `worker` |
| `tests/test_scheduling_migrations.py` | Guarded test/support | `ledger`, `ledger_migrations` |
| `tests/test_streak.py` | Guarded test/support | `client`, `core.proto`, `ledger`, `ledger_requests [lazy]`, `log`, `oneshot`, `plugins.videodl [lazy]`, `qrlogin [lazy]`, `queue_service [lazy]`, `tests.ledger_fixtures` |
| `tests/test_tui_services.py` | Guarded test/support | `services` |
| `tests/test_unknown_resolution.py` | Guarded test/support | `circuit_breaker`, `ledger`, `ledger_requests`, `main`, `queue_service`, `services`, `unknown_resolution` |
| `tests/test_worker.py` | Guarded test/support | `circuit_breaker`, `ledger`, `ledger_migrations`, `ledger_requests`, `main`, `oneshot`, `queue_service`, `services`, `worker` |
| `tests/test_worker_migrations.py` | Guarded test/support | `ledger`, `ledger_migrations` |
| `tests/test_ws_auth_boundary.py` | Guarded test/support | `client`, `config`, `oneshot` |
| `tiktok_tui.py` | Runtime/application | `oneshot [lazy]`, `services`, `services [lazy]` |
| `unknown_resolution.py` | Runtime/application | `ledger`, `ledger_requests [lazy]`, `queue_service [lazy]`, `rotation` |
| `worker.py` | Runtime/application | `circuit_breaker`, `ledger`, `ledger_requests`, `oneshot [lazy]`, `queue_service`, `rotation`, `scheduling [lazy]` |
| `ws_auth_capture.py` | Runtime/application | `oneshot [lazy]`, `qrlogin [lazy]` |

No file is proven unused solely because the AST graph has no incoming edge. CLI dispatch, tests, manual commands, package imports and dynamic loading are independent consumers. No source deletion is recommended in this phase.

### Other tracked areas

| Area | Classification | Decision |
| --- | --- | --- |
| requirements.txt | Reviewed shared dependencies | KEEP; package moves do not justify dependency changes |
| requirements/windows.txt | Optional Windows capture support | REVIEW documentation/optional install scope; do not delete |
| deploy/systemd templates | Future Debian operations | KEEP paths and operational entry contract |
| docs/phases/ | Accepted historic phase records | KEEP Phase5A exactly |
| docs/operations/ | Debian staging and checklist | KEEP Phase5A exactly |
| docs/security/ and docs/evidence/ | Security review and execution evidence | KEEP |
| docs/archive/TERMUX.md and root TERMUX.md | Retired guide and compatibility stub | KEEP accepted archive/stub; do not revive Termux |
| README.md, .gitignore, CHANGELOG.md | Accepted root guidance/hygiene | KEEP byte-for-byte during Phase5B |
| config samples | Non-secret examples | KEEP compatibility; runtime local files are excluded from this audit |
| browsercookies.py, test_ws_capture.py | Manual/legacy diagnostics | REVIEW supported workflow, not confirmed unused |
| plugins/*.py | Legacy/disabled behaviors and test consumers | KEEP; no deletion or activation |
| fyp2 legacy helper reference | Legacy core/API dependency not supplied as tracked runtime module | REVIEW unsupported route; do not install or activate automatically |
| Generated artifacts and private runtime directories | Out of audit read scope | Never treat as source or open to establish architecture |

## 3. Dependency and side-effect findings

### Verified direction and cycles

oneshot.py imports main.validate_config_data at module level. queue_service.py and services.py also import configuration validation from main lazily. Transport and services therefore depend on CLI entrypoint code. A package move would preserve this inversion unless validation is explicitly extracted in a separately approved change.

The potential SCC is:
`circuit_breaker`, `client`, `core`, `core.api`, `core.self_identity`, `identity_service`, `ledger`, `ledger_migrations`, `ledger_requests`, `main`, `oneshot`, `operations`, `qrlogin`, `queue_service`, `readiness`, `scheduling`, `services`, `tiktok_tui`, `unknown_resolution`, `worker`, `ws_auth_capture`.

worker/scheduling and ledger/migrations/request admission depend on one another through lazy imports. ledger_requests also calls queue, worker, scheduling and UNKNOWN checks: it is not a pure storage adapter. Labels such as storage/runtime do not create a clean layer automatically.

core/__init__.py re-exports protocol/API modules. Root __init__.py exports client. client supports relative and absolute import fallbacks. Introducing a package initializer that eagerly re-exports all modules could turn lazy cycles into eager failures. Broad ImportError fallback can also mask a missing transitive dependency; audit canonical imports before changing this behavior.

Dynamic legacy plugin loading in client uses spec_from_file_location and an adjacent plugins directory. These edges are absent from the static graph. Disabled video download behavior still has test consumers. Absence from the static map does not authorize deletion.

### Import-time behavior to preserve

| Module | Observed behavior | Move implication |
| --- | --- | --- |
| main | Adds its own directory to sys.path | New location changes import search/root semantics |
| cli | May reconfigure stdout encoding | Wrappers must not unexpectedly duplicate side effects |
| services | Computes ROOT, runtime/config/preferences paths at import | New __file__ silently changes defaults |
| runtime_paths | Computes repository anchor from __file__; validates runtime roots on calls | Keep anchor stable |
| ledger | Captures env-backed state/ledger/lock defaults at import/function definition | Later environment changes do not replace bound default arguments |
| log | Evaluates stdout/NO_COLOR and compiles redaction patterns | Preserve order and canonical module identity |
| client | Selects WebSocket library keyword compatibility at import | Keep dependency behavior and secret-safe failures |
| deploy/render_units | Adds repository parent to sys.path | Moving it changes template/entry discovery |
| operational_entry | Mutes outputs before importing operations/main | An eager wrapper/package import can violate this security boundary |
| test_ws_capture | Imports optional Playwright at top level | Not a standard guarded-suite entrypoint |

Inspected normal runtime imports do not themselves justify opening a database or initiating network activity. This is not a universal guarantee for every optional diagnostic. The existing guarded runner remains the authority for controlled import/CLI tests.

## 4. Path and consumer risk assessment

| Anchor/consumer | Current contract | Risk if moved |
| --- | --- | --- |
| runtime_paths.py:8 | Repository root anchored to current file | Private root/default paths redirected |
| services.py:17 and derived paths | ROOT plus TIKTOK_RUNTIME_DIR; legacy session directory | Wrong config/preferences/session lookup |
| ledger.py:47–50 | root or TIKTOK_RUNTIME_DIR + state; default ledger/run.lock | Different database or lock silently selected |
| qrlogin.py:33 | Adjacent sesion directory | Different session destination |
| client.py | Adjacent legacy auth, plugins, state paths | Wrong plugin/session/ledger paths |
| core/api.py:13–16 | Parent-parent root and UID cache | Wrong cache/root; do not inspect cache to test this |
| main.py default config | streak.json remains relative to working directory | Moving entrypoint may alter Owner commands/cwd expectations |
| TUI subprocess routes | ROOT/main.py and cwd=ROOT | Broken login/dry-run child commands |
| deploy/render_units.py | Repository parent and adjacent unit templates | Broken rendering/input validation |
| systemd templates | Explicit WorkingDirectory and operational_entry.py | Loss of muted entry boundary or wrong root |
| tests/run_offline.py | Parent-root discovery and protected runtime paths | Guard might protect the wrong directory |
| tests fixture imports | ledger_fixtures and test search paths | Discovery/import failures |
| test_ws_capture.py | Root-based manual profile under work | Different private profile location |

No move of actual config, session, state, database or browser profile is proposed. Runtime root contracts must be tested with temporary synthetic directories, never real runtime data.

## 5. Security and regression coverage

The existing hardcoded WS key regression in tests/test_ws_auth_boundary.py scans root *.py and core/signers/plugins/deploy/tests recursively. It does **not** automatically cover a new application/ or relttk/ directory. Before any future move, scanner discovery must cover canonical implementations and compatibility surfaces; a synthetic forbidden-pattern fixture should prove the new directory is scanned. Do not insert actual keys or test literals in production defaults.

tests/test_legacy_send_closure.py inspects client.__file__ with AST and verifies legacy methods immediately refuse unsupported sends. A shallow wrapper may contain no implementation for that scanner to inspect. Tests must follow the real class definition and exercise every old/new public surface.

Tests also patch cli.CONFIG_PATH, main/services objects and oneshot functions. A wrapper using import * copies attributes while function globals remain in the canonical module: monkeypatches to the old wrapper may stop affecting behavior. Aliasing through module identity needs a specific design and proof, not an assumed transparent shim. Duplicate old/new module loading can duplicate caches, exception classes and global state. Preserve exception identity and any __reduce__ importability; SQLite history is not presumed to use pickle.

Identity Contract stays BLOCKED. Preserve verified account/session binding, explicit WS auth, FIFO/atomic claim, immutable request snapshots, idempotency, quota/cooldown, UNKNOWN handling, consent versions, budget marker accounting and muted operational output. No new fallback, retry, bootstrap or implicit migration.

Relevant coverage:
- WS boundary, independent review and safety tests: explicit auth, session pair matching, fail before connection.
- Legacy send closure: prohibited raw sends remain refused.
- Queue/ledger/rate-limit tests: FIFO, transactions, idempotency, markers and Asia/Ho_Chi_Minh quota.
- Rotation/hardening/UNKNOWN tests: immutable snapshot, cancel/skip races and append-only history.
- Worker/scheduling tests: consent ABA versions, bounded echo handling, no resources held during waits, atomic re-admission, manual/UNKNOWN budget.
- Runtime paths/readiness/identity tests: strict private roots and BLOCKED identity.
- Migration/deployment/operations tests: explicit schema upgrades, backups, rollback, entrypoint and templates.

Security hygiene remains accepted Phase5A scope. No credentials, session artifacts or runtime DB were read. Previously published Git history may retain an old WS literal; this audit neither verifies revocation nor authorizes history rewriting. Source architecture cleanup cannot remediate an exposed credential. Debian live identity/transport behavior remains unverified.

## 6. Alternatives and exact proposed maps

### A — Keep source locations; improve navigation (recommended)

All 70 Python paths KEEP. No wrappers, import edits or source deletion. A possible separately approved documentation deliverable is docs/architecture/MODULES.md, linked from README, containing the inventory, runtime flow, path anchors and safety coverage.

Benefits: zero runtime-path relocation, no scanner blind spot, low rollback cost. Cost: root remains broad and the CLI validation dependency remains. This is appropriate until a measurable maintenance objective justifies source restructuring.

### B — Logical application namespace with bounded compatibility

Proposed new package: application/, inert application/__init__.py.

| Existing path | Proposed canonical location | Existing public path |
| --- | --- | --- |
| cli.py | application/cli.py | KEEP compatibility surface |
| services.py | application/services.py | KEEP compatibility surface |
| tiktok_tui.py | application/tui.py | KEEP compatibility surface |
| All other tracked Python files | Unchanged | KEEP |

Only these three modules move; main's lazy dispatch/imports and consumers would need approved adjustments. services must derive exactly the old repository anchor from unchanged runtime_paths, preserving environment evaluation semantics. No new TUI features.

Before acceptance, select and verify one canonical module identity model. import * is not sufficient. Include old-path monkeypatch, exception identity, optional Textual absence, direct import and script modes. Update security scanner scope first. Keep initial compatibility files; removing them is a later decision.

Benefits: clearer UI/service namespace without moving ledger or transport. Costs: three wrappers plus initializer, not fewer files; service-to-main validation dependency persists; optional GUI/subprocess and patch paths require changes. Rollback: restore moved modules/imports/tests/docs from an Owner-approved snapshot; delete only newly approved package files after confirming paths. Runtime data/schema untouched.

### C — Packages for runtime/storage/application (not recommended now)

Proposed inert package root relttk/ with inert subpackage initializers. Keep existing root public module paths as compatibility surfaces during migration.

| Existing module(s) | Proposed canonical package path |
| --- | --- |
| cli, services, tiktok_tui | relttk/application/cli.py, services.py, tui.py respectively |
| client, oneshot, qrlogin, ws_auth_capture | relttk/transport/<same name>.py |
| worker, scheduling, rotation, unknown_resolution | relttk/runtime/<same name>.py |
| ledger, ledger_migrations, ledger_requests, queue_service | relttk/storage/<same name>.py |
| circuit_breaker, identity_service, readiness | relttk/identity/<same name>.py |
| main.py, operational_entry.py, config.py, runtime_paths.py, log.py, __init__.py | KEEP root anchors/entry surfaces |
| browsercookies.py, test_ws_capture.py | KEEP pending workflow review |
| core/, signers/, plugins/, deploy/, tests/ | KEEP existing locations |

This moves 18 canonical module implementations while retaining 18 compatibility surfaces initially. Relative import fallbacks, plugin discovery, default path anchors and source-inspection tests must explicitly use canonical implementations and unchanged roots. A new namespace does not resolve the 21-module potential SCC.

Benefits: explicit domains and future import qualification. Costs: broad cross-module/test change; wrapper identity complexity; scanner bypass risk; unclear architectural improvement without dependency inversion work. It is inappropriate as a cosmetic cleanup before staging. Rollback requires restoring every old canonical file and all changed consumer/scanner imports as one unit, not mixing versions. No runtime data move or schema alteration.

### Candidate outcomes by file

The inventory table lists every Python file. Its default decision is KEEP under A. Under B only the three named modules become MOVE + KEEP compatibility. Under C only the 18 named modules become MOVE + KEEP compatibility. browsercookies.py/test_ws_capture.py and optional Windows dependency documentation are REVIEW, not REMOVE. **No Python REMOVE candidate is verified.**

## 7. Ordered, reversible future Phase5C candidates

Nothing in this sequence is currently authorized.

1. Owner selects A/B/C and concrete maintenance outcome. Technical Owner and Product Owner must approve source/test/doc scope and rollback boundary.
2. Freeze accepted Phase5A hashes and exact dev base; establish full guarded baseline on the approved Python version. Record platform-specific SKIPs.
3. Document existing public import names, monkeypatch expectations, __file__ consumers, cwd/config semantics, root/env evaluation timing and operational entry order.
4. For B/C, extend static scanner discovery and canonical AST inspection **before moving any source**. Add synthetic path, module identity and wrapper coverage. Prove tests fail against a deliberately unscanned fixture without real secrets.
5. Define inert package initializers and a single module identity model. Verify old imports/direct CLI/optional dependencies before approving first move.
6. Prefer B's small application group if a move is required. Validate services root and TUI subprocess paths with fixture directories. Do not treat storage/runtime moves as independent when their lazy dependency cycles cross groups.
7. For C, separately approve each coherent dependency group. Keep root entrypoints/anchors and explicit auth contract stable. Do not extract validation or redesign service APIs under a file-move label; that would require another reviewed scope.
8. After each group: run AST/import/CLI/scanner/path checks plus full guarded suite. Stop and restore source/consumer/scanner set together on any unexplained regression.
9. Validate Debian 13 and supported Python dependencies in an Owner-operated fixture environment. No service activation, live traffic or identity bootstrap follows from an offline pass.
10. Review compatibility deprecation separately. Do not remove root surfaces merely because new imports work.

A requires only documentation validation and baseline preservation, with trivial document-only rollback. B/C rollback never changes ledger schemas or runtime data.

## 8. Offline validation and acceptance matrix

| Check | Before moves | After each approved group | Acceptance |
| --- | --- | --- | --- |
| SHA256 source/Phase5A freeze | Record exact accepted files | Compare untouched files | No unintended changes |
| AST Python 3.10/3.13 | Parse all tracked implementation/test files | Parse originals plus new canonical paths | Zero syntax failures |
| Import graph/cycles | Record eager/lazy/dynamic consumers | Recompute with packages/wrappers | No new eager cycle |
| Guarded imports | Network/runtime protection enabled | Old and canonical names; optional libs absent/present where fixture permits | No network or runtime writes; one module identity |
| CLI help | main/operational/admin approved commands | Direct root and deployment command paths | Same safe commands/help, no DB initialization |
| Canonical AST security scans | Existing root coverage | Scan new dirs and wrappers, canary fixtures | No uncovered implementation |
| Fixture paths/cwd/env | Old root/config/session/state contracts | Different cwd, synthetic runtime root, symlink/private-root rejection | Exact existing semantics |
| Monkeypatch/exception compatibility | Legacy test patch targets | Canonical and legacy imports | Same globals/class identity, no duplicate state |
| Deployment templates | Current entry/root inputs | Renderer plus static unit command check | Muted operational entry preserved; no systemd action |
| Full guarded offline suite | 390/387 PASS/3 SKIP accepted baseline | Same suite + approved new tests | Zero FAIL/ERROR; every SKIP explained |
| Documentation links | Existing Phase5A links | Local relative links and anchors | Zero broken paths |
| Debian 13/Python 3.13 fixture | Not certified on Windows alone | Owner-operated offline dependency/import suite | Report native platform evidence, no live claims |

Unrestricted pytest discovery is not an equivalent substitute for tests/run_offline.py: manual root diagnostics can import optional capture tools. Existing guarded network/runtime protection must remain active. No test may rely on credentials or real state. A compile/import pass alone does not certify native wheels, Playwright browser support or Debian staging.

## 9. Approval decisions and residual limits

Owner decisions required:
1. Select A (recommended), B, or C; define whether namespace organization warrants its compatibility cost.
2. Approve exact documentation/source/test changes for Phase5C, preserving accepted Phase5A.
3. If B/C selected, approve canonical module identity, root anchors and scanner-first work.
4. Approve any validation extraction as a separate dependency-direction improvement, not an implicit move.
5. Decide optional Windows/manual legacy workflow support and future deprecation; no deletion now.
6. Confirm Owner-operated Debian fixture validation and rollback artifact process.

This report proves static relationships and path risks, not live transport correctness or TikTok streak recognition. API behavior is internal/unofficial. Identity Contract remains BLOCKED. No Safety Layer boundary, schema, auth fallback or sending policy is changed.

STOP at PLAN / REPORT. Await Technical Owner and Product Owner approval before Phase5C.

## 10. Phase5B completion evidence

SHA256 comparison after writing this plan: all 102 frozen existing files remain byte-identical, including accepted source and Phase5A artifacts. The only project deliverable created by this audit is PHASE5B_ARCHITECTURE_PLAN.md. The plan inventories 70 unique Python paths. C2C read_file retrieval of this report was verified. No full regression rerun is claimed for this read-only audit.

