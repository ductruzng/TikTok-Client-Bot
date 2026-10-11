> Historical record: original phase decisions and test counts are retained. They do not certify the current release. Debian 13 is the sole current staging target; Identity Contract remains BLOCKED. Run repository command examples from the repository root. See [current operations](../operations/DEPLOY_DEBIAN.md) and [current security baseline](../evidence/EVIDENCE_PHASE4_SECURITY.md).

# Phase 3D — Durable Queue, UNKNOWN Resolution & Legacy Send Closure

Status: IMPLEMENT / offline TEST completed; awaiting independent Technical Owner review.
Authorization: `phase3d-implementation`, approved decisions A–E and safety addendum.
No Phase 4 work, Git operations, Debian deployment, real TikTok calls, real session
access or runtime database initialization/migration were performed.

## Implementation and schema V6

One SQLite database remains authoritative. `send_requests` is still the only
source of request status, transmission markers and quota. No counter, lease,
broker, daemon, scheduler or dependency was added.

Additive V6 tables:

- `queue_entries`: `enqueue_seq INTEGER PRIMARY KEY AUTOINCREMENT`, unique
  request FK, nullable `session_name`, `policy_reference`, `policy_fingerprint`.
  Routing fields are either all NULL (UNBOUND) or all present. The SHA-256
  fingerprint includes session, normalized targets, content/catalog and Settings.
  Queue identity/deletion are forbidden; routing updates require a queued request
  with no transmission marker. Changes create immutable `QUEUE_BOUND` audit events.
- `unknown_resolution_events`: append-only event ID, request FK, action, required
  reason/evidence, preview fingerprint, UTC epoch milliseconds, optional unique
  replacement request FK. A partial unique index permits only one final
  CLOSE/REPLACE decision per UNKNOWN; KEEP_BLOCKED reviews may accumulate.
  Triggers prohibit decision update/deletion and decisions on non-UNKNOWN or
  already resolved requests.

All requests have a queue entry, including historical terminal requests. Sequence
allocation and request creation commit in the same `BEGIN IMMEDIATE` transaction.
Migration imports existing rows in rowid order as a **migration order**, without
inventing historical timing or account/session routing. All imported routes are
UNBOUND. Existing requests, legacy data, UNKNOWN, pending markers, rotation and
audit records remain unchanged; UNKNOWN is not automatically resolved.

## Queue and common admission

`services.send_plan` remains the CLI/TUI entry. Existing `--send`, CLI, TUI and
the new consumer use `ledger_requests.start_transmission` / `check_admission`:

1. Existing V6 schema, verified session→UID binding, exact route/reference and
   current policy fingerprint are required. No guessed UID or auto-binding.
2. Snapshot checks retain Phase 3B's separate old-snapshot approval. Rebinding
   routing never approves changed templates; fixed-content changes require a new
   request instead. Atomic claim Settings must equal the bound current policy.
3. Phase 3A quota, cooldown/window, unresolved UNKNOWN and global pending checks
   use `send_requests`. All applicable quota reasons and usage are preserved.
4. Strict FIFO applies across campaigns within `(account, conversation)`.
   A queued/pending older head cannot be overtaken. A blocked head does not hold
   unrelated conversations. Both circuit scopes gate the claim.
5. Marker and audit event commit atomically immediately before the packet send.

The runner holds the existing process RunLock for its entire finite run and
reuses it through a validated internal handle. It takes a fixed candidate
snapshot, considers each ID at most once and defaults to one transmission.
`--max-jobs` is an explicit bound (1–100) on durable new transmission markers,
including UNKNOWN or a result/cleanup failure after commit. It never sleeps,
retries, polls for new work or switches sessions. Newly enqueued jobs wait for a
later explicit run. This is oldest-eligible ordering, not a round-robin scheduler.

Request/key/client ID and exact payload/snapshot survive restart. Queue enqueue
and one-shot share the existing task-key encoding. A terminal replay is returned
before credentials, network or recovery writes, even if a circuit subsequently
opened. A replay does not claim quota or select another template. Unbound
accounts still fail closed. A mixed batch that needs new execution remains
subject to circuit/queue admission.

Routing rebind previews include the current binding audit event ID, preventing
stale/ABA confirmations, and are rechecked inside the writer transaction.
Session changes during a queue run are refused, including another alias of the
same verified account. Pending crash recovery retains the existing conservative
UNKNOWN + circuit OPEN transaction.

## UNKNOWN decisions

