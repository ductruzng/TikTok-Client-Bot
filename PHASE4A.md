# Phase 4A — Offline Readiness and Identity Administration

Status: independent review PARTIALLY ACCEPTED (offline readiness/isolation/admin).
**Operational identity is
BLOCKED**, because no authenticated-self response contract has been established
from trusted evidence. This is not a production-ready sending release.
Authorization: phase4a-implementation, approved A–F and three mandatory conditions.
No SSH, live TikTok, real session/database, migration, Git or Debian host changes.

## Implemented

- Common explicit TIKTOK_RUNTIME_DIR resolver. Absolute contained DB/config and
  session/auth paths, ancestor symlink and POSIX ownership/permission checks.
  Legacy Windows paths remain when opt-in is unset. Opt-in forbids global WS auth
  fallback and legacy session enumeration/loading. Settings and ledger accesses
  validate containment. No new dependencies, schema or duplicate worker.
- runtime-preflight local metadata mode plus explicit credential inspection.
  Neither mode mkdirs, chmods, writes credentials, migrates or creates sidecars.
  Immutable SQLite inspection refuses nonempty WAL/journal instead of silently
  ignoring their committed rows. It checks schema/integrity, binding/circuit and
  unresolved UNKNOWN; changing file/sidecar stamps invalidate the report.
- identity-verify default local preview, explicit --live verification and separate
  --apply interactive reason/challenge. Verified service results keep credential
  generation in memory, omit it from public output, and compare it on apply.
  Apply rechecks both candidate account and session circuit versions in the
  binding transaction, including OPEN→RESET ABA. Binding another UID to an
  existing alias is rejected. No reset, quota refund, enqueue or send occurs.
- Pure WS-auth pair validator shared by actual loading and credential preflight.
  Private credential inspection does not invoke the legacy mutating loaders.
- Fresh identity lookup and bootstrap share core/self_identity.py. Generic
  odinId or guessed login-shaped JSON is rejected. Legacy cached UID is never
  evidence for a managed send or bootstrap.

## Concrete unresolved identity blocker

core/self_identity.py currently has **no acceptance rule**: every HTML input is
unverified and fails closed. The repository only provided bare odinId fixtures,
which cannot prove authenticated-self provenance. Inventing a login response
shape would violate the approved requirement. As a result, real bootstrap and
managed sends are blocked before WS/message transmission until a separately
reviewed authenticated-self contract is implemented from trusted evidence.

Positive bootstrap tests use a synthetic provider to exercise transaction,
generation, idempotency and concurrency. They do not prove that verifier can
accept a real TikTok response. No real authentication or response capture was
authorized/performed. Explicit --live may read the messages page, then report a
protocol failure and append the existing circuit audit; it cannot bind an
unverified identity. No --uid override or configuration bypass exists.

Owner review must decide whether to accept the readiness portion while keeping
identity blocked, or approve a separate evidence acquisition/contract-validation
task. This report does not claim full Phase 4A production verification.

## CLI examples (not executed on runtime data)

```sh
python -B main.py runtime-preflight --runtime-dir /PRIVATE/ROOT --db /PRIVATE/ROOT/state/ledger.db --config /PRIVATE/ROOT/policy.json
python -B main.py runtime-preflight --runtime-dir /PRIVATE/ROOT --db /PRIVATE/ROOT/state/ledger.db --config /PRIVATE/ROOT/policy.json --check-credentials
python -B main.py identity-verify --db /PRIVATE/ROOT/state/ledger.db --session SESSION
# Only for a separately authorized live verification after the evidence blocker is resolved:
python -B main.py identity-verify --db /PRIVATE/ROOT/state/ledger.db --session SESSION --live --apply
```

Set TIKTOK_RUNTIME_DIR to the same absolute private root before starting the
process; it contains sesion/SESSION.json, sesion/ws-auth/SESSION.json and state/.
Do not set it to a shared or symlinked directory. The root must already exist;
readiness does not prepare it. Preflight returns 2 for BLOCKED, 1 for UNVERIFIED.
It never declares live credentials or Debian compatibility verified. Metadata
mode checks only credential paths; --check-credentials additionally parses the
pair without printing values. Windows ACLs are not certified by chmod.

Identity preview returns 0 when local schema/circuit checks pass, but does not
establish server identity. --apply without --live is rejected. Live apply requires
a TTY, reason and exact BIND session UID challenge; no unattended initial binding.
Missing/older schema fails before credential/network access.

## Schema, relocation and rollback

V7 is unchanged. Existing ledger-preflight/initialize/migrate remain explicit
administration; none was run on real data. Immutable readiness is a quiescent
main-file inspection, not a replacement for Backup API or a live-WAL snapshot.
Stop writers and use the approved operational checkpoint/backup procedure before
readiness on a WAL-active ledger; never delete WAL/SHM to make the check pass.

Windows queue policy paths/old manifests are not rewritten. On relocation, use
existing explicit queue-bind and fresh worker approval. Roll back code/path
configuration while retaining all ledger, binding, marker and audit history.
Never restore a stale backup to erase UNKNOWN/quota. The stricter verifier must
not be bypassed to restore sending; identity evidence still requires review.

## Files and testing

Created: runtime_paths.py, readiness.py, identity_service.py,
core/self_identity.py, tests/test_runtime_paths.py, tests/test_readiness.py,
tests/test_identity_bootstrap.py, PHASE4A.md and TERMUX.md.
Modified: main.py, services.py, qrlogin.py, client.py, core/api.py,
circuit_breaker.py, ledger.py, oneshot.py, queue_service.py,
tests/test_circuit_breaker.py, tests/run_offline.py and README.md.
PHASE4A_PLAN.md is the earlier design/approval record.

Guarded offline suite: **310 tests, 309 PASS, 1 SKIP, 0 FAIL/ERROR**, 29.923 seconds.
Command: work/verify-venv/Scripts/python.exe -B tests/run_offline.py. CLI help
checks passed. Result is recorded in the C2C execution record and final report.
Coverage includes no credential reads in metadata mode, unchanged file
bytes/modes/mtime, no mkdir/chmod/sidecars, WAL refusal, old/missing schema,
auth-pair mismatch, OPEN/UNKNOWN, runtime fallback/containment, symlinks, default
CLI gates, stale generation, both circuit ABA scopes, competing bind processes,
audit insertion rollback and generic/guessed identity rejection. The previous
bare-odinId success expectation is deliberately changed to fail closed.

Actual POSIX permission test is skipped on Windows. No Debian/Android execution,
host readiness, real UID provenance, credential validity or live handshake has
been verified. TikTok APIs remain internal/unofficial; correlated echo is not
recipient delivery/read confirmation and streak credit remains unconfirmed.
No daily enqueue, recurring consent, scheduler, systemd or Phase 4B work.

STOP at REPORT for independent review.

Independent review confirmed 309 PASS / 1 POSIX SKIP and accepted the offline
infrastructure. Identity is not certified; the proposed next task is a separate
identity-contract PLAN, including origin/redirect, self-context, ambiguity,
negative fixtures and privacy-safe evidence acquisition. No live-read permission
was granted. This implementation stops at REPORT.
