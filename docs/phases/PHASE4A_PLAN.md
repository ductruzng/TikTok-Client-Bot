> Historical record: original phase decisions and test counts are retained. They do not certify the current release. Debian 13 is the sole current staging target; Identity Contract remains BLOCKED. Run repository command examples from the repository root. See [current operations](../operations/DEPLOY_DEBIAN.md) and [current security baseline](../evidence/EVIDENCE_PHASE4_SECURITY.md).

# Phase 4A — Production Readiness (AUDIT / PLAN ONLY)

Task: phase4a-plan. Source audit completed 2026-10-11. Implementation NOT started.
Phase 3E accepted baseline: 281 guarded offline tests PASS. This audit reused
that evidence, not a new regression run. No source changes, SSH, real credentials,
runtime database, live TikTok, Git or host changes were performed.

## Findings from the existing clone

- `queue_service.binding()` refuses unbound sessions. `oneshot.py` checks V7
  before credential access and compares a fresh `get_own_user_id(use_cache=False)`
  response against the stored binding before sending. This fail-closed behavior
  must stay. `circuit_breaker.bind_session()` persists identity and its audit,
  but only tests currently call it: there is no production verification CLI.
- `core/api.py` extracts the first numeric odinId from the messages HTML. Fresh
  mode avoids UID-cache reads/writes, but the parser does not demonstrate the
  complete authenticated response shape or reject conflicting identity fields.
  This is brittle protocol evidence, not an official identity API. Do not accept
  config/cookie UID, a cached value or a manually typed UID as verification.
- `qrlogin.py` credentials and `services.py` session enumeration independently
  point at repo/sesion. `ledger.py` defaults to repo/state and `main.py` defaults
  its policy relative to the current working directory. Multiple implicit roots
  are unsuitable for a read-only code installation and predictable startup.
- `load_session()` creates/tightens directories on read; `load_ws_auth()` chmods
  existing paths. These loaders cannot be used for a strictly read-only readiness
  report. Credential permissions and storage must be checked without repairing
  them silently during a preflight.
- Managed sends load only session-bound WS auth and verify the sessionid hash;
  they do not fall back to the global auth file. Capture is Windows-only, probes
  in memory before saving, and does not currently retain a device_id. `config.py`
  still contains an upstream default key; production must never use that fallback.
- Queue entries store an absolute policy path and its fingerprint. Windows paths
  will not work on Debian. Explicit queue-bind and new worker consent are needed
  after relocation; never rewrite existing routes/consents automatically.
- RunLock already selects msvcrt on Windows / flock on POSIX. SQLite V7 needs
  JSON support, WAL and local durable storage. Full Linux permissions, locking,
  signals and native lz4 installation have not been tested on the target host.
- Local evidence only: Python 3.10.11, SQLite 3.40.1 with JSON; installed websockets
  15.0.1 and lz4 4.4.5 require Python >=3.9; code's union types require >=3.10.
  qrcode 8.2 and tzdata 2026.5 are installed. The Debian/Python/architecture of
  SSH alias surface remain unknown. No target compatibility is claimed.
- README/capture errors reference TERMUX.md, which is absent in this clone.
  No packaging manifest, Debian deployment files or dependency lock were found.
  This plan does not repair unrelated encoding/UI or legacy helper issues.

## Proposed decisions A–F for approval

### A. Keep V7 and the accepted worker

No schema V8, counters, alternate queue or transport. Reuse existing binding,
breaker events, explicit migration, queue bind and worker consent. Bootstrap is
administration, never an enqueue or send operation. Existing OPEN/UNKNOWN and
account/session versions must not be reset or cleared by verification.

### B. Explicit identity bootstrap, with bounded protocol evidence

Add an application service and `identity-verify` CLI. Default shows only local
readiness; `--live` expressly opts into a bounded authenticated read, and `--apply`
requires interactive preview/reason/confirmation before writing the binding.
No non-interactive initial binding in 4A. No UID override argument.

