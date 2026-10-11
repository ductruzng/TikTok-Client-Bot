# H0–H5 implementation and combined Owner fixture test

Owner authorized remaining H work directly in Codex on 2026-10-11. The earlier
plan's per-phase approval stops are superseded for this batch. No ChatGPT/C2C
handoff, live TikTok, credential/runtime database access, Git mutation, SSH,
deployment, systemd activation or runtime migration was performed.

## Outcome and important blocker

H0A terminal encoding work is retained. H0B closes a real policy discrepancy:
`extract_self_uid_candidate` parses display/diagnostic candidates only;
`verify_authenticated_self` refuses `AUTHENTICATED_SELF_CONTRACT_UNVERIFIED`.
Fresh `get_own_user_id(..., use_cache=False)` validates explicit session input
and refuses before transport/cache. No global-cookie fallback or old ledger
binding can promote a candidate to verified identity. Candidate UID validation
is ASCII canonical decimal, up to 20 digits. No TikTok login flag or protocol
schema was invented as an authentication authority.

**Production identity is not solved.** A sanitized authenticated-self contract
with independently established provenance is missing. The Owner's prior Debian
pilot demonstrates observed behavior, not that the parser is authoritative in
guest/challenge/conflicting cases. Production managed sending is therefore
blocked, including existing pilot bindings. All recorded bindings/grants/history
remain intact; no database change or migration is needed for this source update.
A future verified contract must establish origin, reject unsafe redirects,
validate response status/type/size/strict encoding and bound its entire transport.
Those HTTP cases cannot be promoted by the current universally refusing boundary.

H1–H4 are implemented offline for Owner fixture testing; H5 provides this test
procedure. Native Debian/browser/SSH visual acceptance is still Owner work.
Do not describe the whole product as production ready or all H acceptance gates
as passed while the identity evidence and native platform gates remain open.

## Changed files (this batch, excluding pre-existing H0A changes)

| File | Behavior |
| --- | --- |
| `core/self_identity.py` | Candidate/verified separation; canonical ASCII candidate IDs |
| `core/api.py` | Explicit session validation before fresh verification; remove unreachable unsafe dual-cookie promotion |
| `relttk/identity/identity_service.py` | ASCII canonical provider result validation |
| `relttk/transport/bounded_inbox.py` (new) | Spawned read-only inbox task, finite deadline and child cleanup |
| `relttk/transport/oneshot.py` | Use bounded inbox; keep event loop responsive during it; explicit WS open/close deadlines |
| `relttk/transport/ws_auth_capture.py` | Local preflight, finite launch/navigation, cleanup on setup failure, saved-session freshness after probe |
| `requirements/auth-browser.txt` (new) | Explicit optional Windows/Debian Playwright |
| `requirements/auth-windows.txt` | Compatibility include; cookie extraction not added |
| `deploy/render_units.py` | Narrow two-target artifact profile; no service operations |
| `relttk/application/services.py` | Exact fixed-message save; recurring list/status/challenges through existing backend |
| `relttk/application/tui.py` | Multiline editor, per-account drafts, ABA protection, time validation, dropdown border fix, explicit schedule screen |
| `relttk/application/schedule_ui.py` (new) | Preview/reason/separate confirmation; authorize/activate/pause/revoke/status; no tick/worker |
| `relttk/application/cli.py` | Fixed-message menu no longer trims the input |
| `main.py` | Local `browser-preflight`; capture help applies to both platforms |
| `tests/test_h0a_identity_evidence.py` | Replace historical permissive expectations with H0B refusal/candidate checks; original observations retained in H0A report |
| `tests/test_self_identity_parser.py` | Candidate still parses; verified promotion now refused |
| `tests/test_self_identity_cookie_consistency.py` | Matching/conflicting fixtures cannot promote unverified identity |
| `tests/test_circuit_breaker.py` | Fresh refusal makes zero HTTP/cache calls |
| `tests/test_tui_services.py` | Exact whitespace preservation expectation |
| `tests/test_safety_fixes.py` | TextArea assertion and disposable DB route for explicit TUI save action |
| `tests/test_hardening_browser_inbox.py` (new) | Fake lifecycle/CDP qualification, spawn deadline/reap, two-target units |
| `tests/test_hardening_schedule_ui.py` (new) | Shared grant service, actual UI lifecycle, drafts/ABA/layout, two-target fake packet/echo |
| `README.md`, `docs/operations/DEPLOY_DEBIAN.md`, `docs/operations/POST_LIVE_TEST_HARDENING_PLAN.md`, this document | Current dependency/profile/test guidance and historical-plan supersession notice |

