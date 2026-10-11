# Phase5 — Repository cleanup audit and plan

**PLAN ONLY; Technical Owner approval required.** Audit date 2026-10-11.
Deployment target: **Debian 13**. Owner has retired the Termux direction.
No source/test edits, file moves/deletions, schema changes or deployment occurred.
Only this plan is created. Recommendations below are not executed.

## 1. Verified repository inventory and scope

Existing clone: `D:/Projects/python_projects/ReLttk-TikTok-Client-Bot`.
Verified branch dev/HEAD `e771161f416249cf0e16d64e20048b434ecf540d`, matching
Owner's dev SHA. Initial status was clean. There are **99 tracked files**:
70 Python (41 outside tests/deploy, 28 in tests, 1 renderer), 20 Markdown,
2 unit templates, 4 requirements files, and .gitignore/LICENSE/streak.json.
Directories: core, signers, plugins, deploy/systemd, tests and repository root.
All 70 tracked Python ASTs parsed under Python3.10 without importing application
code. Byte-hash comparisons found no exact duplicate tracked file pairs.
Current Markdown local hyperlink file targets exist; anchors were not checked.

No tracked credential/session/cookie/auth JSON, runtime DB, virtualenv/cache,
profile, log or private-capture path was found by path inspection. No tracked
generated runtime artifact is approved for removal. Ignored runtime contents
were not read or recursively inventoried. The sanitized security evidence document
is deliberate evidence, not a runtime artifact. This is not a full secret scan.

**Blocker for main/dev comparison:** Owner supplied main SHA
`6289a3b99baa94fca8fd0bcafbfc0b6660783337`, but it is not available locally.
Local main is `52b3c4af798ebc0d15f7d57af57d105dd2d296c0`. Origin still names
`https://github.com/ductruzng/ReLttk-TikTok-Client-Bot.git`, whereas Owner's official
repository is `https://github.com/ductruzng/TikTok-Client-Bot`. Rename/redirect
is plausible, not verified. No fetch or remote modification was performed.
This plan audits the verified dev tree, not the unavailable main snapshot.
Owner must confirm repository identity and exact release SHA before implementation.

**Confirmed unused files: none.** Missing static import does not prove absence
of dynamic, manual or external consumers. No removal is proposed now.

## 2. Proposed directory tree

```text
README.md
CHANGELOG.md
LICENSE
.gitignore
PHASE5_REPO_CLEANUP_PLAN.md  # review artifact; later placement requires approval
TERMUX.md                  # optional tiny retirement notice, not an active guide
*.py                       # existing root Python modules remain in place
requirements*.txt
streak.json
core/                      # unchanged
signers/                   # unchanged
plugins/                   # unchanged
tests/                     # unchanged
deploy/
  render_units.py
  systemd/relttk.service.in
  systemd/relttk.timer.in
docs/phases/               # 13 existing phase reports/designs
docs/operations/DEPLOY_DEBIAN.md
docs/operations/PHASE4D_OWNER_CHECKLIST.md
docs/security/REVIEW.md
docs/evidence/EVIDENCE_PHASE4_SECURITY.md
docs/archive/TERMUX.md     # historical only; no Termux staging/tests
```

Keep README/CHANGELOG/license at root; preserve chronological reports rather
than merging/deleting older designs. Optional docs index can be plain Markdown;
no generator/dependency needed. Debian is the only staging target in this plan.
Windows setup extras are retained for compatibility, not a second deployment goal.

## 3. File-by-file disposition

Each row covers one of the original 99 tracked paths. MOVE is a proposal;
REVIEW is not deletion permission. **No REMOVE-CANDIDATE is verified**. The new
plan is outside this tracked snapshot and remains at root during Owner review.