Order: local path/V7 gate → read private session → uncached TLS identity request
→ validate exactly one distinct positive numeric identity and response provenance
→ preview UID/session/evidence method → confirmation → reacquire RunLock and
transaction, recheck binding/circuit versions and credential generation → bind.
Do not hold a SQLite transaction or RunLock while waiting for network or Owner.
Check failure must leave the binding unchanged; relevant authenticated failures
may append the existing classified circuit audit under the explicit live mode.
Same UID is idempotent; different UID under the same alias is rejected and requires
a distinct session. Concurrent change/stale confirmation fails, without resetting
breakers or invalidating old history by overwriting it.

Minimal proposed bind_session API extension: optional expected account/session
versions plus sanitized verification method in its existing transaction/audit.
Credential generation is compared in memory and never printed. An old V7 binding
is not silently upgraded or treated as a cookie-generation guarantee.

Important tradeoff: uncached odinId HTML is the existing verification level, not
proof of receiver identity or an official authenticated-user endpoint. Tighten
ambiguity/redirect rejection with synthetic fixtures; if no unambiguous evidence
is available, fail closed. Do not invent a new self-profile endpoint or bypass
TLS. Genuine response-shape verification is a separate, explicitly approved
live-read step before operational deployment, not part of offline implementation.

### C. One minimal path resolver, explicit production roots

Add a small stdlib `runtime_paths.py` shared by managed CLI, services, qrlogin and
WS-auth lookup. Proposed opt-in environment `TIKTOK_RUNTIME_DIR`: absolute path,
with sesion/, sesion/ws-auth/, state/ beneath it. Preserve existing Windows
repo defaults when unset; production readiness requires an explicit root plus
explicit absolute --db and policy path. No silent search, copy or fallback to
another credential directory. Validate aliases and containment, reject symlinks
in each existing path component, reject shared/unowned POSIX credential roots.
Do not broaden the current session-name allowlist.

Proposed eventual Debian layout (not created now): code /opt/tiktok-streak,
private runtime /var/lib/tiktok-streak, policy in that private root, unprivileged
service user. Paths are illustrative until the actual host is inspected.
No global relocation of unrelated legacy caches in this scope; disable their use
on managed readiness/bootstrap paths. venv is dependency isolation, not security.

### D. Read-only readiness and separate preparation

`runtime-preflight --runtime-dir ABS --db ABS --config ABS` uses only explicit
paths and reports structured safe codes, PASS/BLOCKED/UNVERIFIED by category.
Check Python/imported core dependency versions, SQLite JSON/backup capability,
V7 integrity/schema via existing read-only routines, timezone, canonical path
containment, ownership/modes and sidecar parent safety, policy validation, stored
identity/circuit/UNKNOWN state and availability of session-bound auth paths.
Default inspects metadata only, not credential bodies, and does not imply token
validity. Optional explicit `--check-credentials` parses privately and validates
session/auth pairing, with no network and no values/hashes in output. This mode
does not repair permissions or create files either.

Readiness does not prove credentials are current, handshake works, target inbox
matches or TikTok counts streaks. Separate --live operations are never called by
preflight. Missing/old DB is BLOCKED; no initialize/migration/RunLock acquisition
with file creation. Existing send schema guard stays before credentials/network.
Permission repair or runtime preparation must be an explicit administration
action; recommend documented setup rather than adding another initializer in 4A.

### E. Debian compatibility and host preflight are separate gates

Target Python >=3.10, using the Debian-provided supported version only after host
inspection. Core install stays requirements.txt; Windows browser extraction and
Playwright capture are not installed on the Debian worker. Auth transfer/setup
needs separate permission and must preserve the exact session/auth pair privately.
No browser is required by the worker, but browser-issued auth expiry remains an
operational blocker. Do not promise autonomous renewal or guess device/routing.

