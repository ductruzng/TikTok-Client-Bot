# Phase 4B — Bounded Daily Automation (offline)

Status: core conditionally accepted at iteration 1; UI review delta awaiting
final independent acceptance. Identity remains
BLOCKED: core/self_identity.py still accepts no real response contract. This is
not production sending certification. Owner performs online testing separately.
No real credentials/database, HTTP/WS, SSH, Git, migration, activation, systemd
installation or Phase 4C deployment was performed.

## Behavior

One-shot schedule-tick reuses Worker 3E. There is no new daemon or worker loop.
Defaults: disabled, 08:00 Asia/Ho_Chi_Minh, 60-minute window, seven local dates
(maximum 31), one automatic request/account/conversation/date. Daily budget
defaults to recipient count, total budget to recipient count times valid dates.
Explicit smaller budgets are allowed; existing account/conversation quota,
cooldown, FIFO, rotation, UNKNOWN and circuit policies also apply.

AUTHORIZE and ACTIVATE are separate interactive actions, neither sends. Pausing
cannot reactivate old consent; authorize a new grant for future unstarted dates.
Revocation is permanent. Changes observed during a modifying tick/claim record
HELD; restoring policy or resetting circuits cannot revive that grant. Read-only
previews report holds without changing state. New approval does not overwrite
old requests, keys, occurrences or history.

Daily keys use SHA-256 of exact canonical UID/conversation/local-date tuple with
automation:v1 prefix. Keys intentionally omit grant, campaign, alias and schedule
IDs. Same occurrence returns the same manifest/request IDs/snapshots. Cross-
schedule reuse cannot silently create another automatic request that date.
FAILED/CANCELLED are not recreated. No UNKNOWN retry, reset or quota refund.

Creation of all requests, selected immutable rotation snapshots, routes, finite
V7 worker consent and daily membership is one BEGIN IMMEDIATE transaction.
Concurrent ticks cannot create two manifests. An older queued/pending request
holds the entire batch, rather than being adopted or overtaken. Rotation advances
only on existing correlated-echo SUCCESS; an uncompleted random selection is
reused the next eligible date rather than redrawn.

Recurring parent checks run through shared claim admission, including manual
CLI/TUI and queue sends. Omitting worker context cannot bypass them. Durable V8
membership and complete manifest/routing identity must validate; a JSON parent
label alone is rejected. Worker start/wake/completion validates parent authority.
Both session/account circuit audit versions catch OPEN -> RESET ABA.

Budgets query send_requests markers directly for the approved account/recipient
scope and validity timestamps, including manual sends before/after grant creation
within that interval and UNKNOWN. Daily usage uses actual transmission local date.
No separate counters or fabricated SUCCESS. All checks and marker reservation
share the writer transaction. After a marker, bounded echo handling can finish
despite pause/revoke/expiry; stop does not cause retransmission. Forced crash is
recovered to UNKNOWN through existing exclusive-lock recovery.

Late invocations process only today's window. No prior-day catch-up, deadline
renewal, automatic worker reapproval or automatic cleanup of held requests.
Old queued snapshots remain held and may require explicit Owner cancellation
before another day's rotation/FIFO can proceed.

## SQLite V8 and rollback

Four new append-only tables:

| Table | Purpose |
| --- | --- |
| recurring_grants | Immutable grant/schedule definition and fingerprint |
| recurring_events | Sequential audit versions and authorized/activated/paused/revoked/held state |
| daily_occurrences | Unique account/schedule/date, parent version, finite run link and immutable window/fingerprint |
| daily_occurrence_requests | Unique request membership matching finite worker ordinal/account |

V7 request, quota, UNKNOWN, rotation and worker history are preserved. Foreign
keys, JSON/type checks, unique keys, monotonic audit versions/state transitions
and UPDATE/DELETE rejection triggers protect V8 history. No new queue or quota
counter. Schema validation fails closed if required structures are absent.

Only explicit ledger-preflight/ledger-initialize/ledger-migrate administer schema.
Migration rechecks source under the writer lock, uses Backup API including
committed WAL, applies V8 in a transaction and validates before commit. Applying
V8 twice is a no-op. No send/tick/preview initializes or migrates a database.

Rollback tests restore a V7 fixture backup and inject a V8 pre-commit failure.
There is no destructive in-place downgrade. Old V7 code cannot operate V8.
After any new runtime activity, a stale backup must not replace current history:
pause invocation, retain database/WAL and obtain a compatible rollback release.
No runtime rollback/migration was executed.

## CLI examples — placeholders only

Use an explicitly prepared fixture/database and private absolute policy path.
Replace python with work/verify-venv/Scripts/python.exe on Windows if appropriate.

```text
python -B main.py schedule-preview --db ABS_DB --config ABS_POLICY --schedule-id daily --time 08:00
python -B main.py schedule-authorize --db ABS_DB --config ABS_POLICY --schedule-id daily --time 08:00 --apply
python -B main.py schedule-status --db ABS_DB --grant-id GRANT
python -B main.py schedule-activate --db ABS_DB --grant-id GRANT
python -B main.py schedule-tick --db ABS_DB --grant-id GRANT
python -B main.py schedule-tick --db ABS_DB --grant-id GRANT --grant-fingerprint EXACT_HASH --enqueue
python -B main.py schedule-pause --db ABS_DB --grant-id GRANT
python -B main.py schedule-revoke --db ABS_DB --grant-id GRANT
# Separate live authorization/identity verification still required before real use:
python -B main.py schedule-tick --db ABS_DB --grant-id GRANT --grant-fingerprint EXACT_HASH --execute --yes
```