| Tracked file | Decision | Proposed path | Role / dependency |
|---|---|---|---|
| `.gitignore` | KEEP | `.gitignore` | Credential/runtime exclusion policy |
| `CHANGELOG.md` | KEEP | `CHANGELOG.md` | Historical change record |
| `DEPLOY_DEBIAN.md` | MOVE | `docs/operations/DEPLOY_DEBIAN.md` | Current Debian staging/backup guidance |
| `EVIDENCE_PHASE4_SECURITY.md` | MOVE | `docs/evidence/EVIDENCE_PHASE4_SECURITY.md` | Sanitized 390-test evidence and C2C read path |
| `LICENSE` | KEEP | `LICENSE` | Distribution license |
| `PHASE2.md` | MOVE | `docs/phases/PHASE2.md` | Accepted phase report/design; retain historical evidence |
| `PHASE3A.md` | MOVE | `docs/phases/PHASE3A.md` | Accepted phase report/design; retain historical evidence |
| `PHASE3B.md` | MOVE | `docs/phases/PHASE3B.md` | Accepted phase report/design; retain historical evidence |
| `PHASE3C.md` | MOVE | `docs/phases/PHASE3C.md` | Accepted phase report/design; retain historical evidence |
| `PHASE3D.md` | MOVE | `docs/phases/PHASE3D.md` | Accepted phase report/design; retain historical evidence |
| `PHASE3E.md` | MOVE | `docs/phases/PHASE3E.md` | Accepted phase report/design; retain historical evidence |
| `PHASE4A.md` | MOVE | `docs/phases/PHASE4A.md` | Accepted phase report/design; retain historical evidence |
| `PHASE4A_IDENTITY_CONTRACT_PLAN.md` | MOVE | `docs/phases/PHASE4A_IDENTITY_CONTRACT_PLAN.md` | Accepted phase report/design; retain historical evidence |
| `PHASE4A_PLAN.md` | MOVE | `docs/phases/PHASE4A_PLAN.md` | Accepted phase report/design; retain historical evidence |
| `PHASE4B.md` | MOVE | `docs/phases/PHASE4B.md` | Accepted phase report/design; retain historical evidence |
| `PHASE4B_PLAN.md` | MOVE | `docs/phases/PHASE4B_PLAN.md` | Accepted phase report/design; retain historical evidence |
| `PHASE4C.md` | MOVE | `docs/phases/PHASE4C.md` | Accepted phase report/design; retain historical evidence |
| `PHASE4C_PLAN.md` | MOVE | `docs/phases/PHASE4C_PLAN.md` | Accepted phase report/design; retain historical evidence |
| `PHASE4D_OWNER_CHECKLIST.md` | MOVE | `docs/operations/PHASE4D_OWNER_CHECKLIST.md` | Owner-operated Debian fixture checklist |
| `README.md` | KEEP | `README.md` | Root navigation/current guide |
| `REVIEW.md` | MOVE | `docs/security/REVIEW.md` | Historical security review; stale names need contextual labels |
| `TERMUX.md` | MOVE | `docs/archive/TERMUX.md; root retirement notice optional` | Retired Android guide; archive only, no supported deployment target |
| `__init__.py` | KEEP | `__init__.py` | Package LttkClient export |
| `browsercookies.py` | REVIEW | `unchanged pending separate approval` | Optional Windows cookie extractor; no internal Python importer found, manual/external use unknown |
| `circuit_breaker.py` | KEEP | `circuit_breaker.py` | Account/session safety and audit versions |
| `cli.py` | KEEP | `cli.py` | Separate interactive CLI; services/main imports and Phase2/3B test consumers |
| `client.py` | KEEP | `client.py` | Managed auth/decoder plus guarded retained legacy methods |
| `config.py` | KEEP | `config.py` | Shared defaults, no embedded WS key |
| `core/__init__.py` | KEEP | `core/__init__.py` | API/protocol export surface |
| `core/api.py` | KEEP | `core/api.py` | HTTP/internal API helpers, dormant fyp2 dependency gap |
| `core/proto.py` | KEEP | `core/proto.py` | Packet builders and signer dependency |
| `core/self_identity.py` | KEEP | `core/self_identity.py` | Unconditional authenticated-self contract refusal |
| `core/signer_client.py` | KEEP | `core/signer_client.py` | All three signers referenced |
| `deploy/render_units.py` | KEEP | `deploy/render_units.py` | Root bootstrap and adjacent template resolution |
| `deploy/systemd/relttk.service.in` | KEEP | `deploy/systemd/relttk.service.in` | Reviewed oneshot operational template |
| `deploy/systemd/relttk.timer.in` | KEEP | `deploy/systemd/relttk.timer.in` | Reviewed timer template; not activated |
| `identity_service.py` | KEEP | `identity_service.py` | Identity preview/binding gate |
| `ledger.py` | KEEP | `ledger.py` | Ledger access, locks and compatibility API |
| `ledger_migrations.py` | KEEP | `ledger_migrations.py` | Explicit V2-V8 administration |
| `ledger_requests.py` | KEEP | `ledger_requests.py` | Canonical requests, markers, quota and atomic claims |
| `log.py` | KEEP | `log.py` | Common logging |
| `main.py` | KEEP | `main.py` | Lazy CLI entrypoint/default dry-run |
| `oneshot.py` | KEEP | `oneshot.py` | Managed transport/correlated echo |
| `operational_entry.py` | KEEP | `operational_entry.py` | Pre-import operational output protection; renderer requires basename |
| `operations.py` | KEEP | `operations.py` | Status, backup and safe metadata |
| `plugins/info.py` | KEEP | `plugins/info.py` | Dynamic plugin discovery; preserve legacy retention; video stub has security regression |
| `plugins/menu.py` | KEEP | `plugins/menu.py` | Dynamic plugin discovery; preserve legacy retention; video stub has security regression |
| `plugins/ping.py` | KEEP | `plugins/ping.py` | Dynamic plugin discovery; preserve legacy retention; video stub has security regression |
| `plugins/react.py` | KEEP | `plugins/react.py` | Dynamic plugin discovery; preserve legacy retention; video stub has security regression |
| `plugins/stickerdl.py` | KEEP | `plugins/stickerdl.py` | Dynamic plugin discovery; preserve legacy retention; video stub has security regression |
| `plugins/videodl.py` | KEEP | `plugins/videodl.py` | Dynamic plugin discovery; preserve legacy retention; video stub has security regression |
| `qrlogin.py` | KEEP | `qrlogin.py` | Private session writer and QR setup; do not execute |
| `queue_service.py` | KEEP | `queue_service.py` | Durable FIFO/admission |
| `readiness.py` | KEEP | `readiness.py` | Runtime and dependency preflight |
| `requirements/auth-windows.txt` | KEEP | `requirements/auth-windows.txt` | Optional Windows-only Playwright setup |
| `requirements/tui.txt` | KEEP | `requirements/tui.txt` | Optional Textual/full-suite UI coverage |
| `requirements/windows.txt` | REVIEW | `unchanged pending separate approval` | Optional pycryptodome linked to cookie helper |
| `requirements.txt` | KEEP | `requirements.txt` | Core websockets/lz4/qrcode/tzdata |
| `rotation.py` | KEEP | `rotation.py` | Snapshot and template state |
| `runtime_paths.py` | KEEP | `runtime_paths.py` | Module-relative private path resolution |
| `scheduling.py` | KEEP | `scheduling.py` | Bounded recurring consent/tick gates |
| `services.py` | KEEP | `services.py` | Shared application service |
| `signers/bogus.py` | KEEP | `signers/bogus.py` | Protocol signing |
| `signers/xdynosaur.py` | KEEP | `signers/xdynosaur.py` | Protocol signing; imports xgnarly |
| `signers/xgnarly.py` | KEEP | `signers/xgnarly.py` | Protocol signing |
| `streak.json` | KEEP | `streak.json` | Unconfigured root dry-run sample |
| `test_ws_capture.py` | REVIEW | `unchanged pending separate approval` | Manual Playwright diagnostic with ROOT/work profile paths; not guarded discovery |
| `tests/__init__.py` | KEEP | `tests/__init__.py` | Package marker |
| `tests/ledger_fixtures.py` | KEEP | `tests/ledger_fixtures.py` | Synthetic fixtures |
| `tests/run_offline.py` | KEEP | `tests/run_offline.py` | Network/runtime guard and root/tests discovery |
| `tests/test_api_inbox.py` | KEEP | `tests/test_api_inbox.py` | Existing guarded regression: api inbox; preserve discovery and coverage |
| `tests/test_baseline_packets.py` | KEEP | `tests/test_baseline_packets.py` | Existing guarded regression: baseline packets; preserve discovery and coverage |
| `tests/test_circuit_breaker.py` | KEEP | `tests/test_circuit_breaker.py` | Existing guarded regression: circuit breaker; preserve discovery and coverage |
| `tests/test_deployment.py` | KEEP | `tests/test_deployment.py` | Existing guarded regression: deployment; preserve discovery and coverage |
| `tests/test_identity_bootstrap.py` | KEEP | `tests/test_identity_bootstrap.py` | Existing guarded regression: identity bootstrap; preserve discovery and coverage |
| `tests/test_independent_review.py` | KEEP | `tests/test_independent_review.py` | Existing guarded regression: independent review; preserve discovery and coverage |
| `tests/test_ledger_v2.py` | KEEP | `tests/test_ledger_v2.py` | Existing guarded regression: ledger v2; preserve discovery and coverage |
| `tests/test_legacy_send_closure.py` | KEEP | `tests/test_legacy_send_closure.py` | Existing guarded regression: legacy send closure; preserve discovery and coverage |
| `tests/test_operations.py` | KEEP | `tests/test_operations.py` | Existing guarded regression: operations; preserve discovery and coverage |
| `tests/test_phase3b_hardening.py` | KEEP | `tests/test_phase3b_hardening.py` | Existing guarded regression: phase3b hardening; preserve discovery and coverage |
| `tests/test_queue.py` | KEEP | `tests/test_queue.py` | Existing guarded regression: queue; preserve discovery and coverage |
| `tests/test_queue_migrations.py` | KEEP | `tests/test_queue_migrations.py` | Existing guarded regression: queue migrations; preserve discovery and coverage |
| `tests/test_rate_limits.py` | KEEP | `tests/test_rate_limits.py` | Existing guarded regression: rate limits; preserve discovery and coverage |
| `tests/test_readiness.py` | KEEP | `tests/test_readiness.py` | Existing guarded regression: readiness; preserve discovery and coverage |
| `tests/test_rotation.py` | KEEP | `tests/test_rotation.py` | Existing guarded regression: rotation; preserve discovery and coverage |
| `tests/test_runtime_paths.py` | KEEP | `tests/test_runtime_paths.py` | Existing guarded regression: runtime paths; preserve discovery and coverage |
| `tests/test_safety_fixes.py` | KEEP | `tests/test_safety_fixes.py` | Existing guarded regression: safety fixes; preserve discovery and coverage |
| `tests/test_scheduling.py` | KEEP | `tests/test_scheduling.py` | Existing guarded regression: scheduling; preserve discovery and coverage |
| `tests/test_scheduling_migrations.py` | KEEP | `tests/test_scheduling_migrations.py` | Existing guarded regression: scheduling migrations; preserve discovery and coverage |
| `tests/test_streak.py` | KEEP | `tests/test_streak.py` | Existing guarded regression: streak; preserve discovery and coverage |
| `tests/test_tui_services.py` | KEEP | `tests/test_tui_services.py` | Existing guarded regression: tui services; preserve discovery and coverage |
| `tests/test_unknown_resolution.py` | KEEP | `tests/test_unknown_resolution.py` | Existing guarded regression: unknown resolution; preserve discovery and coverage |
| `tests/test_worker.py` | KEEP | `tests/test_worker.py` | Existing guarded regression: worker; preserve discovery and coverage |
| `tests/test_worker_migrations.py` | KEEP | `tests/test_worker_migrations.py` | Existing guarded regression: worker migrations; preserve discovery and coverage |
| `tests/test_ws_auth_boundary.py` | KEEP | `tests/test_ws_auth_boundary.py` | Existing guarded regression: ws auth boundary; preserve discovery and coverage |
| `tiktok_tui.py` | KEEP | `tiktok_tui.py` | Existing optional Textual UI |
| `unknown_resolution.py` | KEEP | `unknown_resolution.py` | Append-only UNKNOWN decisions |
| `worker.py` | KEEP | `worker.py` | Finite worker/budgets/admission |
| `ws_auth_capture.py` | KEEP | `ws_auth_capture.py` | Optional Windows explicit-pair auth setup; not executed |

