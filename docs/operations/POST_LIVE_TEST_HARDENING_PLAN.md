# Post-live-test hardening: source review and implementation plan

Historical audit/approval plan. Owner authorized remaining H implementation
directly on 2026-10-11; see [current batch report](HARDENING_H0_H5.md) for actual
changes, tests and unresolved production/native acceptance gates. Original
read-only scope and per-phase stops below describe the earlier audit.

Task: `post-live-test-hardening-review`.
Scope: REVIEW_AND_PLAN_ONLY. Implementation is NOT authorized.
Status: REVIEW REPORT; stop for Owner approval.

## Scope and provenance

The requested product outcome is a Windows/Debian 13 setup and TUI workflow
for selecting two recipients, preserving multiline message text, configuring
a bounded recurring schedule, explicitly authorizing it, and managing its
status without copying JSON or grant IDs. Termux is retired.

Verified locally: checkout HEAD is
`6b3ee1b90cd02b49ca0cbd5fad8454738572b71f`; working tree was clean before this
report. The commit changes six files: `core/api.py`, `core/self_identity.py`,
`main.py`, `relttk/transport/ws_auth_capture.py` and two new identity tests.
Git inspection was read-only. No fetch, checkout, commit, push or merge occurred.

Owner's reported Debian login, identity pilot, WS capture/probe, two actual
transmission attempts and recurring authorization/tick are external pilot
evidence. They were not independently reproduced here. No real session,
credential, browser capture or runtime database was opened. Two attempts do
not establish recipient receipt, streak credit, production identity assurance
or seven-day unattended operation. SUCCESS remains correlated server echo.

Only this report is added. Application, tests, dependencies and templates are
unchanged; offline outputs live under ignored `work/post-live-review-evidence/`.

## Evidence-based findings

### R1 — Identity verification changed substantially; production assurance unresolved

`core/self_identity.py:14` previously refused every verified-self request.
It now delegates to `extract_self_uid_candidate`, accepting a single
rehydration script with matching `odinId` and `user.uid`, a nonempty `secUid`
and a positive decimal UID. This is stricter than generic HTML search but
does not itself establish authenticated provenance. The module docstring
still says provenance is absent. The synthetic parser tests prove parsing
rules, not that the schema represents the authenticated account in all
responses. A guarded probe accepts a synthetic context with no explicit
authenticated-session signal; this is a coverage gap, not a proven TikTok
account spoofing exploit.

`core/api.py:49` compares full-cookie and sessionid-only responses. Matching
two responses from the same endpoint is a consistency check, not an
independent identity authority. The request code does not explicitly validate
HTTP final origin, redirects, content type, response size or login/challenge
state. These omissions need protocol review and controlled synthetic tests.

The current fresh path refuses mismatched responses and avoids UID cache;
managed transport uses it at `relttk/transport/oneshot.py:474` and compares
against the ledger binding. Binding still checks generation and circuit
versions. Do not replace these protections with user-entered UID or cached
HTML. README, readiness, scheduling and operational status retain unconditional
`IDENTITY_CONTRACT_BLOCKED` labels, but those labels alone do not enforce the
former refusal. Reported BLOCKED and executable parser behavior disagree.

Additional guarded probes: missing session input performs one mocked HTTP
call before `AUTHENTICATED_SESSION_REQUIRED`; a non-ASCII decimal UID is
accepted. Move session validation before transport and propose ASCII canonical
UID validation. Neither probe used actual network or credentials.

Recommendation: keep parsing candidates separate from authenticated verification.
Require Owner review of credential-free contract evidence, authenticated vs
guest/challenge/conflicting cases and the caller boundary before approving a
production identity contract. Until that is accepted, propose restoring an
enforced verification refusal, rather than relying on a status label. This
would intentionally block the pilot path and requires explicit approval;
no such change has been applied during this audit.

### R2 — Linux capture enabled by removing platform gates only

The commit removes Windows refusal in `main.py` and both capture functions.
It retains capture in an ephemeral Chromium context, candidate filtering,
in-memory handshake probe and session/hash-bound private writes. It does not
add Debian dependency declarations or preflight. `requirements/auth-windows.txt`
still excludes Linux Playwright, and help/docs remain Windows-oriented.
Browser launch and context creation occur before the current cleanup try/finally;
partial setup failures require cleanup tests. CDP qualification counts frames;
it is not proof of message acceptance or identity provenance.

Recommendation: a separately installed optional cross-platform browser-auth
dependency group, explicit browser/setup diagnostics, bounded launch/capture,
private in-memory handling and cleanup on every stage. No browser installation,
auth refresh, capture or probe may happen implicitly during send/timer execution.
Retain `requirements/auth-windows.txt` as a compatibility include if reorganized.
Do not add cookie extraction to the Debian dependency group. Rootless Debian
Chromium/sandbox prerequisites must be validated; do not default to --no-sandbox.