Preview/authorize without --apply/status/tick without mode flags never mutate or
read credentials. Their immutable read-only path refuses nonempty WAL/journal;
they do not checkpoint/create sidecars or repair permissions. Stop writers and
use the approved backup/checkpoint procedure rather than deleting sidecars.
Preview of random rotation displays the authorized catalog, not a promised draw.

Bounds flags: --valid-from DATE, --valid-through DATE, --window-minutes 1..1440,
--daily-budget 1..recipient_count, --total-budget 1..recipient_count*days,
--max-wait 0..86400. Dates are local, inclusive, cannot authorize past dates.
Window is clamped to midnight/expiry. No recipients are discovered automatically.

Authorization challenge: AUTHORIZE fingerprint. Activation/pause/revoke challenge:
ACTION grant_id fingerprint event_version. Each requires TTY, preview and reason.
--yes cannot authorize/activate a grant. --enqueue cannot send. --execute requires
--yes AND exact existing grant fingerprint; every claim still validates parent.
SIGINT/SIGTERM uses the existing Worker graceful-stop event.

Tick exit 0: DUE/NOT_DUE/ENQUEUED/EXISTING/Worker COMPLETE; exit 2: other reported
holds/outcomes; exit 3: refused operation. JSON reports reasons, usage and retry
time when known. COMPLETE is processed manifest/budget, not recipient delivery.
The legacy TUI timer and Scheduler source cannot send from old enabled=true
preferences. Use CLI for recurring administration; no new TUI interface added.

## Files and testing

Created: scheduling.py, tests/test_scheduling.py,
tests/test_scheduling_migrations.py and PHASE4B.md.
Changed: ledger_migrations.py, ledger_requests.py, ledger.py, worker.py,
services.py, main.py, readiness.py, tiktok_tui.py,
tests/test_worker_migrations.py and README.md.

Connection-scoped request/worker insertions are extracted existing logic; public
APIs retain their transaction/interactive semantics. ledger.is_already_attempted
now recognizes V8 in its existing request-history lookup. No dependency added.

Final guarded suite: **358 tests, 357 PASS, 1 POSIX SKIP, 0 FAIL/ERROR**, 41.377s.
This includes 48 new schedule/migration tests. AST checks passed for 12 changed
Python files; schedule CLI help checks passed. The earlier 349-test run is
superseded by this final run. Evidence is in work/phase4b-tests.txt and the
execution report. The full suite denies external networking and real
runtime/session file access; only disposable databases and mocked transport are
used. Migration tests cover WAL backup, rerun, rollback, fixture restore and V7
history preservation. Concurrency tests spawn real competing processes.

Ponytail-review of this task's changed code: no additional framework, dependency,
duplicate queue/worker or counter to remove. No simplification applied after the
final regression run. Prior baseline status lookup omitted V8; corrected within
schema integration. Added shutdown regression exposed a post-marker parent check
overriding STOPPED; corrected while preserving bounded echo and marker history.

## Remaining limits

Identity contract, live auth/protocol, receiver delivery, streak credit, Debian
and Android ARM64 behavior remain unverified. The APIs are internal/unofficial;
limits are local policy, not guaranteed bot-detection thresholds. Legacy media
API risk outside the managed text Safety Layer remains unresolved.

No scheduler is installed or activated. Phase 4C/systemd and online testing are
separate. Read-only previews require a quiescent database. Direct policy edits
that change and restore before any modifying tick/claim observes them cannot be
detected historically; observed drift and circuit/route ABA do remain invalid.
Old held queue/rotation selections are never silently cleared. STOP at REPORT.

## Review delta — truthful legacy TUI status

Task phase4b-review-delta fixes the display finding only. The old scheduler
switch is disabled and always initializes OFF, even if a saved preference says
enabled=true. Its label and summary explicitly say the TUI scheduler is disabled
and CLI scheduling requires recurring consent. Saving a plan persists the old
preference as enabled=false and does not claim activation of CLI schedules.
Saved message/recipient configuration, repeat Settings and reference HH:MM are
preserved. Reading legacy preferences does not rewrite them.

The obsolete periodic timer/no-op callback and unreachable scheduled-key branch
were removed. Explicit Scheduler source still refuses sending; manual preview/
confirmation behavior remains. Readiness now labels the validated schema using
ledger_migrations.VERSION (currently QUIESCENT_V8_BOUND).

Delta files: tiktok_tui.py, readiness.py, tests/test_safety_fixes.py,
tests/test_readiness.py, tests/test_scheduling.py and this document. Headless
Textual regressions verify enabled=true display, disabled switch, retained plan
fields, save behavior and zero send calls. Existing tests assert the obsolete
callback is absent and readiness reports V8. No identity, migration, budget,
consent or Worker admission semantics changed.

Final delta validation: **359 tests, 358 PASS, 1 POSIX SKIP, 0 FAIL/ERROR**,
41.927s; changed AST 5 files PASS. This supersedes iteration 1's 358-test count.
Evidence: work/phase4b-delta-tests.txt, guarded with real runtime/network denied.
The initial new test used an unavailable Textual Static.renderable attribute;
corrected to the installed public content API, targeted TUI tests passed, then
the full guarded suite was rerun successfully. No dependency/API production
change was needed. STOP at REPORT for final independent review.
