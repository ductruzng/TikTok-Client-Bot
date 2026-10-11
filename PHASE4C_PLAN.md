# Phase 4C — Debian deployment, systemd and operational recovery

Task: `phase4c-plan`. Status: **AUDIT / DESIGN ONLY — awaiting Owner approval**.
Only this document is added. No source implementation, installation, activation,
SSH, Git, real session/database access or TikTok traffic is authorized here.
Phase 4B final review accepted 359 guarded tests: 358 PASS, 1 POSIX SKIP,
0 FAIL/ERROR, 41.927s. That is reused evidence, not a new test run.
Identity Contract remains **BLOCKED**. Offline deployment artifacts cannot certify
live identity, delivery, streak credit or Debian operation.

## 1. Audit and scope

Audited `main.py` scheduling commands, `scheduling.py`, `worker.py`, `oneshot.py`,
`ledger.py`, migration backup code, `runtime_paths.py`, `readiness.py`, `log.py`,
core HTTP timeout call sites, requirements and the guarded test runner.

Existing capabilities to reuse:

- V8 recurring consent, immutable daily occurrences and exact V7 Worker linkage;
  daily idempotency, FIFO and atomic transmission claims remain authoritative.
- Separate explicit AUTHORIZE and ACTIVATE, grant fingerprint, both circuit audit
  versions, binding/policy checks, marker-based budgets including manual/UNKNOWN.
- Worker releases RunLock/DB/WS before waiting; wakes through admission again.
  Terminal requests/manifests are not recreated or automatically retried.
- SIGINT/SIGTERM set the CLI stop event. Correlated echo handling has a default
  20-second monotonic bound including transmission; SUCCESS is server echo only.
- Explicit schema initialization/migration; sending opens an existing V8 database.
- POSIX owner/private-path checks; SQLite Backup API in migration implementation.

Gaps affecting deployment:

- Full CLI JSON can contain policy/message/recipient snapshots. `log.redact()`
  protects recognized secrets, but does not sanitize arbitrary JSON print sinks
  or hide recipient identifiers in lower-level oneshot logs. Raw CLI output must
  not become unattended journald output.
- Readiness and schedule read-only preview require a quiescent main file and
  refuse nonempty WAL/journal. They are not a concurrent live-WAL health API.
- Existing backup helper is migration-specific, not a public operational backup.
- No systemd templates or Debian install/recovery documentation exist. Windows
  tests do not establish POSIX ownership/flock or actual systemd behavior.
- Worker consent accepts larger waits than a reasonable fixed service timeout.
  Deployment must reject incompatible grants, not silently shorten consent.
- Existing HTTP timeouts are per operation. Whole-operation pre-marker latency
  and WS closure need Linux measurement; no unproven total shutdown guarantee.

No V9 schema, monitoring counter table, new transport, daemon or queue worker is
proposed. No dependency upgrade, identity parser or auth changes in this phase.

## 2. Architecture and explicit authority

Use one systemd oneshot service and timer **per explicit grant**, generated into
an output directory for review. No shell command construction, wildcard grant
discovery, default grant selection, automatic renewal or login/bootstrap hooks.

The service invokes the existing command through the reviewed absolute Python
and main.py paths:

```text
/opt/relttk/releases/RELEASE/venv/bin/python -B /opt/relttk/releases/RELEASE/main.py schedule-tick --db /var/lib/relttk/state/streak_ledger.db --grant-id EXACT_ID --grant-fingerprint EXACT_SHA256 --execute --yes --operational-output
```

`--operational-output` is a proposed opt-in presentation flag, not implemented.
It must call the same application service and preserve existing CLI exit codes.
Grant ID/fingerprint are authority selectors, not TikTok credentials; no session
token/cookie/auth URL appears in argv, unit files or EnvironmentFile.
The generator validates arguments/escaping and refuses missing paths, symlinks,
unsafe owners, unknown grant, fingerprint mismatch and timeout incompatibility.
Rendering uses fixture/offline consent only; it never authorizes or activates.

On the eventual Debian host, Windows absolute policy references cannot be copied
and rewritten inside immutable requests/manifests. Owner must review Linux policy
paths and create explicit new routing/consent through existing administration.
Existing history is preserved; blocked old requests need explicit Owner handling.

## 3. Proposed service and timer decisions

