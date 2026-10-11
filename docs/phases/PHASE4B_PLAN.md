> Historical record: original phase decisions and test counts are retained. They do not certify the current release. Debian 13 is the sole current staging target; Identity Contract remains BLOCKED. Run repository command examples from the repository root. See [current operations](../operations/DEPLOY_DEBIAN.md) and [current security baseline](../evidence/EVIDENCE_PHASE4_SECURITY.md).

# Phase 4B — Automatic Daily Enqueue and Scheduling

TASK_ID: phase4b-plan. Status: PLAN ONLY; decisions A–F need Owner approval.
2026-10-11. No implementation, online requests, credentials/runtime DB, SSH,
Git, host changes or scheduler activation. Owner performs online testing.
Accepted offline baseline is 309 PASS / 1 POSIX SKIP, not rerun for this plan.
Identity Contract remains BLOCKED. This plan does not grant live-send authority.

## Audit findings

- queue_service.enqueue normalizes explicit recipients and uses an existing
  account/session binding, then creates each request in a separate transaction.
  Durable request identity, rotation snapshot and queue route already exist.
  There is no durable daily occurrence or recurring authorization.
- ledger_requests.create_request returns the original request on same-key/same
  intent, rejects conflicting intent, freezes rotation at enqueue and prevents
  a second queued/pending rotation request in the same scope. UNKNOWN, quota,
  FIFO, snapshots and breaker checks are shared at the transmission boundary.
- worker.py consumes exact existing requests only. V7 stores immutable consent,
  members and events. Approval binds policy, route, request identity and both
  circuit versions. Its marker budget includes manual sends and UNKNOWN for
  manifest members. It must not acquire recurring power implicitly.
- services.scheduled_run_key uses exact HH:MM equality and in-memory last_run.
  tiktok_tui._check_schedule polls every 60 seconds and calls send_plan with a
  scheduled key. This is not durable recurring consent or missed-run handling.
  Current sending still fails closed through identity/confirmation gates; the
  proposed schedule must not simply turn that legacy callback into permission.
- readiness has an immutable/quiescent inspection path that rejects nonempty
  WAL/journal. Existing ledger status readers may create SQLite sidecars. Strict
  new previews should use the former and report DATABASE_NOT_QUIESCENT rather
  than silently inspect stale main-file data.
- The strict fresh self verifier accepts no responses today. Synthetic bindings
  enable offline tests only. Automatic enqueue can use an existing reviewed
  binding locally; actual worker execution must still perform fresh verification.
  Readiness must clearly show IDENTITY_CONTRACT_BLOCKED before online execution.

Reviewed: queue_service.py, ledger_requests.py, worker.py, rotation.py,
ledger_migrations.py, services.py, main.py, tiktok_tui.py and PHASE3E.md.

## A — Minimal architecture and scheduling

Recommend a one-shot application operation `schedule-tick`, initially defaulting
to preview. It computes today's due occurrence, optionally enqueues atomically,
and optionally invokes the existing finite Worker. No new daemon, queue worker,
timer thread, framework or dependency. A future external scheduler can invoke
the same command; systemd templates/installation remain Phase 4C.

Use Asia/Ho_Chi_Minh local calendar dates and one HH:MM daily time. Store all
instant timestamps as UTC epoch ms. Proposed delivery window is 1 hour, explicitly
configurable (1–1440 minutes), clamped at the next local midnight and grant expiry.
No catch-up for prior dates. A late tick within today's window may process today's
occurrence once; after it closes, show MISSED with no late transmission/backfill.
A restarted worker keeps its original durable deadline; never renew max_wait.

`--enqueue` changes SQLite but cannot send. `--execute --yes --grant-fingerprint`
may create the due occurrence and run its finite manifest only under explicitly
activated recurring authority. Ordinary --yes is never authorization. CLI flags
are a second execution opt-in, not a replacement for durable recurring consent.
External scheduling is disabled by default and is not installed by Phase 4B.

For multiple accounts, use separate grants and one explicit schedule per account
scope; no implicit session discovery. Process finite scopes sequentially, retain
database-wide concurrency=1, no DB/RunLock/WS while waiting between invocations.
The Worker retains its existing bounded temporal waits inside a finite window.

## B — Bounded recurring consent

Recommend immutable, explicitly named schedule definitions embedded in a new
recurring grant. An interactive preview lists exact UID/session, absolute policy
and DB references, recipient routes, fixed message or complete template catalog
including revisions/mode/campaign, Settings, HH:MM/timezone/window, valid dates,
daily and total marker budgets, max_wait and both circuit versions.