Prepare a read-only host checklist (OS/Python/SQLite JSON, arch, CA/TZ, local disk,
flock, writable private roots, dependency wheels/build requirements, clock and
systemd presence). Do not execute ssh surface in this phase. Linux CI or a
disposable Linux test environment needs explicit availability; mocked POSIX tests
alone cannot certify Linux operation. No Docker/systemd/scheduler installation.

### F. Preserve authority and rollback boundaries

4B may call accepted enqueue/worker services only after separately designed daily
idempotency and recurring consent. 4C may invoke the same CLI with explicit paths;
no service/timer or recurring authority is implemented in 4A.

No new migration is planned. V6→V7 remains Owner-driven existing preflight +
Backup API + explicit migration. Relocated queued routes require interactive
queue-bind and new manifests. Old manifests/routes remain history; no rewriting.
Rollback of path configuration means restore the prior environment/installation
and keep the SAME ledger/history. Never restore an old DB to erase markers,
UNKNOWN, quota or binding/circuit audits. Never revert to a legacy bypass send.
Bootstrap records are append-only: an erroneous identity is quarantined under
the old alias; correction uses a new verified session, not DELETE/UPDATE history.

## Proposed file scope (not yet changed)

Create runtime_paths.py, readiness.py, identity_service.py,
tests/test_runtime_paths.py, tests/test_readiness.py, tests/test_identity_bootstrap.py,
PHASE4A.md. Modify main.py/services.py for CLI/shared service; qrlogin.py/client.py
for common path resolution and non-mutating inspection; core/api.py for bounded
fresh identity evidence; circuit_breaker.py for atomic stale-version checks;
tests/run_offline.py for explicit fixture-only runtime-root protection; README.md
for approved usage. Restore or replace missing TERMUX.md references minimally.
Ledger schema/worker behavior are unchanged. If ledger.py needs a helper for
read-only validation, reuse its current functions before adding another opener.

## Offline test matrix after approval

- Paths: Windows default compatibility, explicit root from another CWD, absolute
  paths, traversal/symlink ancestors, wrong root/ownership/modes, missing roots;
  no mkdir/chmod/read-credential side effects in metadata preflight.
- Readiness: missing DB/old schema/malformed V7/JSON absent/invalid policy,
  verified binding absent, OPEN/UNKNOWN, auth missing/mismatched, no writes or
  networking in default/credential inspection. Safe diagnostics and exit codes.
- Bootstrap: fresh UID success, missing/ambiguous/invalid identity, redirects,
  HTTP auth/rate errors, cache forbidden, missing creds or V7 rejects before
  transport; no DM/WS; preview/read-only default and explicit interactive apply.
- Transaction: same UID idempotency, conflicting UID rejected, concurrent bind,
  circuit OPEN→RESET during preview, credential generation changed during prompt,
  append failure rollback, stale versions, no automatic breaker/UNKNOWN reset.
- Existing 281 offline regressions including FIFO/idempotency/rotation/worker
  manifest marker budgets; managed packets still use snapshots and shared claim.
- POSIX permissions/lock/signal behavior on disposable Linux when available;
  Windows fixture coverage remains distinct from real Debian verification.

## Review gate

Please approve or adjust A–F, especially HTML identity evidence limits, explicit
live-read/apply consent, environment-based runtime root and strict preflight modes.
STOP at PLAN. No implementation is authorized by this document.

## Technical Owner response received

ChatGPT reviewed iteration 1 and approved A–F for a separate
phase4a-implementation task, with mandatory conditions:

1. A lone odinId is insufficient: prove authenticated-self context and share
   the strict verifier between bootstrap and managed sends; ambiguous evidence
   fails closed. Live evidence verification remains separately unapproved.
2. Preflight must not create WAL/SHM, mkdir, chmod, write credentials or migrate;
   test all these side effects explicitly, including SQLite read-only WAL behavior.
3. Explicit runtime roots prohibit silent legacy auth/session fallback and require
   ancestor symlink/ownership checks plus DB/config path consistency.

This turn stops at the plan/report boundary; no implementation has started.
