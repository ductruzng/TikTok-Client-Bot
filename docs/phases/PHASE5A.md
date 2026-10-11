# Phase5A — Bounded documentation cleanup REPORT

Completed offline against audited local dev snapshot
`e771161f416249cf0e16d64e20048b434ecf540d`; source/runtime behavior unchanged. Independent Owner review
pending; no Debian staging or Phase5B started. Debian13 is the sole staging target.

## Initial state and boundaries

Verified dev HEAD before changes; initial status contained only the previously
created PHASE5_REPO_CLEANUP_PLAN.md. The supplied official main snapshot remains
unavailable locally; local main/origin naming differences are unchanged.
No fetch/checkout/reset/remote update, staging/commit/push or history rewrite.
No real credentials/session/runtime DB, SSH/VPS/systemd or TikTok traffic.
The guarded runner allows loopback required by asyncio, blocks external network.

## Exact moves (18, no overwritten destinations)

| Original root path | New path |
|---|---|
| `PHASE2.md` | `docs/phases/PHASE2.md` |
| `PHASE3A.md` | `docs/phases/PHASE3A.md` |
| `PHASE3B.md` | `docs/phases/PHASE3B.md` |
| `PHASE3C.md` | `docs/phases/PHASE3C.md` |
| `PHASE3D.md` | `docs/phases/PHASE3D.md` |
| `PHASE3E.md` | `docs/phases/PHASE3E.md` |
| `PHASE4A.md` | `docs/phases/PHASE4A.md` |
| `PHASE4A_IDENTITY_CONTRACT_PLAN.md` | `docs/phases/PHASE4A_IDENTITY_CONTRACT_PLAN.md` |
| `PHASE4A_PLAN.md` | `docs/phases/PHASE4A_PLAN.md` |
| `PHASE4B.md` | `docs/phases/PHASE4B.md` |
| `PHASE4B_PLAN.md` | `docs/phases/PHASE4B_PLAN.md` |
| `PHASE4C.md` | `docs/phases/PHASE4C.md` |
| `PHASE4C_PLAN.md` | `docs/phases/PHASE4C_PLAN.md` |
| `DEPLOY_DEBIAN.md` | `docs/operations/DEPLOY_DEBIAN.md` |
| `PHASE4D_OWNER_CHECKLIST.md` | `docs/operations/PHASE4D_OWNER_CHECKLIST.md` |
| `REVIEW.md` | `docs/security/REVIEW.md` |
| `EVIDENCE_PHASE4_SECURITY.md` | `docs/evidence/EVIDENCE_PHASE4_SECURITY.md` |
| `TERMUX.md` | `docs/archive/TERMUX.md` |

13 phase reports/plans moved to docs/phases; two operations guides, one security
review, one evidence document and one archived Termux guide moved as approved.
Root TERMUX.md is a new short retirement notice for unchanged CLI references.
PHASE5_REPO_CLEANUP_PLAN.md remains at root and byte-identical.

## Documentation/ignore modifications

- README rewritten for current Debian13 navigation, guarded runner, 390-test
  security baseline, unchanged safety gates and Identity Contract BLOCKED.
  Removed current Termux deployment direction and stale active TUI-scheduler
  description; no Python behavior was changed.
- Moved files received relocation/historical/retirement notices and correct
  relative hyperlinks. Each original document body was compared against its
  pre-move copy after only approved hyperlink rewrites; historical decisions,
  command examples and test results are preserved.
- Security evidence retrieval text records original historical path, current
  docs/evidence path and original C2C execution_output ID13; its 390-test trailer
  and historical result were not replaced by the cleanup run.
- .gitignore adds *.sqlite, *.sqlite-wal, *.sqlite-shm, *.sqlite-journal,
  root /session.json, /credential.json and /browser-profile/. Synthetic filename
  probes confirm these exclusions. Existing source, tests, sample JSON and
  requirements probes remain visible. No real credential file was inspected.
- PHASE5A.md is this new report. No original Python/tests/requirements/templates,
  sample JSON, schema or migration was modified or relocated.

Before:20 root Markdown documents plus the untracked audit plan.
After:18 original documents under docs/, root README/CHANGELOG, root Termux
retirement notice, audit plan and this report. Python/core/signers/plugins/tests/
deploy/requirements/sample locations unchanged. No file removal candidates acted on.

## Hash/provenance verification

**78 frozen tracked files byte-identical**, including70 Python files,4 requirements,
2 systemd templates, streak.json and LICENSE. Frozen manifest SHA256 (sorted JSON
path->hash map): `663f2d0d6859cd26926a9701a5027a4057026046b70147544203a383124a2ade`.
Before/after18 document mappings verified; all destination paths were absent and
within workspace before moves, no symlink destinations accepted.18 body-preservation
comparisons PASS (labels/links and explicit evidence-path update are the only moved
body changes). Audit plan hash unchanged; local HEAD unchanged.
Per-file baseline hashes and exact original Markdown/README/.gitignore bytes are
retained locally in `work/phase5a-c8917d2c1fbc4ac2a3b7cd35c9c0796a/`.
This rollback material contains only reviewed source hashes and documentation,
not real credentials/runtime data; it is excluded from Git/source packages.

## Offline regression evidence

Command: `.\work\verify-venv\Scripts\python.exe -B tests/run_offline.py`

```text
Ran 390 tests in 41.417s
OK (skipped=3)
Offline guard: external network and real runtime files blocked.
```

**390 total,387 PASS,3 SKIP,0 FAIL/ERROR**; 41.417 seconds, exit0.
No count/skip deviation from accepted security baseline. The unchanged skips are
POSIX permission testing on Windows and two actual WAL backup tests lacking
sqlite3 no-checkpoint-on-close capability on the accepted Python3.10 build.
Original full-log SHA256: `5b1607c2085aff7771a9cfd23159cec09ab1c5d4b8ffea553da9dbb136438ca7`.
Only sanitized completion trailer is published through C2C; no raw transcript.

Additional checks: all70 Python ASTs PASS under3.10 and3.13; guarded import smoke
13 modules PASS; guarded help-only checks main --help, worker-run --help,
schedule-tick --help and ws-probe --help:4 PASS. Root executable/runner paths5 PASS.
Initial checker treated a valid plugins/ directory hyperlink as a missing file;
corrected directory handling passed without changing that valid link. An initial
shell quoting error in the help check was corrected; final guarded check passed.
Final documentation check: 60 local targets (1 directory target), 2 heading anchors,0 broken links. Markdown fences balanced across all current documents.

## Risks and rollback

Remain REVIEW-only and unchanged: browsercookies.py, requirements/windows.txt,
test_ws_capture.py. No verified unused files removed. Legacy fyp2 helper dependency
gap, historical key exposure, limited secret detection and actual Debian13/POSIX/
full3.13 suite verification remain unresolved. Identity stays BLOCKED; root retired
Termux notice covers legacy CLI diagnostics without modifying Python.

Rollback: use the exact table above in reverse, first refuse destination collisions;
restore saved original root documentation bytes and remove only the cleanup-generated
root retirement notice when restoring original TERMUX.md. Restore original README/
.gitignore from local snapshot. Keep/handle new audit/report artifacts explicitly.
Do not delete unrelated files, touch runtime, run migration or rewrite Git history.
No rollback has been executed; no DB/schema/session rollback is required.

STOP at REPORT; await independent Technical Owner review.
