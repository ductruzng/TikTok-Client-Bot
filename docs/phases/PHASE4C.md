> Historical record: original phase decisions and test counts are retained. They do not certify the current release. Debian 13 is the sole current staging target; Identity Contract remains BLOCKED. Run repository command examples from the repository root. See [current operations](../operations/DEPLOY_DEBIAN.md) and [current security baseline](../evidence/EVIDENCE_PHASE4_SECURITY.md).

# Phase 4C — implementation report

Task `phase4c-implementation`, approved A–F plus review addenda.
Status: implemented offline, **STOP REPORT / independent review pending**.
Identity Contract remains BLOCKED. Nothing installed/activated/deployed.

## Delivered changes

- `main.py`: opt-in `--operational-output` for schedule-tick; explicit
  `operational-status` and `ledger-backup`. Existing shared service and exit code
  conventions retained; interactive send/admin previews remain unchanged.
- `services.py`: local operational-status/backup wrappers.
- `operations.py` (new): bounded allowlist metadata, fd/Python sink suppression,
  quiescent-only local status and explicit validated SQLite Backup API.
- `operational_entry.py` (new): systemd bootstrap silences output before importing
  CLI/dependencies. Supports only explicit operational subcommands; raw startup
  failures return 3 without traceback. No new sender or grant authority.
- `deploy/render_units.py` and two `deploy/systemd/*.in` templates (new): reviewed
  per-grant artifacts only, no shell/host commands or activation hooks.
- `tests/test_operations.py`, `tests/test_deployment.py` (new): privacy, backup,
  health, workload, rendering, signal/kill and concurrent-process regressions.
- `DEPLOY_DEBIAN.md` (new), `README.md`: staged Owner install, safe status/backup,
  explicit authority, shutdown, non-destructive recovery and operational gates.
- This report (new). No dependency, schema, Worker/oneshot/admission/identity/
  migration-semantic changes. PHASE4C_PLAN.md remains the approved design record.

## Authority, units and workload

Per-grant service uses exact ID/fingerprint, absolute immutable release paths,
unprivileged relttk account, UMask0077, explicit private runtime and sandbox.
Type=oneshot, Restart=no, startup600s, stop90s; SIGTERM goes to existing stop
handling. Timer evaluates each minute in Asia/Ho_Chi_Minh, Persistent=false,
AccuracySec1s, no jitter/catch-up or authority renewal.
All work calls the existing schedule-tick application service and V8/Worker
parent/FIFO/atomic claim gates. No new counter, manifest recreation or retry.

Renderer requires actual POSIX paths/existence/ownership, exact grant/state,
policy/binding/circuit checks and expiry. Windows unit text tests are simulations.
Strict path syntax refuses control characters, whitespace, quotes, backslash,
dollar, percent specifiers, traversal and unresolved substitutions. Output is
new private artifacts only. No systemctl, installation, daemon-reload or enable.

Conservative accepted rendering profile is **one recipient and daily_budget=1**,
max_wait<=300s, window>=10min and at least ten minutes before local midnight.
Multi-recipient grants fail UNSUPPORTED_WORKLOAD, without modifying consent.
Planning allowance is wait+120s setup+30s one echo+90s stop <=540s. This is a
conservative profile/watchdog budget, **not a proven live HTTP bound**: pagination
is not globally timed. Actual Linux/online timing remains an activation gate.
Unsupported larger workload requires separate review, not silent truncation.

The operational bootstrap is a bounded addition to the planned file scope to
cover pre-import failures. Unit StandardError=null additionally prevents a missing
interpreter/bootstrap from writing raw early stderr. Safe summaries go to stdout
journald. Missing summaries must be investigated; not treated as healthy.

## Privacy and health

No raw log capture (memory is not proportional to logged data). Both fd1/fd2
and Python streams are redirected to devnull before command imports/parse.
Only a <=2048-byte allowlist envelope is emitted to a saved fd. If suppression
cannot be installed, command is not run. Arbitrary nested result/exception data
is excluded: no message/template, cookie/token, auth URL, UID/conversation/session,
payload, path or freeform audit reason is printed in operational mode.
Known fixed reasons and bounded integer counts are allowed. Raw human previews
remain available only through ordinary interactive CLI, not the unit bootstrap.

Health reads only a quiescent V8 snapshot, no credentials/network/DB creation or
migration. Nonempty WAL/journal yields UNKNOWN with fixed diagnostic. Valid
storage reports BLOCKED because identity remains unverified. Grant state/usage
and durable aggregate counts are available without raw consent. Usage reuses
V8 marker accounting including manual/UNKNOWN; occurrence counts are for that
grant's linked requests. No separate monitoring state database.

## Backup, schema and rollback