## 4. Dependency and broken-path risks

Verified imports/entrypoints:

- main is a lazy CLI dispatcher; services is shared by TUI/integrations.
  cli.py is independently executable and referenced by tests/test_ledger_v2.py
  and tests/test_phase3b_hardening.py. Keep both CLI surfaces.
- oneshot imports client auth/decoder and core API/packet helpers. client.run
  and legacy mutations reject before side effects; the retained module is still
  used by managed transport. It is not removable legacy-only code.
- Ledger/requests/queue/worker/scheduling/identity/circuit have lazy cross-imports;
  do not flatten or deduplicate them. core/self_identity always raises
  AUTHENTICATED_SELF_CONTRACT_UNVERIFIED. Identity remains BLOCKED.
- core/signer_client references all three signers; xdynosaur imports xgnarly.
  No signer is proved unused. core/proto and core/api consume signing helpers.
- Plugins are loaded dynamically from client._plugins_dir. Missing static
  imports do not mean unused. Video upload stub is disabled and directly tested
  in tests/test_streak.py. Retain all plugins and guarded legacy methods.
- core/api.py:91 lazily imports fyp2; no tracked fyp2 module/requirements entry
  exists. This is a legacy dependency gap, not proof that managed sending needs
  it. Do not invoke it, install a guessed package or refactor it in cleanup.