### R3 — Multi-recipient runtime exists; reviewed deployment profile excludes it

`relttk/runtime/scheduling.py` already creates daily occurrences and finite
worker manifests for multiple targets. Daily idempotency, immutable consent,
versioned actions and marker-derived budgets exist. `worker.run` waits only
for temporal rate holds, releases RunLock/DB/WS while waiting and rechecks
admission. No new worker or scheduler is needed.

`deploy/render_units.py:28` deliberately requires one target/daily budget one.
Its comment states pre-marker setup lacks an established global bound.
Templates use 600-second startup and 90-second stop limits, minute ticks,
Restart=no and Persistent=false. Merely accepting target count two would
remove a reviewed safety restriction without establishing runtime bounds.

Recommendation: first bound identity/inbox/setup operations end-to-end and
verify the existing finite worker completes two synthetic recipients with
the configured 60-second cooldown. Size a conservative reviewed two-target
profile against max_wait, echo/stop bounds and current-day window. Narrow
windows, exhausted quota and circuit/UNKNOWN holds must report refusal.
The 60-second interval and other thresholds are internal policy, not TikTok
anti-detection guarantees. Keep max concurrency one, no resend of terminal
requests, no catch-up after expiry, and no automatic circuit reset.

### R4 — TUI is a retained configuration/preview client, not schedule management

`relttk/application/tui.py:293` renders a disabled scheduler switch.
`_run_send` explicitly refuses the legacy Scheduler path; manual confirmation
callback returns false, holding a preview and directing users to CLI. Do not
enable that legacy path. The shared services already expose schedule preview,
authorize, status, activate/pause/revoke, worker and queue operations.

The message widget is single-line Input; TUI and `services.save_plan` strip
text, so boundary whitespace is not preserved. `_save_all` writes the plan
before validating time in save_preferences, allowing partial persistence
after invalid time. Time validation exists in services/scheduling but no
inline pre-save validation exists in TUI.

Inbox loading is manual, runs in a thread, prevents concurrent fetches and
rejects results if the account changed. Success rebuilds selection from the
saved plan, losing unsaved edits; account change clears current selection.
No outer request deadline is present. UI wait cancellation alone cannot stop
the underlying blocking thread. Core profile enrichment loops can multiply
per-call timeouts. Preserve per-account draft selection with generation checks
and bounded service calls, not merely asyncio.wait_for around to_thread.

Account dropdown defects were reported by Owner but not visually reproduced.
CSS has a fixed-height time row and generic Select styles; choose layout fixes
from Textual pilot/screenshot evidence at multiple terminal sizes, not guessing.
QR TUI launcher only opens a terminal on Windows; Debian TUI login also needs
a deliberate user-operated flow if setup is to stay within the interface.

### R5 — Authorization encoding failure root cause remains unknown

Schedule CLI uses ASCII JSON and exact fingerprint/version challenges.
`input()` for the reason can raise UnicodeDecodeError; output in other menu/TUI
flows can raise UnicodeEncodeError. UnicodeDecodeError is a ValueError and
UnicodeEncodeError is also a ValueError, so schedule's broad handler masks
the distinction as a generic blocked operation. No credential-free traceback,
locale or stream encoding from the failure was available in this task.

Do not decode input with errors=ignore/replace for authorization or change the
required challenge to bypass failure. Reproduce stdin/stdout encoding failure
with synthetic streams; failed decoding must leave no grant/action event.
Expose a sanitized encoding-specific diagnostic. Allow explicitly configured
UTF-8 terminal setup; use ASCII escape fallback only for presentation, never
silently alter exact message text, reason or confirmation. Preserve non-TTY
refusal, EOF/cancel handling and stale-preview checks.

### R6 — Existing protection coverage is valuable but not product acceptance

The current full guarded Windows Python 3.10.11 suite ran 475 tests in
70.437 seconds: 471 PASS, 4 SKIP, 0 FAIL/ERROR. The delta from the prior
465-test baseline is ten added identity tests. AST parsing passes for all
112 application/test/tool Python files on Python 3.10 and 3.13.
No source hashes changed during the audit. These results do not certify native
Debian, browser compatibility, TUI layout or authenticated-self provenance.
No native Linux environment was used. Tests currently preserve synthetic
identity success and generic-HTML refusal; restoring a contract block would
need an explicitly reviewed adjustment to that expectation.

## Proposed architecture and design choices

Keep SQLite V8 as the single source of request/grant/event truth. No schema
change is proposed unless later implementation proves a specific missing
invariant; request separate approval if it does. Reuse scheduling and worker
services for all CLI/TUI actions. Add small typed UI-facing projections and
validation helpers only where existing services expose too much raw data.
No FastAPI, web UI, new framework, independent counters or background TUI timer.