SQLite remains V8. Queue/FIFO/atomic claim, marker-derived quotas, idempotency,
rotation, immutable snapshots, UNKNOWN, consent/circuit versions and worker
admission logic are unchanged. No new queue worker, scheduler or counter exists.

## Browser and bounded two-target profile

`python -B main.py browser-preflight` is a local explicit diagnostic. It checks
optional import/driver/executable only, reads no session and launches no browser.
LOCAL_READY is not a successful native sandbox/network/identity qualification.
Missing dependency/executable gives a sanitized BLOCKED reason, exit 3.

Owner may install `requirements/auth-browser.txt` and Chromium separately when
reviewing browser setup. `capture-ws-auth --session NAME` is online and remains
an explicit Owner action, never a send/tick/bootstrap hook. It uses ephemeral
context, hides candidate values, requires qualified handshake/frame evidence,
then probes the pair in memory before writing the session-bound private file.
When loading the saved session itself, a change during capture prevents saving.
No `--no-sandbox` default or automatic browser/dependency installation was added.

Inbox uses spawn, in-memory cookies/IPC, no credentials on argv/disk, suppressed
child output and a 4 MiB result cap. A 45-second deadline covers the entire
HTTP/name-enrichment task, followed by at most two bounded 2-second termination
joins. There is no retry. A subprocess/venv is **not a security sandbox**.
The child performs read-only TikTok calls, can use the legacy display UID cache,
and cannot claim/send or manipulate the ledger. Display names are not identity
authority. The Python event loop remains responsive while awaiting the task;
application shutdown may wait for bounded child cleanup.

Two targets require explicit daily_budget=2; seven days normally means a
14-marker total budget. Manual markers and UNKNOWN consume those budgets too.
max_wait<=300, cooldown<=max_wait, window>=15 minutes, at least fifteen minutes
before midnight, and max_sends_per_window>=2 are required by the renderer.
Two-target startup watchdog=900 seconds, stop=90; one-target stays 600/90.
The internal allowance is conservative policy, not a platform performance SLA.
Native process startup, SQLite/filesystem stalls and termination must be checked
on Debian. Timer remains Persistent=false; service Restart=no. Rendering
installs/activates nothing. UNKNOWN is never resent or treated as SUCCESS.

## TUI behavior

Run `python -B main.py tui` after explicitly installing `requirements/tui.txt`.
The later [TUI usability update](TUI_USABILITY.md), explicitly requested by the
Owner, supersedes the original offline inbox mount policy: an available selected
account now automatically syncs inbox at startup and on account changes. No
account means no fetch. Schedule-screen mount remains offline. QR on Debian gives an explicit
instruction to close the TUI, use `main.py login`, then reopen. It does not spawn
a guessed terminal or perform hidden login. Windows keeps the manual QR window.

Select the account, sync inbox, choose targets, enter exact multiline text and
HH:MM, save. Invalid time is checked before either file write. Refresh failure
preserves drafts; A→B→A cannot accept an earlier A fetch. Drafts are per-account
in memory and lost on application exit unless saved. Removed/mismatching server
conversation metadata clears only the affected recipient selection. A content
or recipient edit must be saved deliberately; active grants require pause/revoke
before the standard TUI save path. The backend additionally holds any stale
policy at admission. The two JSON saves are individually atomic, not a single
cross-file transaction; an I/O failure can leave preferences unapplied without
authorizing any send. Inspect saved state after an I/O failure.

QUẢN LÝ LỊCH opens a separate screen. Choose DB/config paths, schedule name,
time, dates, window and budgets; preview shows exact immutable policy. AUTHORIZE
opens a dedicated review with reason and the exact word AUTHORIZE. It creates
an inactive grant. Select the grant from the list (no manual ID/JSON copying),
then ACTIVATE in a separate dialog. Fingerprint/version/account/DB are frozen
in each action and transaction freshness checks still apply. PAUSE and REVOKE
are separate reasoned actions; a paused grant is not silently reactivated.
Create a new reviewed grant to resume after pause. No TUI background timer,
schedule tick, service installer, automatic grant renewal or live send was added.
Closing the screen/app does not change authority.