- browsercookies has no internal Python importer found, but REVIEW/CHANGELOG and
  requirements-windows reference it. Manual/external use unknown: REVIEW only.
- test_ws_capture.py is a standalone browser/profile diagnostic, mentioned by
  REVIEW; it is not discovered by tests/run_offline. A future tools move could
  change ROOT/work paths and security scanner coverage. Do not execute/move now.
- tests/test_tui_services.py imports services.py, not the historical absent
  tui_services.py mentioned in REVIEW. Keep the test; label old documentation.

Paths that would break on source/test/deploy relocation:

- runtime_paths.REPO and services.ROOT are based on __file__; session/config/state
  fallbacks derive from module location. Moving Python could redirect private data.
- main.DEFAULT_CONFIG_FILE is relative streak.json; README commands and service
  WorkingDirectory assume release root. Keep entrypoints and sample there.
- Tests use parents[1], ROOT/sys.path, ledger_fixtures and subprocess entry paths.
  Keep tests and fixture helpers in place. Guarded runner explicitly discovers tests/.
- deploy/render_units derives root via parents[1], reads adjacent systemd templates
  and requires operational_entry.py basename. Preserve pre-import privacy wrapper,
  template adjacency, executable paths and all admission gates.
- tests/test_ws_auth_boundary scans root/core/signers/plugins/deploy/tests.
  Moving any Python to tools/src can drop static credential regression coverage.
  It needs separately approved scanner changes, not a docs cleanup exception.