Separate local draft configuration from immutable authorized grants. Saving
a draft never authorizes or activates it. Editing an active policy can invalidate
existing consent; show affected grants and require explicit pause/revoke plus
new preview/authorization for changed content or recipients. Do not mutate old
grants or rewrite absolute runtime references when moving between machines.
Debian grants must be created against Debian runtime paths.

TUI confirmation dialogs display account, exact recipients/content, validity
dates, time zone, window, budgets and limits. Bind actions to fresh fingerprint
and event version; reason and a separate confirmation are required. A generic
Send/OK switch cannot grant future authority. Show grant IDs for diagnostics
but select them internally. A stale dialog must fail and request fresh review.

Automatic inbox sync should occur only after a deliberate user choice to use
the saved account in an online inbox screen. An optional remembered preference
may follow Owner approval. TUI startup and local previews must remain usable
offline and must not launch auth/bootstrap/probes. Refresh errors preserve
drafts; an account-generation token prevents A -> B -> A stale results.

TUI controls grant state, not unattended process lifetime. Closing it must not
implicitly authorize, revoke or install a service. On Debian a reviewed timer
can invoke the existing bounded operational entry. Artifact render is distinct
from Owner-operated service installation/activation. Future guided setup can
reduce commands, but must preview destinations, host changes and authority;
this plan does not authorize a privileged automatic installer.

Windows is the setup/manual UI platform for this proposal. Persistent unattended
Windows scheduling is not implicitly promised: Task Scheduler or another host
integration would require its own plan. Debian is the unattended staging target.

## Ordered phases, file scope and acceptance gates

All phases below are recommendations requiring Owner approval, not execution.

| Phase | Proposed files | Acceptance before the next phase |
| --- | --- | --- |
| H0: Identity/encoding baseline | `core/api.py`, `core/self_identity.py`, `relttk/identity/identity_service.py`, `relttk/identity/readiness.py`, `relttk/operations.py`, `main.py`; identity tests; new `tests/test_terminal_encoding.py`; optional small `relttk/application/terminal.py` | Identity authority decision explicit; no label-only gate, no cache fallback; missing auth stops before transport; cookie conflict/redirect/challenge rejection; decoding/confirmation errors produce zero writes; fresh full regression PASS |
| H1: Explicit cross-platform browser setup | `relttk/transport/ws_auth_capture.py`, `main.py`, optional `requirements/auth-browser.txt`, compatibility `requirements/auth-windows.txt`; new capture/preflight tests | Missing browser/dependencies diagnosed without reading secrets or connecting; mock Linux/Windows lifecycle tests; no implicit bootstrap, credentials never logged; capture pair/hash and write-after-probe rules retained |
| H2: Two-target bounded deployment | `core/api.py` and transport setup paths only where bounds required; `relttk/runtime/scheduling.py`, `relttk/runtime/worker.py` only if evidence shows missing bounds; `deploy/render_units.py`, systemd templates; scheduling/worker/deployment tests | Two mock recipients respect cooldown and budgets; sleep releases resources; pause/revoke/ABA/UNKNOWN/crash retain gates; renderer proves narrow profile bounds and refuses unsupported work; no actual unit installation |
| H3: TUI drafts, account/inbox and text | `relttk/application/tui.py`, `relttk/application/services.py`, corresponding CLI draft helpers where shared; new Textual UI tests, `tests/test_tui_services.py` | Exact multiline text roundtrips; invalid HH:MM changes no file; validation before save; per-account selection survives failure; stale refresh rejected; no auth/send at mount; layout verified at agreed sizes |
| H4: TUI grant lifecycle and status | same TUI/services; small `relttk/application/schedule_ui.py` only if needed to keep widgets manageable; tests for dialogs/actions/status | Save != authorize != activate; dedicated fresh challenges; no JSON/grant-ID copying; pause/revoke authoritative; per-recipient queued/UNKNOWN/server-echo/usage/retry reason displayed; no timer bypass |
| H5: Operations/docs and staged acceptance | `README.md`, `docs/operations/DEPLOY_DEBIAN.md`, new Windows/Debian usage/troubleshooting guides if README becomes too large; operational status tests only where projections change | Fresh-machine instructions align with actual optional dependencies and CLI; backup/explicit migration/recovery described; Windows + native Debian offline acceptance; live/7-day trial remains a separately approved Owner action |

H0 precedes any new automation authorization. H1 and H3 can be reviewed
independently after H0. H2 must complete before advertising two-recipient
unattended deployment; H4 uses the accepted service/authority contract. Stop
after each approved phase, report test results and review before proceeding.

Prefer existing modules over new ones; proposed new helper files above are
optional, bounded choices, not a reason for broad refactoring. No relocation
of package/compatibility modules, removal of legacy functions, or schema
redesign is included. Tests asserting legacy TUI scheduler refusal remain;
new TUI grant management must operate through separate service actions.