Service settings: `Type=oneshot`, `RemainAfterExit=no`, `Restart=no`,
`User=relttk`, `Group=relttk`, `UMask=0077`, `KillSignal=SIGTERM`,
`KillMode=control-group`, `StandardOutput=journal`, `StandardError=journal`.
No send-capable ExecStartPre/ExecStop/ExecStopPost or OnFailure action.
Network readiness ordering is advisory, never proof of TikTok reachability.

Proposed deployment profile: grant `max_wait <= 300` seconds,
`TimeoutStartSec=600`, `TimeoutStopSec=90`. Reject grants outside this profile
unless Owner explicitly approves matching unit bounds. These are operational
watchdogs, not promises every HTTP sequence finishes within them. Linux fake
transport tests must verify post-marker echo/close/commit fits stop grace;
if it cannot, approval must revisit bounds before activation. Forced kill/power
loss remains UNKNOWN recovery, never proof that transmission did not occur.
Use TimeoutStartSec for oneshot execution, not RuntimeMaxSec.

Timer recommendation: `OnCalendar=*-*-* *:*:00 Asia/Ho_Chi_Minh`,
`AccuracySec=1s`, `RandomizedDelaySec=0`, `Persistent=false`.
This checks every minute; the existing grant/window controls when sending is
eligible. No catch-up of missed prior dates, no replay of expired occurrences.
Starting after downtime may evaluate the current date only if still in its
approved window. Outside it, report MISSED; do not synthesize an old tick.
Timezone remains explicit even on a UTC host. Reject a window too narrow for
the check interval and tested startup allowance; do not claim exact-time delivery.

A timer does not launch another copy while the same service remains active.
Other instances/manual CLI still depend on shared RunLock, FIFO and SQLite
transaction gates. No extra flock wrapper held across Worker sleep.
Timer invocations may revisit the **same** occurrence/manifest; this is not retry
permission for FAILED/UNKNOWN/terminal runs. No automatic replacement.

Alternative daily OnCalendar was considered: fewer idle checks, but downtime
within the grant window is harder to recover without Persistent catch-up logic.
Minutely checks reuse existing bounded-window logic at a small local overhead.

## 4. Runtime and Linux readiness

Proposed directories (explicit Owner provisioning later):

- Root-owned immutable release and venv under `/opt/relttk/releases/RELEASE`.
  Pin the unit to a real absolute release path; no mutable `current` symlink.
- `/var/lib/relttk` and subdirectories owned by relttk, mode 0700. Config,
  session/auth, DB/sidecars and backup files mode 0600. Keep existing `sesion`
  layout; no silent compatibility-path change.
- `TIKTOK_RUNTIME_DIR=/var/lib/relttk`, `NO_COLOR=1`, unbuffered output, no debug
  transport tracing. Only runtime writes are allowed; code remains read-only.

Proposed sandbox: NoNewPrivileges, PrivateTmp, ProtectSystem=strict,
ProtectHome, PrivateDevices, empty CapabilityBoundingSet, RestrictSUIDSGID,
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6, explicit ReadWritePaths runtime.
Do not use DynamicUser with existing private files. Do not blindly enable
MemoryDenyWriteExecute or syscall filters without dependency validation.
No host sysctl/firewall/journald policy modifications by installer.

Use a fixed Debian stable image/version and target architecture chosen by Owner.
Check Python >=3.10, Python-linked SQLite version/JSON support, ZoneInfo,
websockets 15.x, lz4 4.x, qrcode 8.x and tzdata. `lz4` wheel/native fallback is an
architecture-specific verification item. Record tested versions and pip check;
no invented minimum SQLite version beyond actual schema-feature tests.
CLI deployment excludes optional Textual/Windows Playwright/Chromium. A venv is
dependency organization, not a security isolation boundary.

Install documentation stages files only: no enable/start/restart/preset,
authorization, migration or credential download hooks. Creating the service
user/directories, copying reviewed units and daemon-reload are separate explicit
Owner host actions, not operations performed by this task or a render command.

## 5. Journald and health contract

Add a small allowlist serializer shared by operational CLI output and health.
Emit state, fixed reason code, local date, timestamps, aggregate marker/SUCCESS/
UNKNOWN counts, usage/limit and retry_at where known. Exclude content, templates,
raw grant consent, UID/conversation/session IDs, auth URLs, payloads, headers,
freeform audit reasons, paths and raw exceptions. Unknown reason codes collapse
to a safe fixed code. No arbitrary nested dictionary passthrough.

