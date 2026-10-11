# Approved navigation layout and synthetic preview

Owner approved one left navigation column: Conversations, Schedule and Logs.
The old configuration sidebar is no longer mounted or styled. Its title, info
block, time field, disabled scheduler switch, skip-sent switch and separate
settings/schedule buttons are absent from the main screen. Removing the
`VerticalScroll #sidebar` also removes its right-side scrollbar and corner block.

## Placement

- Header: account selector, refresh-all, explicit QR login, F2 settings.
- Conversations: name/ID search, direct/group filter, selection table, exact
  multiline streak message, draft/saved indicator, **Lưu tin & người nhận**.
  **Gửi ngay** and **Chạy thử** remain below the conversation region. No main
  time field, separate preview button, configuration tab or duplicate log button.
- F2: only skip-if-sent-today and the five numeric rate-limit fields. The switch
  stores the inverse of existing `allow_repeat_same_day`; no competing repeat
  controls. No message or schedule time field is mounted here.
- Schedule page: account, saved recipient count, saved exact message, explicit
  recurring status and configure/manage button. The existing schedule modal
  supplies labelled time/date fields, 7/14/30-day presets, preview, separate
  authorization, saved grant status and activate/pause/revoke confirmations.
  The schedule modal also shows the saved message/recipient count on opening.
- Logs: the existing in-memory activity history, preserved when navigating and
  refreshing. Refresh does not pretend to fetch an external persisted log.
- Status bar: **Scheduler: TẮT · cần recurring consent** remains visible. This
  describes the disabled TUI background scheduler; individual grant states are
  shown separately. Active grants do not start a worker or systemd service.

Refresh-all rereads account names and saved configuration, reloads recurring
grant status, fetches the latest inbox through the existing bounded service and
updates activity/status. Unsaved message/selection drafts remain intact; stale
account-generation results remain rejected. Failures report the affected part.
Missing/incompatible ledger status is reported, never initialized or migrated.

Save message/recipients uses existing `save_plan` and preserves the F2 send
settings. It does not write obsolete scheduler preferences. Their existing
service APIs and legacy send helper remain available; no backend logic, schema,
quota, identity, auth or transport implementation is removed or changed.

## Send-now limitation

The button opens a review of saved exact text and recipients. Unsaved or empty
selections are refused. The actual confirmation control is disabled because
the accepted production authenticated-self contract remains BLOCKED. Opening
the dialog performs no transmission, request creation, identity lookup or auth
bootstrap. This work does not claim to implement or enable live TUI sending.

## Preview and files

Run `python -B tools/tui_mockup.py` in the existing Textual fixture environment.
It installs the offline guard and mocks sessions, inbox, config and recurring
state; it never reads real runtime data. It exports actual Textual screens at
120×40 to `work/ui-preview/index.html` and SVGs. The HTML embeds the SVGs,
requires no server/network and offers links to each example. All displayed data
is synthetic. The preview is an exported visual sample, not a browser bot.

Changed files:

- `relttk/application/tui.py`
- `relttk/application/settings_ui.py`
- `relttk/application/schedule_ui.py`
- `tools/tui_mockup.py` (new)
- `tests/test_tui_usability.py`
- `tests/test_hardening_schedule_ui.py`
- `tests/test_safety_fixes.py`
- This document (new) and the link in `TUI_USABILITY.md`.

No old configuration layout remains on the main screen. Scrollbars inside the
new schedule/settings dialogs are intentional, not remnants of the old sidebar.
The schedule editor still opens as a modal from the Schedule page. Native
Debian/font rendering remains unverified; this pass uses headless Textual pilots.

Guarded Windows/Python 3.10 full suite: **545 total / 541 PASS / 4 SKIP / 0 FAIL /
0 ERROR**, 133.306 seconds. Evidence is retained at
`work/hardening-evidence/navigation-final310.txt`. Three new tests cover the
approved placement, refresh-all draft preservation and the blocked send-now
review. The final per-account saved-count correction was also checked with two
focused layout/refresh tests (both PASS). Source parsing passed for 123 Python
files on Python 3.13, nine guarded CLI help checks passed and the SHA-256 hashes
of nine protected storage/runtime/circuit modules remain unchanged.

Actual Textual export produced all four sample SVGs and a standalone HTML
gallery. Geometry tests cover 120×40 and existing 80×24/100×35/140×45 sizes.
No real session, runtime ledger, live HTTP/WS, Git, SSH or deployment operations
were performed. Native Debian interaction remains for Owner validation.

## HTML prototype adaptation (Owner approved)

The HTML prototype is a visual reference, not executable application logic.
Its dark palette, teal focus/title accents, muted help text, amber warnings and
green saved-state labels now use native Textual styling. The approved left
navigation and message editor below the table remain in place. No web frontend,
new dependency or backend/schema change was introduced.

Inbox has a fixed-height inline notice for no account, loading, empty inbox,
sync failure and no search results. Failed refresh keeps the exact message and
selection draft; the notice is tied to account/generation and does not trigger
automatic retries. Checkbox/name cells render literal text, including brackets
in nicknames. The short-terminal editor removes its border so its two content
lines remain visible at 80×24. The table fills the available width on mounting.

F2 places labelled numeric inputs beside their labels and keeps Save/Cancel
outside the scrolling body. It continues to use the same shared validation and
active-grant/stale-config checks. Schedule retains native validated time/date
inputs, duration presets, collapsed advanced fields and separate consent steps.
Its name field is explicitly labelled as an ID; Unicode display names, a native
HTML date picker, editable grant names and structured log filtering are not
included. Logs remain an in-memory activity view and explicitly distinguish
saving configuration from successful transmission.

The synthetic gallery now contains seven actual Textual exports: conversations,
F2, schedule overview, schedule editor, blocked send review, logs and an 80×24
conversation screen. All data is fake, including inbox logs; no TikTok connection
was opened while exporting. Geometry and interaction are checked with headless
pilots; native Debian terminal/font interaction still requires Owner testing.

This adaptation changes `tui.py`, `settings_ui.py`, `schedule_ui.py`,
`tools/tui_mockup.py`, `tests/test_tui_usability.py` and this document only.
The old configuration sidebar remains absent. Scrollbars within tables or modal
content are native controls, not remnants of that sidebar.

Final adaptation validation on Windows/Python 3.10/Textual 8.2.8:
**549 total / 545 PASS / 4 SKIP / 0 FAIL / 0 ERROR**, 136.084 seconds.
Full guarded evidence: `work/hardening-evidence/html-adaptation-final310.txt`.
The four added tests cover failed/retried inbox notices with exact draft
preservation, account-scoped error notices, literal selection/nickname rendering
and visible multiline content at 80×24, and fixed F2 actions at 120×40/80×24.
Existing search/focus geometry and scheduling/consent tests remain passing.

Python 3.13 AST parsing passed for 123 Python source files; nine guarded CLI
help commands and documentation link checks passed. SHA-256 comparison confirms
the nine protected ledger/queue/runtime/circuit modules remain unchanged.
Evidence: `work/hardening-evidence/html-adaptation-checks313.txt`.
This is not a full Python 3.13 Textual run or native Debian validation. The four
platform/capability skips remain explicit. No real runtime or live send was used.