## Defaults and Owner decisions to settle

Retain dry-run/local preview, allow_repeat_same_day=false, account/day=20,
conversation/day=1, min interval=60 seconds, window=5 per 300 seconds,
concurrency=1 and no automatic retry. Turning repeat on must still require a
compatible conversation limit. UNKNOWN still counts and blocks until explicit
resolution; no new UI shortcut refunds quota or labels it SUCCESS.

Recommend a two-target daily budget of two only when the user explicitly selects
two recipients and approves the resulting preview. Seven days means an explicit
14-attempt total budget, not a success guarantee; manual markers and UNKNOWN
within scope consume that budget. Reuse current 08:00 reference time and
60-minute window as visible suggestions; never silently save/activate defaults.
Keep grant validity finite (existing max 31 days) and derived worker manifests
finite. Shorter windows/max_wait must be validated for the reviewed workload.

Owner must decide:

1. Restore enforced identity block pending independently reviewed contract,
   or authorize a separate evidence-review phase before changing behavior?
2. Accept the proposed phase order and file scope, and approve H0 alone first?
3. Confirm HH:MM (00:00-23:59): the task's formatted text says HH, but previous
   feedback and existing service contract require HH:MM.
4. Confirm inbox online opt-in and Windows manual UI vs Debian unattended scope.
5. Confirm active-policy edits require explicit pause/revoke/re-authorization,
   rather than mutating existing authorized grants.
6. Confirm seven-day/two-target budget and proposed visible time/window defaults;
   they are configurable internal limits, not anti-bot guarantees.

## Regression and cross-platform matrix

| Area | Required offline coverage | Platform/limitations |
| --- | --- | --- |
| Identity | Full vs isolated cookie conflict; missing/invalid session before any HTTP; guest/challenge/redirect/wrong-origin/duplicate-script/HTML corruption; UID canonicalization; cache forbidden; generation and circuit ABA; no binding on failure | Synthetic transports on Windows/Python 3.10 + Debian/Python 3.13; sanitized contract provenance separately reviewed |
| Encoding | UTF-8 Vietnamese/emoji reasons/content, ASCII stdout fallback, undecodable stdin, EOF/non-TTY/cancel; fingerprint unchanged and no grant on failed confirmation | Fake streams plus Debian locale/SSH fixture without real credentials |
| Capture | Optional imports, executable absent, failed launch/context, timeout/cancel, multiple candidate pairs, malformed keys, session mismatch, failed probe prevents write, cleanup/no-token output | Fully mocked Playwright/WS on both; actual browser readiness/live capture separately authorized |
| Two-target scheduler | 60-second temporal wait, released lock/DB/WS, atomic gates after wake, manual marker budget, UNKNOWN, pause/revoke/ABA, stop during bounded echo, crash recovery, expiry/day boundary, duplicate concurrent ticks | Existing tests plus synthetic two-target workload; real POSIX lock/signal tests on Debian |
| TUI | Pilot tests across small/normal terminals; dropdown open/selection; multiline byte-for-byte text; invalid time no writes; refresh failure and A/B/A result discard; fresh confirmation/cancel/stale dialog; no network at local startup | Full Textual optional fixture on Windows and Debian; terminal visual evidence in addition to AST |
| Status | SUCCESS described as server echo only; queued/UNKNOWN/FAILED distinct; all blockers and usage shown; retry_at is evaluation eligibility, not promised delivery | Read-only synthetic ledger fixtures, no migration or credentials |
| Deploy/upgrade | Two-target artifact validation, unsupported windows/budgets, escaping/path confinement; existing Restart=no and stop bound; no automatic install; Backup API/WAL, runtime permissions, explicit migrations and preserved grants/history | Windows unit-text simulation; native Debian offline fixture required; systemd activation is not part of tests |

Every approved implementation phase runs the full guarded suite plus targeted
tests. Do not suppress failures or equate additional skips with full acceptance.
AST/import and CLI help checks complement runtime tests. Preserve packet and
echo use of immutable snapshot; quota from send_requests markers; rotation only
on committed SUCCESS; FIFO/atomic claim; unknown audit history; no hidden retry.

## Evidence, limits and stop condition

Evidence files: `work/post-live-review-evidence/full.txt`, `static-probes.txt`,
`source-hashes.json` and a sanitized execution summary published for review.
No private artifacts are included. Baseline counts and parser probes describe
the audited commit, not a new fix. Terminal root cause, dropdown visual defect,
browser native prerequisites and production identity remain unresolved.

This report is the only repository change. No application/test/dependency edit,
service activation, deployment, runtime migration or live interaction occurred.
Rollback of this planning artifact has no runtime effect. STOP at REVIEW REPORT;
await explicit Owner approval before implementing H0 or any later phase.