Operational CLI must suppress lower-level stdout/stderr safely for its whole
invocation, including exceptions and startup failures, then emit bounded safe
metadata. Do not capture unbounded logs in memory or rely solely on regex.
Keep human interactive previews unchanged. Catch startup failures before any
sensitive print in the operational entry path; tests inject secret sentinels.

No new health state database. `operational-status` (proposed CLI) reads only a
quiescent V8 database through existing readonly APIs, no credentials/network,
reports grant state/last durable occurrence/aggregate usage and explicit identity
BLOCKED. Nonquiescent WAL => UNKNOWN/BLOCKED with an actionable maintenance
instruction, never ignore WAL or label healthy. No new live DB reader in 4C.
During a running service use safe last-tick metadata/journald plus unit state;
label freshness/staleness, not real-time readiness or recipient delivery.

Exit codes remain 0 for existing normal states, 2 for held/review/worker outcomes,
3 for refusals. A systemd inactive oneshot is normal, not proof of failure.
NOT_DUE is normal; BUSY is contention to inspect; UNKNOWN/circuit/identity/schema
blocks require Owner review; MISSED/expiry need explicit future consent rather
than retry. No blanket SuccessExitStatus=2 masking all holds.
Document journalctl/systemctl queries, stale-tick/window and backup-age checks.
No email/webhook/alert transport or automatic remediation in 4C.

## 6. Backup and recovery design

Propose `ledger-backup --db ABS --destination NEW_ABS` administration command.
Explicit invocation; no backup timer in this phase. Validate private existing
source and destination parent; reject symlinks, overwrite, source alias and
sidecar destination aliases. No source creation/migration/chmod.

Use SQLite Backup API into an O_EXCL 0600 new staging file, not a plain copy of
the main file while WAL may contain committed history. Hold BEGIN IMMEDIATE on
a separate existing source writer connection while a separate reader backs up
committed state (reuse the proven migration pattern). Acquire existing RunLock
for coordination, without running recover_pending or touching requests.
All connections/locks close on completion/error. Bounded busy/progress deadline;
on timeout fail, never publish a partial backup as usable.
Validate V8 schema, integrity_check, foreign_key_check, history counts and marker
count, close/fsync destination, publish to a new collision-safe name and fsync
directory on POSIX. Emit only safe completion metadata. Private manifest records
SHA256, schema, snapshot time/counts and code/dependency versions, never auth.
Failed artifact remains explicitly incomplete for Owner inspection; never
overwrite an earlier backup. WAL sidecars are not copied/truncated/deleted.
Backup is point-in-time evidence, not a guarantee there were no later sends.

Recovery is a documented **Owner-only procedure**, no runtime restore command:
disable timer, stop/drain service, isolate all writers; preserve original DB and
all WAL/journal/SHM evidence without deleting anything. Validate backup into a
new private recovery directory and compare all markers/history against the
newest trustworthy source. Never merge by dropping rows or refunding quota.
If any post-backup activity is possible or chronology is uncertain, recovery
copy stays non-operational; do not restore old grants and resume sending.
Missing newer markers could cause duplicates and cannot be reconstructed safely.
No automatic UNKNOWN resolution or circuit reset. Fresh backup of current
evidence before any separately approved recovery action.

Code rollback: stop timer/service, keep current DB, select a reviewed release
that supports V8 and all same safety gates, verify offline, review units again.
No schema downgrade, no restoring stale DB to make old code run. A pre-V8 release
is incompatible. Install rollback never starts services by default.

## 7. File scope after approval

| File | Planned change |
| --- | --- |
| `main.py` | opt-in operational output; operational-status and explicit backup CLI |
| `operations.py` (new) | small allowlist output/status and bounded backup functions; stdlib only |
| `services.py` | wrappers for common operational services, no send bypass |
| `deploy/render_units.py` (new) | offline rendering/validation of fixed per-grant units; no host commands |
| `deploy/systemd/relttk.service.in`, `relttk.timer.in` (new) | nonactivated templates, real release paths |
| `tests/test_operations.py`, `tests/test_deployment.py` (new) | fixture privacy/backup/unit/signal tests |
| `tests/run_offline.py` | only if extra fixture child guarding is necessary |
| `DEPLOY_DEBIAN.md`, `PHASE4C.md` (new), `README.md` | staged install, recovery, evidence and gates |

Do not change V8 schema, migrations, rotation, rate counters, recurring admission,
identity verification, auth or transport. If implementation shows signal/timeout
requirements need Worker/oneshot changes, report evidence and seek scoped approval
before changing those safety-critical semantics.