Status shows marker usage, per-recipient last 50 requests, UNKNOWN/queued/
confirmed and current admission holds (including usage/re-evaluation time where
the backend can determine them). Higher-priority parent/circuit/policy holds
can prevent reaching rate checks. Retry time is not a delivery promise or timer.
Confirmed means correlated **server echo**, not recipient delivery/read/streak.
The manual button is explicitly labelled preview; its legacy send-confirmation
callback still refuses transmission and directs the Owner to managed CLI.

## One combined Debian offline fixture test

Use a disposable source checkout/ZIP and new test venv, **not production runtime**.
Do not put credentials or a real database in the fixture. From its repository root:

```bash
umask 077
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
export PYTHONIOENCODING=utf-8:strict
python3 --version
python3 -m venv --copies work/debian-test-venv
work/debian-test-venv/bin/python -m pip install -r requirements.txt -r requirements/tui.txt
work/debian-test-venv/bin/python -m pip check
work/debian-test-venv/bin/python -B tests/run_offline.py
work/debian-test-venv/bin/python -B main.py --help
work/debian-test-venv/bin/python -B main.py browser-preflight --help
work/debian-test-venv/bin/python -B main.py schedule-authorize --help
```

Do not run unguarded discovery or `--send`, schedule-tick --execute, capture,
login, ws-probe, operational runtime commands or systemctl as part of this batch.
Browser-preflight without --help remains local but may report expected BLOCKED
when browser extras are absent. Install browser extras only for a separately
chosen local browser fixture; guarded lifecycle tests already use fake Playwright.

Report interpreter/OS/architecture, dependency-check result, total PASS/SKIP/
FAIL/ERROR, skip reasons and sanitized failed-test traces only. Debian/Python3.13
may unskip POSIX/WAL capability cases and skip the Windows-only renderer case;
do not require matching Windows skip counts or hide extra dependency skips.
No cookies, URLs containing auth, auth files, profiles, UID/cache captures,
runtime DB/WAL or raw live transcript should be sent.

Then review TUI manually in an empty private fixture with explicit
TIKTOK_RUNTIME_DIR set **before launch**, at 80×24 and 140×45: dropdown, multiline
Vietnamese/emoji text, invalid HH:MM, keyboard navigation and dialog readability.
Do not copy production credentials/database to enable it. Full selection/grant
flow is exercised by the guarded pilots using disposable fixture bindings.
Do not guess or bind a real UID to bypass identity. If native offline checks pass,
production contract evidence still needs review before any live/bounded trial.

## Validation and rollback

Final guarded Windows/Python3.10.11 run: **527 total / 523 PASS / 4 SKIP /
0 FAIL / 0 ERROR**, 81.595 seconds, exit 0. This adds 25 tests to H0A's
502-test baseline; no tests were removed. The existing four Windows capability
skips remain (POSIX permissions, native Linux dir_fd guard, two SQLite WAL capabilities).
Actual Textual UI pilots are included, not skipped.

Python3.13.3 on Windows: **38 targeted tests PASS / 0 SKIP / 0 FAIL / 0 ERROR**,
1.472 seconds (identity/encoding/browser/inbox). Full Python3.13 runtime suite
was not run: this interpreter lacks Textual/websockets/lz4. Both interpreters
parse all **119 Python source files** and pass nine guarded CLI help checks.
Local documentation links pass. Hash comparison confirms nine critical
ledger/queue/worker/scheduling/rotation/UNKNOWN/circuit modules unchanged.

Evidence under ignored `work/hardening-evidence/`: `full-final310.txt`,
`targeted313.txt`, `checks310.txt`, `checks313.txt`, `source-sha256.json` and
`summary.json`. Failed intermediate runs remain there for diagnostics; only
the named final run is the acceptance result. Source SHA256 manifest contains
paths/hashes only. A self-review found the unused new screen field and removed
it; the final full run includes this cleanup and the dialog-generation regression.
Ponytail complexity review found no further necessary deletion; stdlib lifecycle
cleanup and existing services/SQLite are reused without another framework.

The earlier H0A baseline was 502 total / 498 PASS / 4 SKIP on Windows/Python3.10.
Native Debian/systemd/browser/TikTok and actual SSH encoding are not verified
locally. Offline lifecycle/CDP tests are synthetic, not a production attestation.

Rollback is source-only to the reviewed pre-batch files while keeping V8 and
all runtime history. Do not restore a stale DB, delete marker/audit rows, reset
circuits, rebind identity or renew grants as part of rollback. An old source
version with permissive candidate verification is not recommended as a safe
production rollback. No Git history or runtime state was changed in this task.