Proposed defaults for approval: seven local dates (maximum 31); one automatic
request per conversation/date; daily budget equal to the selected target count;
total budget equal to target count times approved dates; Worker max_wait=300s
bounded by delivery window. Values are displayed/validated and Owner may choose
smaller budgets. Worker membership/max_jobs stays within its existing 1–100
bound; grants with larger per-day recipient sets are refused, not split into
silently renewed runs. Existing rate/quota Settings remain the stronger limit.

Default state is disabled. `schedule-authorize --apply` requires TTY, mandatory
reason and exact `AUTHORIZE <fingerprint>` challenge, but does not activate/send.
`schedule-activate` separately previews the same grant/version and requires
`ACTIVATE <grant_id> <fingerprint>`. Expiry has no renewal; new dates require a
new explicit grant. Neither existing worker consent nor saved TUI enabled=true
counts as recurring approval.

Pause/revoke are interactive audited actions with stale-preview/version checks.
No automatic reset or resume. Proposed paused grants cannot resume existing
derived runs; a new grant is required for future unstarted dates, avoiding ABA
and old-manifest revival. Revoke is permanent. A completed/held/wait-expired
daily occurrence never derives a replacement run automatically.

Changes to recipients, message/template content/order/mode/campaign, Settings,
policy path, session binding, circuit audit versions or runtime routes invalidate
the grant; restoring the old configuration does not revive consent once a hold
event has been recorded. First tick/claim detecting drift records a durable hold.
Changes not yet observed are still rejected whenever the current fingerprint
differs. Full historical detection of edits outside this app is not guaranteed.
No auto-approval of snapshots or route rebindings; current grant/occurrence
authority remains immutable. Reauthorization only applies to unstarted dates.

## C — Daily idempotency, atomic creation and rotation

Use a deterministic, versioned automatic request key from canonical UID,
conversation ID and local date, independent of grant ID, config revision,
restart and session alias. Proposed automation:v1 + SHA-256 canonical tuple.
Deliberately omit campaign/schedule ID: one logical automatic daily request per
account/conversation across schedules. A changed campaign/payload on the same
key is a conflict requiring review, not permission to create another request.
Manual Intentional Repeat retains its explicit independent keys and Settings.

Reject overlapping active grants for the same account/conversation, even across
campaigns; check active grant event state under BEGIN IMMEDIATE. Account aliases
cannot duplicate a date's logical automatic request. Changed grant or expiration
does not remove old keys, cancelled requests or UNKNOWN history.

One BEGIN IMMEDIATE transaction must recheck grant/version, time/window,
binding/circuits, policy and budget, then create all requests/queue entries,
rotation snapshots, finite worker manifest and daily occurrence links together.
If any recipient is blocked by active rotation/UNKNOWN or any intent conflict,
roll back the entire new occurrence. Existing unrelated rotation requests are
not adopted, cancelled or re-randomized automatically. Other grants may proceed.

Minimal necessary refactor: extract internal connection-scoped helpers from
create_request and Worker preview/authorization insertion. Existing public APIs
continue to own their transaction and preserve semantics. No nested writer
connection, duplicate request insertion code or weakening of interactive worker
approval. New derived approval helper accepts only validated recurring authority
and writes parent provenance, rather than calling interactive authorize silently.

A unique occurrence constraint and unique daily request keys serialize competing
ticks. Same committed occurrence returns its original IDs/snapshots/run; terminal
FAILED/CANCELLED/UNKNOWN requests are not recreated. If the process crashes before
commit, all creations roll back; after commit, resume the exact stored manifest.
Rotation only advances in the existing correlated-echo SUCCESS transaction.
Random preview must show catalog/possible selection, not invoke RNG or promise a
specific future snapshot. Read-only tick preview never advances rotation or writes.

## D — Claim gates, budgets and cancellation

Daily-generated requests must carry durable membership discoverable from the
database, regardless of adapter. Extend shared claim admission to check parent
recurring grant and occurrence for every daily request, including manual --send,
CLI/TUI, finite Worker and queue-run-once. A different Worker consent cannot
override that parent gate. Ordinary non-daily requests retain their existing
admission behavior. No bypass based on omitting a worker context.

Recheck active grant/current event version, immutable policy and bindings,
circuits including OPEN -> RESET, window/expiry and budgets in the SAME transaction
that records transmission_started_at_ms. Worker start/wake also checks its parent,
including empty-manifest/budget-complete paths. Use existing RunLock and admission;
do not hold a transaction or RunLock across external I/O or waiting.

