> Documentation relocated during Phase5A. Commands assume the repository root. Debian 13 is the only current staging target; Identity Contract remains BLOCKED. Historical test counts below retain their original provenance.

# Phase4 security fix: published execution evidence

Task: `phase4-security-hardcoded-key` — evidence-only review delta.
No source edits or test rerun in this delta.

## Original guarded full-suite result

Command executed previously (Windows Python 3.10):

```powershell
.\work\verify-venv\Scripts\python.exe -B tests/run_offline.py
```

Sanitized verbatim completion trailer:

```text
Ran 390 tests in 45.151s
OK (skipped=3)
Offline guard: external network and real runtime files blocked.
```

390 total = **387 PASS, 3 SKIP, 0 FAIL, 0 ERROR**.
Accepted Phase4C baseline: 380 total, 377 PASS, 3 SKIP, 0 FAIL/ERROR.
Delta: 10 additional passing auth-boundary tests; unchanged skip count.
Skips are the existing POSIX permission and two SQLite WAL capability tests.

## Provenance and sanitization

The complete original final log was read locally and compared byte-for-byte
against its retained security-artifact copy: identical. Its complete successful
unittest trailer and final guarded-run marker were verified; no rerun occurred.
Original log SHA256: `ef37f7511a053183ddc8ed7be918cd998e98cc5bd81fcdb39e7b75dbf74b36fc`.
Sanitized execution-output SHA256 (UTF-8): `b126727ba31b22eaca5a173a5b5b4d723ff5af141ed99b74dbdae4037d03b3d2`.
The published output contains only the three verbatim completion lines above.
All progress output, timing/debug diagnostics, filesystem paths and incidental
log messages were omitted. No original key, credential values/files or raw
transcript is included. The original raw log is not released through C2C.

Additional checks already reported: changed Python AST 4/4 PASS; CLI help
4/4 PASS; focused final auth regressions 10/10 PASS. Their individual outputs
are not claimed as part of the full-suite completion trailer.

## Retrieval and boundaries

Original publication path (historical):
`ReLttk-TikTok-Client-Bot/EVIDENCE_PHASE4_SECURITY.md`.
Current c2c-pyproj `read_file` path (parent workspace):
`ReLttk-TikTok-Client-Bot/docs/evidence/EVIDENCE_PHASE4_SECURITY.md`.
Original execution_output ID13 and its 390-test result remain unchanged.
The same sanitized completion trailer is published with `c2c record` for
`execution_summary`, `test_status` and `execution_output` retrieval.

No Git, SSH, runtime credentials/database, TikTok network, VPS or systemd actions.
No automatic follow-on packaging/deployment. STOP at REPORT for Owner review.
