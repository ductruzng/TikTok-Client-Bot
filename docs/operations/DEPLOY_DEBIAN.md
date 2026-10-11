> Documentation relocated during Phase5A. Commands assume the repository root. Debian 13 is the only current staging target; Identity Contract remains BLOCKED. Historical test counts below retain their original provenance.

# Debian staging and recovery — Owner operated

These are review artifacts, not an installer. Identity Contract remains BLOCKED.
No service/timer was installed or activated. Live TikTok/VPS verification belongs
to Owner after separate approval. Use unofficial internal API at your own account
policy risk; server echo does not establish recipient receipt or streak credit.

## Stage without activation

1. Choose a reviewed Debian version, architecture and immutable release directory
   `/opt/relttk/releases/RELEASE`. Create the unprivileged `relttk` account and
   private `/var/lib/relttk` runtime as separate, explicit Owner host actions.
2. Stage root-owned code, no group/world writes. Create a CLI-only venv using
   `python3 -m venv --copies PATH` because the runtime path checks reject symlinks,
   including the usual symlinked venv interpreter. Install requirements.txt only
   in the reviewed environment, record actual versions and run pip check. No
   Textual/Windows Playwright/browser is needed. A venv is not security isolation.
3. Runtime directories are relttk-owned 0700, files/DB/sidecars 0600; ancestors
   must pass ownership/write checks. Set explicit TIKTOK_RUNTIME_DIR before
   importing CLI modules. Stage config and session/auth privately by Owner.
   Never put cookies/tokens in command arguments, units, EnvironmentFile or logs.
4. Existing runtime DB must be V8. Perform explicit read-only preflight and an
   independently approved initialize/migrate procedure with backup; never migrate
   from ExecStart. Windows absolute policy references cannot be rewritten inside
   old immutable manifests. Review Linux routes and new explicit grants while
   retaining all old history/backlog.
5. After the separate identity contract is implemented/verified, review exact
   grant policy, budgets, circuit versions and UNKNOWN. AUTHORIZE and ACTIVATE
   are distinct Owner CLI actions, not renderer/install actions. This release
   does not overcome the current identity blocker.

## Render artifacts only

Use an already provisioned **fixture** environment for offline validation. The
real renderer requires POSIX and an explicit private runtime. Example selectors
are placeholders, not a grant discovery mechanism:

```text
TIKTOK_RUNTIME_DIR=/var/lib/relttk /opt/relttk/releases/RELEASE/venv/bin/python -B /opt/relttk/releases/RELEASE/deploy/render_units.py --db /var/lib/relttk/state/streak_ledger.db --grant-id EXACT_32_HEX --fingerprint EXACT_64_HEX --python /opt/relttk/releases/RELEASE/venv/bin/python --entry /opt/relttk/releases/RELEASE/operational_entry.py --runtime /var/lib/relttk --output /var/lib/relttk/unit-artifacts
```

Output directory must exist privately; files must be new. Renderer accepts one
recipient with daily_budget=1, window>=10 minutes and ten minutes before midnight,
or two recipients with daily_budget=2, window>=15 minutes and fifteen minutes
before midnight. Both require max_wait<=300. For two recipients, cooldown must
fit max_wait and max_sends_per_window must allow at least two. Unsupported grants
are refused, not shortened. See [H0–H5 report](HARDENING_H0_H5.md).
Paths must be absolute ASCII without whitespace/control, quotes, backslash,
percent, dollar or traversal. No shell or systemd specifier expansion is accepted.
Grant selector, policy, binding/circuit versions and expiry are checked read-only.
Rendering does not attest authenticated identity or host delivery.

Units use fixed real release paths, relttk user, private runtime, restricted
writable paths, Type=oneshot, Restart=no, startup600s (one) / 900s (two), stop90s. Timer checks every
minute in Asia/Ho_Chi_Minh with Persistent=false. It does not catch up old dates;
only existing current-window authority can enqueue/claim. A terminal manifest
is never replaced. Timer repetition is not UNKNOWN retry permission.

Owner separately reviews/copies artifacts and validates with the **installed**
systemd-analyze verify/calendar tooling. Copying units and daemon-reload must be
explicit host actions. No installation step enables or starts timers. Do not
activate this release while identity is BLOCKED. No automated install script,
preset, restart, renewal or credentials/bootstrap hook exists.

## Observe safely

Unit invokes `operational_entry.py`, which suppresses Python/native stdout/stderr
before CLI import and parsing. Journald receives a bounded allowlist envelope;
raw startup stderr is additionally discarded by StandardError=null. Missing
bootstrap/interpreter can yield no safe envelope: treat missing output as failure,
not healthy. No raw payloads, UID/session/conversation IDs or freeform errors.

