# Phase5D G1 — Foundation relocation

Task: phase5d-g1-foundations; date 2026-10-11. STOP REPORT before G2.
Starting/final dev HEAD: e771161f416249cf0e16d64e20048b434ecf540d.

## Exact scope

Moved config.py -> relttk/config.py, log.py -> relttk/log.py, runtime_paths.py -> relttk/runtime_paths.py. Root implementations are absent. Config/log bytes are identical; runtime_paths changes only REPO from file parent to parents[1], preserving the same repository root.

Added relttk/__init__.py (inert), relttk/compat/__init__.py (stdlib explicit enable), and fixed-target alias files relttk/compat/legacy/config.py, log.py, runtime_paths.py. No other production implementation moved. No eager exports, sitecustomize, meta_path hook or auth fallback.

Import-only consumer edits: queue_service.py, core/api.py, operations.py, identity_service.py, qrlogin.py, deploy/render_units.py, services.py, ledger.py, readiness.py, oneshot.py, client.py, scheduling.py. Each has identical AST after removing import nodes from before/after trees. No queue/ledger/transport/identity algorithms changed.

main.py additionally enables legacy compatibility after establishing its root path. operational_entry.py enables it only inside the existing muted region, before application imports. tests/run_offline.py enables compatibility after installing its audit hook and before discovery. These supported root entrypoints remain in place.

Added tests/test_foundation_layout.py (six actual-module regressions). Updated tests/test_source_layout.py: G0 toy namespace renamed g0_layout_fixture; its path-count assertion checks the exact synthetic alias directory, independent of the real approved compatibility directory. No assertion removed. Updated docs/architecture/MODULES.md to distinguish actual G1 from future groups. Created this report. Requirements, templates, samples, schemas/migrations and historical phase documents unchanged.

## Compatibility and paths

External callers use canonical relttk imports or explicitly call relttk.compat.enable() before legacy names. Fixed aliases substitute the canonical module object in sys.modules. Tests prove alias-first/canonical-first identity for all three real modules, monkeypatch consistency, reload identity and canonical exception serialization. Reload intentionally recreates classes; both aliases see the same new class. Conflicts are refused without silently overwriting cached modules. Bootstrap is idempotent and imports no foundation implementation eagerly.

Config environment and log output/environment evaluation remain at first module import. Existing services/ledger defaults still capture their prior environment values at import. REPO, private-root/outside/symlink refusal, QR/plugin paths and synthetic alternate-cwd dry-run remain covered. No runtime resource was copied or moved.

Scanner includes canonical foundation files and all three aliases. Legacy client implementation coverage stays on unmoved root client.py; transport package is not created in G1. Root Python count is now 24; total Python files 79 including six new package/alias/test files.

## Validation and deviations

Accepted pre-G1 baseline: 408 total,405 PASS,3 SKIP,0 FAIL/ERROR.
Six new foundation cases explain the expected increase to 414.

Focused final: 41 tests,40 PASS,1 SKIP,0 FAIL/ERROR;3.223 seconds. The skip is the existing Windows POSIX permissions case. AST all79 files PASS under Python3.10.11 and3.13.3. Guarded import smoke16 PASS;CLI help-only main,worker-run,schedule-tick,ws-probe:4 PASS.

Initial post-move full run:408 tests,4 failures,3 skips (42.617s). Cause was the G0 toy package using the now-real relttk name cached by explicit runner bootstrap. Renaming the toy namespace restored isolated imports. A subsequent intermediate full run (414 tests,44.230s) used the pre-correction path-count fixture and had one failure because two legitimate legacy directories existed. The final fixture counts its exact synthetic directory. These were explained test-isolation problems, not production safety failures; no scope expansion or weakened guard/assertion.

Final full guarded suite: **414 total,411 PASS,3 SKIP,0 FAIL/ERROR**,47.210 seconds,exit0. The same Windows POSIX permissions and two SQLite setconfig/no-checkpoint WAL capability skips remain; no new skips. Command: `./work/verify-venv/Scripts/python.exe -B tests/run_offline.py`.

```text
Ran 414 tests in 47.210s
OK (skipped=3)
Offline guard: external network and real runtime files blocked.
```

## Preservation

110 reviewed existing files were frozen:92 byte-identical at mapped locations,18 deliberately changed paths listed in preservation.json. Both config/log move hashes match original bytes; runtime_paths anchor-only byte transformation verified. Every import-only consumer passed non-import AST equivalence. All other existing tests, accepted phase reports, requirements/templates/sample/schema code and .gitignore are unchanged. Before/after manifest, exact before Python/MODULES bytes and move map are retained under ignored work/phase5d-g1-evidence/.

## Limits, rollback and stop

Actual G1 foundations are tested; application/transport/storage/runtime/identity relocation is not implemented or certified. Debian13 native dependencies, permissions/locking/WAL and full Python3.13 suite remain unverified. Identity Contract stays BLOCKED. No real sessions/DB/credentials/network/TikTok/SSH/VPS/systemd actions or Git mutations.

Owner-authorized rollback must restore the three implementations to their old root paths and restore every changed consumer/entry/test/MODULES file from the reviewed before snapshot together; remove only the G1-added package/alias/test/report files after workspace-path/hash verification. Preserve accepted prior Phase5 changes. Do not reset/clean Git or touch runtime data. Restart interpreters and re-run guarded baseline after rollback; no rollback executed.

STOP REPORT. Await independent review before G2 or any further source moves.