The original `failed_unknown` request is never rewritten or retried. Claim,
rotation skip and breaker reset share the predicate: UNKNOWN without a final
CLOSE/REPLACE event. Decision previews include original request, decisions,
outstanding UNKNOWN, active requests, rotation state, queue routing, circuit
versions, daily usage and a fingerprint; stale/concurrent decisions are refused.
Reason and observation/reference are mandatory; common credential assignments,
URL queries, control characters and raw multiline logs are rejected.

- `KEEP_BLOCKED`: records review only; the UNKNOWN remains unresolved.
- `CLOSE_WITHOUT_RESEND`: Owner accepts uncertainty and removes the outstanding
  barrier. The old key can never execute again. Future new requests may be
  created, subject to all limits and circuits.
- `AUTHORIZE_REPLACEMENT`: closes uncertainty and creates exactly one linked,
  queued request in the same transaction. It has a fresh request ID, idempotency
  key and client UUID, while preserving exact payload, snapshot, revision,
  campaign/selection metadata and intent. It does not transmit.

None of these actions confirms SUCCESS, refunds quota, advances rotation or
resets a circuit. Only correlated server echo commits SUCCESS. A replacement
UNKNOWN requires a separate review of that new request. An active rotation
request, stale selection, unavailable verified routing or missing legacy payload
prevents replacement. Configuration drift holds the old snapshot through normal
queue/Phase 3B checks. Owner can still explicitly cancel and skip selection.

For same-day replacement blocked by limit=1/repeat=false: `unknown-show` displays
usage and current Settings; queue preview/claim shows the actual blockers and
retry information. Owner must explicitly edit Settings and rebind the queued
policy if increasing the limit/repeat permission. UNKNOWN's marker stays counted.
Circuits require a separate explicit reset after all relevant UNKNOWN is resolved.
`retry_at` is an evaluation time, never an automatic schedule.

## CLI commands and examples

Examples use disposable paths/placeholders; none of the execution commands below
were run against TikTok or runtime data during this phase.

```text
python -B main.py ledger-preflight --db ledger.fixture.db
python -B main.py ledger-initialize --db new.fixture.db
python -B main.py ledger-migrate --db ledger.fixture.db

python -B main.py queue-enqueue --db ledger.fixture.db --config plan.fixture.json --idempotency-key task-1
python -B main.py queue-enqueue --db ledger.fixture.db --config plan.fixture.json --idempotency-key task-1 --apply
python -B main.py queue-list --db ledger.fixture.db
python -B main.py queue-run-once --db ledger.fixture.db --session VERIFIED_NAME
python -B main.py queue-bind --db ledger.fixture.db --request-id REQUEST_ID --config plan.fixture.json

python -B main.py unknown-show --db ledger.fixture.db --request-id UNKNOWN_ID
python -B main.py unknown-resolve --db ledger.fixture.db --request-id UNKNOWN_ID --action CLOSE_WITHOUT_RESEND
python -B main.py unknown-resolve --db ledger.fixture.db --request-id UNKNOWN_ID --action AUTHORIZE_REPLACEMENT
```

Enqueue is preview-only unless `--apply` is supplied; it never sends.
`queue-run-once` is offline preview by default. Future authorized live execution
requires `--execute`, an interactive terminal, RUN confirmation and per-request
SEND confirmation. It is interactive-only in 3D; ordinary `--yes` is insufficient.
Binding requires preview, reason and BIND confirmation. UNKNOWN resolution
requires preview, reason, evidence and an exact challenge combining action,
request ID and fingerprint. Existing one-shot noninteractive consent remains
`--yes` plus an explicit idempotency key; it obeys the same atomic queue claim.

## Migration, backup and rollback

Initialization/migration remain separate explicit administration, never a side
effect of send/status/dry-run. Sending with a missing or V5 database stops before
credentials or TikTok. Preflight is read-only and reports counts, unbound queued
rows, pending/UNKNOWN and errors. Invalid schemas/timestamps are not repaired.

Explicit migration rechecks preflight under RunLock + `BEGIN IMMEDIATE`, uses
SQLite Backup API through a separate committed WAL reader, applies additive DDL,
imports routing/order, records V6 and validates integrity/FKs/schema before commit.
Re-running V6 migration is a no-op. Injected failure after V6 DDL rolls back all
changes; backup remains available. Fixtures verify restore to a separate V5 file.

Rollback after deployment would require all writers stopped and an explicit
restore/reconciliation decision. A pre-V6 backup does not contain later writes;
restoring it over a used V6 database can lose quota/history and cause duplicates.
No in-place downgrade, automatic restore or runtime apply was attempted here.

