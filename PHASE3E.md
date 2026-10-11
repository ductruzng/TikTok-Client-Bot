# Phase 3E — Finite Automatic Queue Worker

Status: implementation and guarded offline tests complete; independent final-delta review APPROVED (iteration 2, 281 PASS).
Authorization: `phase3e-implementation`, approved A–F, V7 and the four acceptance addenda.
No runtime database/session, live TikTok, Git, Debian deployment, scheduler or automatic enqueue was used.

## Scope and shared safety path

`worker.py` processes a finite, explicitly approved manifest of existing queued,
untransmitted requests. It never creates requests or selects new recipients.
Application services and CLI use the same implementation. Each attempt reuses
the existing RunLock, FIFO checks, atomic transmission claim, rate limits,
snapshot validation, circuit breaker and bounded one-shot WebSocket handling.
Manual CLI/TUI sends retain this same queue/claim path.

Approval binds verified UID/session, exact request identity and snapshot hash,
queue route and latest QUEUE_BOUND event, account AND session circuit versions,
max_jobs, max_wait and expiry. OPEN followed by RESET changes the version and
invalidates old consent. Rebinding an identical route also invalidates it.
Unverified account/session binding fails closed; no identity or routing guesses.

The budget counts every `transmitted=1` marker for manifest members, including
manual transmissions, UNKNOWN and transmissions with cleanup failures. It is
not a SUCCESS counter and is never refunded. The marker and worker authorization
check share the existing BEGIN IMMEDIATE claim transaction, so competing
processes cannot consume the last budget twice.

## SQLite V7 and migration

V7 adds three tables, without altering request, quota or rotation history:

| Table | Purpose |
| --- | --- |
| worker_runs | Immutable run ID, manifest SHA-256 fingerprint, consent JSON and UTC creation time |
| worker_run_requests | Immutable ordered request membership and expected snapshot/routing identity; foreign keys and unique membership |
| worker_events | Append-only approval, first start, progress, wait, revocation and outcome events |

UPDATE/DELETE triggers protect all three tables. Member insertion requires an
untransmitted queued request. A partial unique index permits exactly one
RUN_STARTED event per run. Event timestamps cannot move backwards in history.
No new transmission counters, queue, credentials or delivery lifecycle exist.
JSON CHECK constraints require SQLite JSON functions; supported by the tested
Windows runtime, not yet verified on Android ARM64 or Debian.

The existing explicit ledger-preflight / ledger-migrate commands now target V7.
Read-only preflight validates source schema/data without creating files. Apply
uses SQLite Backup API (including committed WAL), validation and one transaction.
V6 data and audit history are preserved. Reapplying V7 is a no-op. Send/status
paths reject missing or older-schema databases and never initialize/migrate.
Do not run migration on the real ledger without separate Owner approval.

Rollback tests cover transaction failure and restoration of the V6 backup.
There is no in-place V7 downgrade. Restoring a pre-migration backup after new
activity would lose those later events/markers and could allow duplicates;
stop all processes and preserve the current database/WAL before any operational
restore. A backup is not a safe way to erase transmissions.

## Waiting, restart and outcomes

Defaults: max_jobs=1 (range 1–100), max_wait=300 seconds (range 0–86400), expiry
at the next Asia/Ho_Chi_Minh midnight. Explicit expiry requires a timezone offset.
max_wait is the elapsed horizon from the durable first start, including downtime;
resume cannot renew it. max_wait=0 permits one no-wait pass. Effective deadlines
combine consent expiry, persisted UTC deadline and an in-process monotonic clock.
Clock rollback fails closed; forward jumps can expire consent early.

Only whitelisted temporal admission reasons with concrete retry timestamps can
trigger waiting. All simultaneous blockers must be temporal. FIFO, changed
snapshot/policy/routing or other holds cannot be disguised by cooldown. Independent
conversation heads may proceed; FIFO within each conversation remains enforced.
The worker sleeps until the earliest eligible head (using that head's latest
blocking time), with a one-second minimum backoff to avoid stale-time spinning.
No RunLock, SQLite connection or WebSocket survives a wait. Every wake rechecks
consent and admission; the final check occurs atomically at transmission claim.

UNKNOWN/circuit or identity failures stop for Owner review. No retry, automatic
resolution/reset or quota refund occurs. SIGINT/SIGTERM request graceful stop:
before a marker, no quota is consumed; after a marker, bounded echo handling
finishes without retransmission even if consent expires or is revoked. Forced
termination is recovered through the existing pending → UNKNOWN mechanism.