## 8. Offline acceptance matrix

| Area | Required evidence |
| --- | --- |
| Unit rendering | exact paths/args/grant; escaping/injection tests; missing/unsafe paths refused; no auto-install/activation/authority |
| Timer | HCM calendar/UTC host, midnight, current window, downtime, MISSED/expiry; no prior-date catch-up |
| Grant races | simultaneous fixture ticks/manual send; original parent/FIFO/marker budgets/ABA gates unchanged |
| Shutdown | fake WS SIGTERM before marker and after marker; echo commit or UNKNOWN, no retransmission; timeout/kill restart preserves history |
| Privacy | nested secret/message/URL/ID sentinels through stdout/stderr/errors; bounded output; no raw startup traceback |
| Health | absent/wrong schema, nonempty WAL, active/stale/held grant; no DB/session mutation or misleading healthy result |
| Backup | committed WAL included, rollback state excluded, writer race, timeout/full disk/failure, destination collision/symlink; validation and restore to new fixture preserve all history |
| Rollback | no overwritten source; newer markers never discarded; V7 code refused for V8; no grants autoactivated |
| Linux | actual UID/mode/ancestor/symlink checks, flock multiprocess, signals/native lz4, installed systemd template validation |
| Regression | full guarded suite; expected baseline 358 PASS + 1 POSIX SKIP on Windows; report actual new totals separately |

Windows: AST, template/CLI fixtures, fake transport, SQLite/WAL/concurrency tests.
These are simulations, not systemd tests. Disposable Debian validation must be
separately authorized: credential-free isolated VM/container with no TikTok
network, fixture runtime only. Plain containers can run dependency/POSIX tests
and systemd-analyze verify; booted systemd VM/container is needed for real timer,
sandbox and signal behavior. No Docker/WSL/VM provisioning or downloads in PLAN.
On Debian run full guard suite and report any remaining skips honestly. Document
installed systemd version; upstream main docs are not proof of target support.

## 9. Owner decisions and operational gates

Request approval for: (A) minutely nonpersistent per-grant timer,
(B) 300s max_wait deployment profile / 600s start / 90s stop with measured grace,
(C) safe operational output and quiescent-only status,
(D) explicit backup with no automated restore/backup scheduler,
(E) file scope, no V9 and no transport/identity changes,
(F) disposable Linux test strategy and evidence distinction.

Activation checklist for Owner, **later and separately authorized**:

1. Select Debian/architecture and reviewed release; validate dependencies,
   permissions, systemd directives and fixture suite on that Linux environment.
2. Resolve authenticated-self contract and verify actual account/IM namespace
   through the separate identity workstream. Current BLOCKED status forbids
   operational certification; do not substitute cached UID or guessed HTML.
3. Stage runtime/session privately by Owner; explicit DB preflight, backup and
   separately approved initialization/migration. Never migrate at timer start.
4. Review Linux routing/config, request backlog, UNKNOWN and circuits; explicit
   per-grant preview/AUTHORIZE/ACTIVATE. Unit render/install cannot do these.
5. Owner reviews exact unit selector/paths/bounds and starts timer only with
   explicit online approval. No live test is part of Codex 4C tests.
6. Owner verifies one controlled delivery, journald privacy, graceful stop,
   backup and expiry behavior; stops on UNKNOWN without automatic retry.

API is unofficial internal TikTok API. Correlated server echo is not proof of
recipient receipt/read or streak credit. Limits are internal policy, not TikTok
guaranteed anti-detection thresholds. Legacy media is outside the managed text
Safety Layer; this phase does not certify all Core functionality.

## 10. References and current execution evidence

- [Upstream systemd timer documentation source](https://github.com/systemd/systemd/blob/main/man/systemd.timer.xml): timer does not restart an already active target; calendar/persistence semantics.
- [Upstream systemd service documentation source](https://github.com/systemd/systemd/blob/main/man/systemd.service.xml): oneshot timeout and restart semantics.
- [SQLite Backup API](https://www.sqlite.org/backup.html): use consistent SQLite snapshots instead of copying an active main file.

Audited locally; official systemd rendered manual endpoints returned 403, so
upstream documentation source was consulted. Target Debian man pages and
systemd-analyze remain acceptance requirements. No tests rerun for this PLAN,
no Linux/systemd validation performed. Only PHASE4C_PLAN.md created.
**STOP at PLAN — awaiting Technical Owner review.**