## Legacy closure and audit coverage

The six legacy methods `send_message`, `send_video`, `send_reaction`,
`delete_message`, `delete_message_everyone`, `remove_reaction` raise
`UnsupportedSafetyOperation` as their first operation. `LttkClient.run()` does
the same before login/auth/plugin/socket access. Names and source bodies remain
for import compatibility; no fake success values or unsafe opt-out were added.

Repository-wide sink search covered Python outside work/tests, plugin callbacks,
public exports, CLI/TUI/service entry points and HTTP call sites. AST + behavioral
tests cover all seven guarded methods. Legacy packet send bodies are unreachable;
the retained private heartbeat and run handshake send control `hi`, not messages.
Managed oneshot packet transmission follows the marker claim; auth capture's CDP
`send` is browser instrumentation. Packet builders/echo parsers remain available.

This closes the identified repository DM mutation APIs; arbitrary external Python
or old binaries are not a sandbox. Existing non-DM HTTP mutations such as block,
accept stranger and logout were not expanded/refactored. Plugin sample upload
remains disabled/inert. `ponytail-review`: no extra broker/counter/lease/retry layer
or dependency to remove within approved scope; retained legacy bodies cannot be
deleted under the Owner's compatibility requirement. Net: 0 lines proposed to cut.

## Files changed/created

Runtime modified: `ledger.py`, `ledger_requests.py`, `ledger_migrations.py`,
`circuit_breaker.py`, `oneshot.py`, `services.py`, `main.py`, `client.py`.
Runtime created: `queue_service.py`, `unknown_resolution.py`.
Tests modified: `tests/ledger_fixtures.py`, `tests/test_ledger_v2.py`,
`tests/test_rate_limits.py`, `tests/test_rotation.py`, `tests/test_circuit_breaker.py`,
`tests/test_streak.py`, `tests/test_independent_review.py`,
`tests/test_phase3b_hardening.py`.
Tests created: `tests/test_queue.py`, `tests/test_queue_migrations.py`,
`tests/test_unknown_resolution.py`, `tests/test_legacy_send_closure.py`.
Documentation created: `PHASE3D.md`.

Existing tests now explicitly supply disposable verified bindings, valid targets
and reviewed routing/Settings through fixture helpers. No production admission
checks are globally mocked or disabled by those helpers. Blocked queue fixtures
are explicitly cancelled when a regression intends a new request to become head.

## Verification and remaining limits

Final guarded suite: `python -B tests/run_offline.py` — **240 PASS / 0 FAIL**
(190 baseline + 50 new tests), 20.372 seconds. Evidence: `work/phase3d-tests.txt`.
External networking and real runtime file access are guarded. CLI `--help` passes.
AST parsing passes for all 22 changed Python files.
Coverage includes FIFO/campaign ordering, blocked-head independence, bounded
candidate snapshot, marker-based run bounds, terminal replay, identity/session
drift, Settings drift, stale/ABA routing preview, two-process claim/cancel,
resolution/replacement/reset races, immutable history/quota/rotation, rollback,
WAL backup/restore, missing/wrong schema, and synthetic end-to-end echo sending.
Earlier crash/restart/rotation/idempotency/rate/circuit tests remain in the suite.

Unverified/deferred: Android/Termux, real TikTok auth/transport, recipient delivery,
streak credit, noninteractive queue run manifests, late-echo reconciliation,
protocol restriction/conflicting-echo handling, cross-database coordination,
absolute round-robin fairness and bounded queue capacity/history retention.
Session breaker reset still conservatively checks all unresolved requests.
There is no new identity-bootstrap CLI: a fresh database without an existing
server-verified binding intentionally cannot send/enqueue. Runtime migration or
an explicit identity-setup workflow requires separate authorization/review.

The bot uses unofficial internal TikTok APIs. A correlated server echo is server
acknowledgment, not proof that a recipient received the message or TikTok credited
a streak. Configured limits are internal policy, not guaranteed anti-detection
thresholds. Python venv is dependency management, not a security isolation boundary.

STOP at REPORT; no Phase 4 authorization is implied.

## Independent review acceptance

On 2026-10-10, the ChatGPT Technical Owner reviewed execution iteration 2,
source, tests and this document through the connected workspace and accepted
Phase 3D at the offline-tested level: 240 PASS / 0 FAIL. No further Phase 3D
changes were requested. The task is closed with the deferred limits above;
runtime migration, live sending and Phase 4 implementation remain unauthorized.