Docs references needing updates after approval:

- README hyperlinks: TERMUX, PHASE3E, PHASE4A, PHASE4B, DEPLOY_DEBIAN.
  Change current deployment navigation to Debian operations; Termux only archive.
- PHASE4A/its plan reference README/TERMUX; PHASE3E/PHASE4B reference README;
  PHASE4B_PLAN references PHASE3E/PHASE4B/README; PHASE4C/its plan reference
  DEPLOY_DEBIAN/PHASE4C/README. Update links across folders with ../ paths.
- Checklist references DEPLOY_DEBIAN and Identity Contract design; REVIEW references
  README/TERMUX; archive TERMUX references PHASE4A. Keep historical commands clearly
  historical rather than implying Termux support or production authorization.
- main.py, oneshot.py, qrlogin.py and ws_auth_capture.py emit TERMUX.md guidance.
  This is **verified documentation debt** after retirement. Preferred docs-only
  response: root TERMUX.md retirement notice routes to Debian guide and archive.
  Removing/rewording Python messages requires separate bounded source approval.
- EVIDENCE_PHASE4_SECURITY.md embeds its current C2C read path. Publish the new
  evidence path if moved; preserve old execution records as historical evidence.
- REVIEW describes absent historical tui_services.py/work runner and old counts.
  Add historical context, do not rewrite evidence or delete live service tests.