```text
python -B operational_entry.py operational-status --db ABS_DB --grant-id EXACT_ID --operational-output
```

Health is quiescent-only, never live-WAL readiness. Nonempty WAL => UNKNOWN;
valid storage still reports identity BLOCKED. Aggregate status contains usage and
SUCCESS/UNKNOWN counts; grant usage counts manual/UNKNOWN markers too. It does
not assert that recipients received/read the message. Status cannot create,
migrate or repair DB/session files. Journal last-tick data is not live readiness.

Owner may inspect `systemctl status relttk-GRANT.service`,
`systemctl list-timers`, and `journalctl -u relttk-GRANT.service` on the approved
host. Inactive oneshot is normal after completion. NOT_DUE is normal; BUSY means
inspect contention. HELD/UNKNOWN/circuit/identity/schema refusals need review;
MISSED/expiry do not justify retrying an old occurrence. Check missing/stale
ticks against the configured window and backup age. No notification transport
or automatic reset/retry is configured.

SIGTERM sets existing stop event; a marker already committed receives bounded
echo handling before return. Forced kill/power loss keeps marker and recovers
UNKNOWN under the existing RunLock on the next authorized run; no quota refund,
rotation advance, UNKNOWN resend or grant recreation. Inbox HTTP and profile
enrichment now have a 45-second subprocess deadline plus bounded reap; WebSocket
open/close are bounded. Host process launch, filesystem/SQLite stalls and native
termination remain subject to the watchdog and need Linux fixture validation.
Identity currently refuses before HTTP, so this is not live-send certification.
If the workload/grace cannot be supported, refuse activation.

## Explicit backup; never automatically restore

```text
python -B operational_entry.py ledger-backup --db ABS_DB --destination NEW_ABS_BACKUP --operational-output
```

SQLite Backup API includes committed WAL, holds a separate source writer
reservation and existing RunLock, validates V8/integrity/FKs/table+marker counts,
fsyncs a new artifact, publishes exclusively and records a private SHA256 manifest.
No overwrite, request recovery, source migration or explicit checkpoint/sidecar
delete. Incomplete artifacts stay labelled `.incomplete` on failure.
**WAL backup requires sqlite3.Connection.setconfig and
SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE** (available in the tested Python3.13 build).
Python3.10 refuses WAL backup before mutable open; it supports DELETE-journal
fixture backup. Do not switch runtime journal mode to bypass this gate.
Core CLI requirements remain unchanged; select a capability-qualified interpreter
for operational backup and verify it on Debian. SHM read bookkeeping can change;
committed WAL/main history must not checkpoint or disappear on backup close.

Backup command is bounded and returns only safe metadata. It creates a lock
file if needed under the private state directory. It does not represent a complete
credential/config archive; Owner securely preserves those separately. No backup
timer, automatic retention/deletion or restore command is included.

Recovery is Owner-only: disable timer, drain/stop service, isolate all writers,
preserve source DB/WAL/journal/SHM evidence, validate backup in a **new** private
directory. Never restore stale markers over a newer runtime; if post-backup
activity is possible, keep the recovery copy non-operational and investigate.
Do not drop UNKNOWN, reset circuits, change consent or merge away audit events.
Old backup may forget actual transmissions and cause duplicates.

Code rollback keeps current V8 DB and selects a reviewed V8-compatible release
with the same safety gates; no schema downgrade or old DB swap. Review units
again. A pre-V8 release is incompatible. Rollback does not activate services.

## Validation gates before an eventual live host

Windows unit/clock/signal fixtures are simulations. Validate actual POSIX UID,
private mode/ancestors/symlinks, flock, native lz4, Python-linked SQLite/JSON/TZ,
backup WAL capability, systemd parsing/calendar, sandbox and external SIGTERM
in a separately authorized isolated, credential-free Linux environment.
Network guard must deny TikTok traffic. A nonbooted container is insufficient
for actual timer lifecycle evidence. No Linux environment was provisioned here.
Owner online checks account provenance/binding, controlled recipient delivery,
streak credit separately, privacy, stop, expiry and backup recovery before normal
use. Internal rate limits are not guaranteed bot-detection thresholds.

## Full guarded fixture dependencies

Core deployment dependencies remain in requirements.txt. For full offline test
coverage also install requirements/tui.txt into the disposable test environment;
Textual is optional for the core CLI but required for the actual TUI regression.
A core-only run with additional TUI skips is not equivalent to the full baseline.
The [Debian staging harness report](DEBIAN13_STAGING_FIX.md) describes descriptor
relative cleanup protection and native Linux checks that the Owner must rerun.