Schema remains V8, no V9 migration. Explicit backup opens existing private source,
uses RunLock and BEGIN IMMEDIATE plus a separate reader, includes committed WAL,
validates schema/integrity/FKs/all-table and transmission counts. New exclusive
0600 staging/manifest and hard-link publication prevent overwrite. SHA256 and
Python/SQLite versions are recorded privately; files and POSIX directory are
fsynced. Timeout/error retains labelled incomplete evidence, never publishes a
partial copy as success. Backup does not call recover_pending or migration.

Critical compatibility gate: to prevent SQLite's last-writer-close checkpoint,
WAL source requires `Connection.setconfig(SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE, True)`
on source connections. Python3.10 lacks this; it **refuses WAL before mutable
open**. No dependency upgrade or journal-mode change is performed. Native
DELETE-journal fixture backup passes on 3.10. An already installed Python3.13
passes actual committed/persistent WAL Backup API tests. Source main/WAL persist
unchanged on last-close tests; SHM reader bookkeeping may change. No explicit
checkpoint/truncate/delete of source sidecars. Select and validate this capability
on Debian before operational backup; core >=3.10 CLI compatibility is unchanged.

No automatic restore/retention/backup scheduler. Owner recovery preserves original
DB/WAL/SHM/journal evidence and validates in a new private directory. If newer
markers may exist, old backup cannot replace runtime or restart sending. Code
rollback keeps current V8 DB and uses a reviewed V8-compatible release with the
same safety gates. No old-schema rollback by losing transmission/audit history.

## Commands (paths and selectors are placeholders)

```text
python -B operational_entry.py operational-status --db ABS_DB --grant-id EXACT_ID --operational-output
python -B operational_entry.py ledger-backup --db ABS_DB --destination NEW_ABS_BACKUP --operational-output
python -B main.py schedule-tick --db ABS_DB --grant-id EXACT_ID --grant-fingerprint EXACT_FP --operational-output
```

The last command is preview by default. Unit explicitly adds --execute --yes;
only prior Owner authority permits its immutable grant. See DEPLOY_DEBIAN.md
for renderer inputs and staged verification; do not use live data for offline tests.

## Validation evidence

Full guarded suite on Windows/Python3.10: **380 tests, 377 PASS, 3 SKIP,
0 FAIL/ERROR**, 47.056s. Skips: existing POSIX check plus two actual WAL
no-checkpoint capability tests unavailable on Python3.10. Both WAL tests run
and pass in the separate Python3.13 subset; POSIX remains unverified.
Previous accepted baseline: 359 tests, 358 PASS, 1 POSIX SKIP.
New tests cover nested/native sink privacy and unavailable sink, early bootstrap/
parser errors, no raw output despite secret sentinels, quiescent/missing status,
no overwrite/alias/collision, validation/failure/deadline backup, unsupported WAL,
render injection and workload refusal, process competition and abrupt exit.

CLI SIGTERM before marker, after marker with correlated synthetic echo and after
marker with echo timeout are exercised through actual existing CLI handlers using
signal.raise_signal. Echo drains/commits or becomes UNKNOWN; no retransmission.
Spawned child exits immediately after durable marker; restart recovery preserves
marker and records UNKNOWN. Windows signal fixtures are not external POSIX or
systemd signal certification. Fake transport only; no TikTok traffic.

Separate Windows/Python3.13 guarded subset: **4 PASS, 0 SKIP/FAIL/ERROR**, 0.913s,
including committed WAL, rejection during uncommitted writer contention,
persistent WAL/last-connection-close preservation, native restore validation and
concurrent backup publication. Evidence `work/phase4c-wal-tests.txt`.
AST7 and CLI help4 PASS, evidence `work/phase4c-static-checks.txt`.
Full-suite output `work/phase4c-tests.txt`; failed early fsync attempt on read-only
Windows fd corrected to writable staging fd, then tests rerun.

Docker daemon was unavailable; no isolated Linux environment was started or
provisioned. No actual POSIX ownership/flock, systemd-analyze/calendar/sandbox or
timer lifecycle claims. No SSH/runtime/session/live/Git/systemd host actions.

## Outstanding gates

- Identity Contract BLOCKED; no live routing/account certification or bypass.
- Actual Debian/architecture dependencies, no-checkpoint backup capability,
  POSIX tests, sandbox and real external SIGTERM/timer validation pending.
- One-recipient renderer only; live HTTP timing/watchdog adequacy not established.
- Quiescent-only health; active WAL readiness intentionally unavailable.
- No automated alerts/remote monitoring, restore, new daemon or deployment.
- API remains unofficial; correlated server echo is not recipient receipt/read
  or proven streak credit. Rate limits are policy, not guaranteed detection safety.
- Legacy media remains outside managed text Safety Layer; not all Core certified.

**STOP REPORT. Independent review required; do not begin Phase4D.**