- Phase4D's 380-test table records Phase4C; the current security baseline is390.
  Add current-baseline reference rather than falsifying old test provenance.

Python/dependency compatibility:

- Python>=3.10 follows annotations/readiness. AST parsing under3.10 passed;
  no full import/full3.13 suite was run for this audit.
- Core: websockets>=15.0.1,<16; lz4>=4.4.5,<5; qrcode>=8,<9; tzdata>=2024.1.
  Keep optional Textual>=8.2.8,<9, Windows Playwright>=1.63,<2 (platform marker)
  and pycryptodome>=3.20 separate. No dependency removal is justified yet.
- WAL backup needs Connection.setconfig and SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE.
  Python3.10 lacks capability on accepted build; previous selected3.13 backup
  tests passed. Target build capability, full3.13/Linux suite, native lz4,
  SQLite JSON/timezone and POSIX behavior must be checked on Debian13 fixtures.
- A venv isolates dependencies, not security privileges. Approved Debian guidance
  uses --copies because private path validation rejects symlinked interpreters.
  No Android/Termux testing or deployment is in the Phase5 acceptance matrix.

## 5. Security and Git hygiene

Facts: no suspicious tracked runtime path found; limited production AST checks
found no nonempty access_key/sessionid/password/client_secret/api_key literals.
This is not a comprehensive secret-history/content certification. No real
credentials or DB were read. Numeric device/protocol constants were not assumed
secret; provenance review before source distribution remains necessary without
printing values. Retain the accepted hardcoded-key security regression.

Synthetic check-ignore probes confirmed .env, *.local.json, *.sqlite3/WAL, *.db,
ws_auth/auth/cookies JSON, browser-profiles, state and work are ignored.
Names probe.sqlite/probe.sqlite-wal/session.json/credential.json and singular
browser-profile/file.txt are **not ignored**. These are coverage gaps only,
not discovered exposures. Owner may approve narrow *.sqlite/sidecar and explicit
credential/profile patterns; avoid broad patterns hiding source/fixtures.
Custom runtime roots and backup names require packaging exclusions regardless
of ignore rules. No ignore edit is made now.

.gitignore does not remove already tracked or historical credentials. Earlier
Git history/clones may retain the removed upstream literal. Credential owner
revocation/rotation and any coordinated history cleanup are separate decisions.
No historical blobs or original literal were inspected/reproduced in this audit.
No secret use, history rewrite or Git branch/remote mutation is authorized.
Never stage private captures/tool transcript/venvs/runtime in a source package.

## 6. Ordered reversible implementation proposal

1. Owner confirms official repo and release/dev SHA; do not act on unavailable
   main snapshot. Record safe documentation path/hash mapping before moves.
2. Approve docs destinations, Termux archival/root retirement notice, historical
   labels, README/current-baseline references and optional docs index. Freeze all
   Python/tests/templates/requirements/database schemas and migrations.
3. Check absent destinations/no collisions, then move one group at a time:
   phase reports, Debian operations, security/evidence, retired Termux archive.
   Preserve content and update relative links in the same reviewable step.
4. Update README and publish moved C2C evidence path. No import or runtime path
   change; do not introduce compatibility Python wrappers or bootstrap behavior.
5. Separately approved .gitignore additions can follow synthetic filename probes.
   No actual ignored artifact examination/deletion is part of that operation.
6. Run below offline acceptance gates on disposable fixtures; compare source,
   tests and template hashes unchanged. Stop for review; no deployment/activation.
7. Rollback uses saved old->new mapping and exact document content to restore
   paths/README/ignore changes. Refuse conflicting destinations, never overwrite
   unrelated files. No DB/session rollback because none changes. Git commits or
   revert/branch operations require explicit approval beyond this plan.