Worker COMPLETE means the manifest/budget has been processed, not that every
message succeeded. Inspect individual request outcomes. HELD, WAIT_LIMIT,
NEEDS_OWNER_REVIEW, COMPLETE and REVOKED are closed runs. STOPPED can resume only
within the original consent/deadline. New approval never retries terminal
requests; only existing queued/untransmitted requests can enter a new manifest.

## CLI (examples only; not executed on real data)

Use an explicitly initialized/migrated V7 database. On Windows replace `python`
with `.\work\verify-venv\Scripts\python.exe` if needed.

```sh
python -B main.py worker-preview --db FIXTURE.db --session SESSION --request-id REQUEST_1 --request-id REQUEST_2 --max-jobs 2 --max-wait 300
python -B main.py worker-authorize --db FIXTURE.db --session SESSION --request-id REQUEST_1 --request-id REQUEST_2 --max-jobs 2 --max-wait 300 --apply
python -B main.py worker-status --db FIXTURE.db --run-id RUN_ID
python -B main.py worker-run --db FIXTURE.db --run-id RUN_ID
python -B main.py worker-run --db FIXTURE.db --run-id RUN_ID --manifest-fingerprint EXACT_HASH --yes --execute
python -B main.py worker-revoke --db FIXTURE.db --run-id RUN_ID
```

Preview, status, authorize without --apply, and run without --execute are read-only.
Authorize --apply requires a TTY, reviewed exact content, a reason and the exact
`APPROVE <fingerprint>` challenge. It stores consent but sends nothing. Executing
requires all of --execute, --yes and the exact stored manifest fingerprint;
ordinary --yes cannot create consent. Revocation separately requires interactive
preview, reason and `REVOKE <run_id> <fingerprint>`; stale previews are rejected.
Revocation is effective against subsequent claims, not an already marked packet.
Exit codes: COMPLETE 0, HELD 1, WAIT_LIMIT 2, NEEDS_OWNER_REVIEW 3, BUSY 4, STOPPED 130.

## Files and evidence

Changed: ledger_migrations.py, ledger_requests.py, ledger.py, oneshot.py,
services.py, main.py, tests/test_queue_migrations.py and README.md.
Created: worker.py, tests/test_worker.py, tests/test_worker_migrations.py,
PHASE3E.md. No new dependencies.

Baseline after integration: 240 PASS. Final full guarded suite:
`work/verify-venv/Scripts/python.exe -B tests/run_offline.py` — **281 PASS,
0 FAIL, 0 ERROR**, 29.068 seconds. The guard blocks external network and real
runtime files. Only temporary fixtures, synthetic identity and fake transport
were used. Intermediate run exposed a duplicated diagnostic keyword; corrected
before the final run. Async debug timing notices are not test failures.

Coverage includes consent bounds/stale previews, independent FIFO heads,
cooldown/sliding window/daily midnight and explicitly authorized next-day wait,
lock/DB release while sleeping, both circuit ABA versions, route-binding ABA,
manual/UNKNOWN marker budgets, two spawned competing claim processes,
atomic revocation/stop/member checks, crash/restart and original deadlines,
shutdown/expiry after marker, cleanup failure, clock skew, cancelled members,
rotation success/replay, mocked correlated echo, CLI read-only/non-TTY gates,
V6→V7 WAL backup, preservation, rerun, failure rollback and backup restore.

Final review follow-up: late concurrent worker progress cannot append over a
closed outcome, and wake/post-pass completion checks authorization/circuits
before reporting exhausted budget. Added regressions for closed-run events and
a manual UNKNOWN consuming the last manifest budget while the worker sleeps.
The earlier 279-PASS execution record is superseded by iteration 2 (281 PASS).

Ponytail review: no new framework, transport, counter or speculative queue layer.
Optional simplification: worker.py's message preview sort could use a precomputed
request-ID-to-position map instead of repeated lookup (clarity/performance only).
No safety guards were removed for brevity.

## Remaining limitations

Live authentication, protocol behavior, Android/Termux signal handling and Debian
deployment are unverified. Unit tests do not prove receiver delivery. SUCCESS is
correlated server echo, not receiver read/delivery confirmation. TikTok APIs are
internal and unofficial; whether bot messages count toward streaks remains
unconfirmed. Rate thresholds are local policy, not guaranteed anti-detection
limits. No scheduler, automatic enqueue, identity bootstrap, systemd or Phase 4
implementation is included. Stop here for independent Owner review.