send_requests remains the only source for transmission counts. Recurring budgets
count ALL markers for that grant's UID/recipient scope in its validity interval,
including manual sends and UNKNOWN, not merely worker SUCCESS or member markers.
Daily counts use transmission local date; total counts use timestamp interval.
Use EXISTS/direct predicates to avoid counting a request twice through joins.
No counter table, refunds or quota exemptions. Existing account-wide quota counts
all conversations as before. Manual sends outside the grant may still consume
the existing account quota. These are internal limits, not anti-detection claims.

Before marker, pause/revoke/expiry prevents transmission. After marker, finish
existing bounded echo handling even if authority expires/revokes; never retransmit.
Crash after marker retains quota and recovers to UNKNOWN through existing logic.
UNKNOWN stops the affected scope for review, never triggers retry/reset/replacement.

Expiry/pause/revoke does not delete or silently cancel queued requests. They stay
held for explicit existing cancel/review, preserving FIFO and rotation. Next day's
enqueue is refused when held requests block that scope; report exact IDs and
reason. This may require Owner cleanup but prevents silent content changes.

## E — Proposed SQLite V8 (requires approval)

V7 cannot express future-date authority, durable occurrences and parent claim
revocation. Recommend explicit V8 with four append-only tables, no new queue:

| Table | Contents / constraints |
| --- | --- |
| recurring_grants | grant_id PK, stable schedule_id, consent fingerprint, immutable consent_json, UTC created_at_ms; identity/policy/time/bounds inside validated JSON |
| recurring_events | event_id PK, grant FK, monotonic per-grant event/version, type and sanitized details; AUTHORIZED/ACTIVATED/PAUSED/REVOKED/HELD events |
| daily_occurrences | occurrence_id PK, UID, schedule_id, local_date, grant FK, worker run FK, immutable occurrence fingerprint/window; UNIQUE(UID,schedule_id,local_date), UNIQUE(run_id) |
| daily_occurrence_requests | occurrence FK, request FK, ordinal; PK(occurrence_id,ordinal), UNIQUE(request_id) |

Requests additionally remain protected across different schedule IDs by existing
UNIQUE(canonical_uid,idempotency_key). FK/JSON/type constraints and immutable
UPDATE/DELETE triggers protect history; event versions support exact CAS/ABA.
Current enabled state is derived from latest events, not a mutable counter.
Indexes cover grant/schedule history, occurrence date and reverse request lookup.
Daily operational outcomes come from existing worker/request events, avoiding a
parallel delivery lifecycle. Derived V7 worker APPROVED event details record
authority_kind=RECURRING, parent grant and occurrence fingerprint; V8 links are
mandatory for validation, never trust that JSON tag alone.

Explicit preflight -> Backup API including committed WAL -> BEGIN IMMEDIATE
migration -> validation -> commit. Preserve V7 tables/rows/triggers, UNKNOWN,
rotation, worker consent/events and quota markers byte-for-byte where applicable.
No automatic initialization/migration in tick/send/status. Missing/older/wrong
schema fails before credential/network access. V8 rerun is a no-op. Validate
source data and report blockers without guessing/repairing records.

Rollback: disable invocation and revoke/hold authority, preserve current DB/WAL
and all request/audit history. No destructive in-place downgrade. Old V7 code
must reject V8; rollback to executable V7 code alone cannot safely operate V8.
Restore the V7 backup only in fixture tests or before any post-upgrade activity;
never restore stale production data to erase later markers/UNKNOWN. Operational
rollback after activity needs a separately reviewed compatible release.

## F — CLI, file scope and validation

Proposed commands (design only; none exists or was executed):

```text
schedule-preview --db ABS_DB --config ABS_POLICY --schedule-id NAME --time 08:00 --valid-from DATE --valid-through DATE
schedule-authorize <same bounds> --apply
schedule-activate --db ABS_DB --grant-id ID
schedule-status --db ABS_DB --grant-id ID
schedule-pause --db ABS_DB --grant-id ID
schedule-revoke --db ABS_DB --grant-id ID
schedule-tick --db ABS_DB --grant-id ID                         # preview only
schedule-tick --db ABS_DB --grant-id ID --grant-fingerprint HASH --enqueue
schedule-tick --db ABS_DB --grant-id ID --grant-fingerprint HASH --execute --yes
```