No source/dependency/helper removal is part of this proposal. Optional future
review candidates must not block the minimal documentation organization.

## 7. Offline validation and acceptance criteria

Before work: verify baseline evidence via current EVIDENCE_PHASE4_SECURITY.md
and C2C execution_output id13; capture safe source/doc/template hashes. Accepted
baseline: **390 total, 387 PASS, 3 SKIP, 0 FAIL/ERROR**. Not rerun in this audit.

Before/after each doc group: validate exact move map, unique relative destinations,
no symlinks/collisions, Markdown link files/heading anchors, bare references,
root working-directory commands, C2C evidence paths, retirement notices and all
Identity BLOCKED/security warnings. Audit currently verified hyperlink file
existence only, not anchors or execution of every document command.

After approved cleanup:

- AST on3.10 and3.13; imports under tests.run_offline guard for main/services/
  runtime_paths/application modules, without credential/data reads or networking.
  Do not import/execute manual browser diagnostic as an offline test.
- CLI help-only smoke: main --help, worker-run --help, schedule-tick --help,
  ws-probe --help, applicable identity/ledger administration help. The restricted
  operational_entry refuses plain --help (3); do not treat it as normal main CLI.
- Existing `python -B tests/run_offline.py`: same390 tests, Windows3.10
  387PASS/3SKIP/0FAIL/ERROR, no unexplained count/skip change. No test edits.
- Preserve auth/legacy closure, atomic FIFO, quota/idempotency, UNKNOWN and
  rotation, Worker/recurring consent/budget, Identity, migrations/backup and
  operational metadata regression coverage. Do not weaken guards to pass.
- Core-only environment may skip optional UI; this is not the full accepted
  baseline. Install requirements-tui in a disposable full-test fixture if needed;
  production CLI dependencies remain core-only.
- Owner-operated Debian13 offline fixture: full3.13 suite, permissions/ownership,
  locking, dependency/native lz4/TZ/SQLite JSON, NO_CKPT capability/WAL cases.
  Report unavailable capability explicitly; version alone is not proof. Existing
  Windows3.10 skips are POSIX plus two WAL capability tests; Linux skip expectations
  must be approved from actual build capabilities, not copied blindly.
- Static renderer/template checks and existing deployment fixture tests only.
  Host systemd validation/installation/activation, SSH and live traffic need
  separate permission. No true runtime/session/database migration test.
- No secret output, no embedded-key regression, no source/test/template hash
  change, no Identity bypass. Offline tests cannot certify TikTok receipt/streaks.

## 8. Owner approvals, blockers and minimal-complexity findings

Approval needed: repo/branch identity and release SHA;18 document destinations;
Termux retirement notice/archival policy; historical context/current baseline
labels; optional index; C2C evidence relocation; narrow ignore additions and
Debian offline test/skip matrix. Any Python/helper/dependency/test move/removal
is a new scope requiring approval. No Phase5 implementation is approved yet.

Blocker: supplied main SHA unavailable, local main/origin naming mismatch.
Dev-tree audit/plan is complete. Residual risks: historical key exposure,
limited static credential checks, ignore gaps, manual browser diagnostic/profiles,
legacy fyp2 gap/internal API helpers and unverified Debian platform behavior.
Identity Contract stays BLOCKED; binding, budgets, UNKNOWN and manual consent
remain unchanged. Termux is retired, not part of upcoming deployment work.

Ranked Ponytail audit recommendations (no fixes applied):

1. shrink: root docs sprawl; organize Markdown, retain accepted reports.
2. shrink: old review text appearing current; label historical context instead
   of deleting security/architecture evidence.
3. yagni (REVIEW): Windows cookie helper/pycryptodome; remove only with confirmed
   absence of manual/external users and separate approval.
4. shrink (REVIEW): root manual test_ws_capture naming; any tools relocation
   must preserve ROOT/profile paths and security scanner coverage.

Confirmed deletion opportunity: none. Proposed source reduction now:
**0 lines, 0 dependencies**. Favor documentation cleanup, not safety-layer refactor.

STOP at PLAN/REPORT. Await Technical Owner review before implementation.