Authorization/activation/pause/revoke require interactive exact preview, reason
and CAS challenge. Status/preview are nonmutating and do not inspect credentials.
Tick may report NOT_DUE, MISSED, DISABLED, EXPIRED, HELD, BUSY or existing Worker
outcomes; expose reasons/usage/re-evaluation times without treating them as a
promise or renewed consent. Live readiness remains blocked until identity is
implemented/reviewed; offline execution tests inject only synthetic transport.

| File | Proposed bounded change |
| --- | --- |
| scheduling.py (new) | Grant lifecycle, pure due computation, transaction orchestration and parent claim check |
| ledger_migrations.py | Explicit V8 preflight/apply/validation and immutable constraints |
| ledger_requests.py | Connection-scoped create helper; parent admission for daily membership |
| worker.py | Connection-scoped manifest insertion; parent start/wake/claim gates without new run loop |
| queue_service.py | Reuse existing routing/FIFO; minimal internal helper integration if needed |
| services.py / main.py | Shared schedule operations and explicit CLI opt-ins |
| tiktok_tui.py | Replace legacy timer send callback with held/disabled guidance to common service; old preferences cannot activate grant; no new UI |
| readiness.py | V8/schema readiness and truthful identity-blocked status |
| tests/test_scheduling.py (new) | Pure dates, grants, recurring authority, daily transactions and integration |
| tests/test_scheduling_migrations.py (new) | V7 -> V8 backup/WAL/rollback/history preservation |
| tests/test_worker.py / existing queue/claim tests | Parent gates on all adapters, preserved V7 worker API behavior |
| PHASE4B.md (future) / README.md | Commands, Owner online test handoff, limits and rollback |

No QR/auth/signer changes, identity parser, TUI feature expansion, systemd install,
daemon, VPS connection or deployment scripts in 4B. Changing legacy TUI timer
behavior and connection-scoped transaction APIs are material proposed changes;
Owner must explicitly approve them with the schema and consent design.

Offline test matrix:

- 07:59/08:00/window cutoff, local midnight vs UTC, month/year leap boundaries,
  forward/backward clock jumps; no historical catch-up or expired grants.
- Default disabled, authorize != activate, TTY/challenges/stale previews, pause/
  activate ABA, expiry, revoked grant and no accidental old-consent reuse.
- Two spawned ticks produce one occurrence/request/manifest; crash before/after
  commit; full batch rollback on one recipient conflict; same daily key/different
  payload; alias/campaign/grant changes cannot generate duplicate logical work.
- Fixed text and rotation snapshots, random restart stability, one active scope,
  SUCCESS-only advancement, FAILED/CANCELLED/UNKNOWN replay, no re-randomization.
- All manual/CLI/TUI/queue/Worker claim paths honor parent pause/revoke/budget,
  including concurrent final-slot claims; manual and UNKNOWN marker budgets.
- Policy/recipient/template/session/route changes, circuit OPEN -> RESET ABA,
  identical route rebind and unknown/unverified identity all hold without reset.
- Restart resumes exact manifest/original deadline; terminal run no replacement;
  due window after downtime, skipped dates, expired queued FIFO blockage.
- Revocation/expiry during wait releases resources and rechecks at wake; after
  marker completes bounded echo, forced crash recovers UNKNOWN, no retransmit.
- Byte/mode/mtime/sidecar snapshots prove read-only preview/status; no credential
  access/network during planning/enqueue; missing/wrong schema rejected early.
- V7 history/constraints preservation, committed WAL backup consistency,
  migration rerun, injected transaction failures, fixture backup restore.
- Full guarded regression suite with fake clock/identity/transport. No live tests.

## Decisions requested and stop point

Approve A–F or adjust: one-shot scheduling adapter rather than daemon; seven-date
grant/31-date maximum and explicit budgets; one-hour default delivery window and
no prior-day catch-up; two-step authorize/activate; pause requires a new grant
for future unstarted dates; one logical automatic request per UID/conversation/
date across campaigns; all-or-nothing daily batch; scopes/manual marker budget;
V8 and universal parent claim checks; strict read-only quiescent previews;
legacy TUI timer removal from automatic sending without developing new UI.

The principal tradeoff is deliberate holding rather than automatic cleanup or
retry: a stale queued rotation scope may need Owner cancellation before later
dates. Multiple grants do not promise recipient delivery or streak credit.
TikTok API is internal/unofficial; server echo is not receiver delivery/read,
and whether these messages count toward streaks remains unverified.

Only this plan was created. No new regression run, source edit, migration,
credentials/runtime access, online request, Git, deployment or activation.
STOP at PLAN for independent review; no automatic IMPLEMENT transition.
