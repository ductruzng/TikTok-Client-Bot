# TUI inbox, layout and settings update

The later [approved navigation layout](TUI_NAVIGATION.md) supersedes placements
described below. Message editing is now in Conversations, time is only in the
schedule editor, F2 contains send policy only, and the old sidebar is removed.

Owner requested automatic inbox sync, stable search layout, restricted time
editing and a settings interface for the existing six rate-limit fields.
Windows and Debian remain the supported direction; this does not restore Termux.

## Behavior

- On startup select the configured saved account, or the first available account
  if that saved account is unavailable, and sync inbox once. Account changes sync
  again. No saved account means no fetch. This is an explicitly requested online
  inbox read, not an authentication bootstrap or send authorization.
- Use the existing bounded inbox service. Only one fetch runs at once; switches
  during a fetch coalesce into one subsequent fetch for the latest account.
  Reject results from an older account generation, including A → B → A.
  Failure preserves drafts; no automatic retry. The Sync button retries explicitly.
- Search keeps a fixed three-row border box while focused. Compact terminals
  use a narrower sidebar and put the account selector above its two buttons.
  Reduce nested padding, obsolete scheduler controls and log height. The table
  shows selection, name and type; both exact IDs remain in row metadata and
  searchable. Filtering/selecting never invents IDs or changes sending rules.
- Both dashboard and schedule preview use the same HH:MM input, allowing only
  valid time prefixes, five characters maximum, with complete-time validation.
  Letters, invalid paste and out-of-range hours/minutes are refused; incomplete
  time shows a dashboard hint and cannot be saved. Content remains exact.
- **F2** or **CÀI ĐẶT GIỚI HẠN GỬI** opens a scrollable settings screen. It edits
  `max_sends_per_account_per_day`, `max_sends_per_conversation_per_day`,
  `allow_repeat_same_day`, `min_send_interval_seconds`, `max_sends_per_window`
  and `window_seconds` through existing `save_send_settings` and validation.
  Cooldown accepts zero; other numeric limits require at least one. Existing
  backend upper bounds remain unchanged. Repeat requires enough conversation
  quota; enabling repeat alone never bypasses quota. UNKNOWN still consumes quota.
- Cancel performs no writes. Invalid numbers, unreadable configuration, changed
  configuration and active recurring grants block saving. Pause/revoke and review
  new authorization before editing a policy with an active grant. Saves preserve
  unrelated config fields; the dashboard's skip-sent switch reflects saved repeat.
  A stale policy is additionally held by existing backend admission checks.

No scheduler, worker, migration, consent, identity or transport logic is modified.
These internal limits do not guarantee avoidance of TikTok bot detection.
Production Identity Contract remains BLOCKED.

## Files

- `relttk/application/tui.py`: automatic inbox reads, compact/stable layout,
  three-column table, settings action and F2 shortcut.
- `relttk/application/time_input.py`: shared restricted HH:MM input.
- `relttk/application/settings_ui.py`: existing send-policy settings screen.
- `relttk/application/schedule_ui.py`: reuse time input.
- `tests/test_tui_usability.py`: synthetic startup/switch/failure, layout/time
  and settings tests.
- `tests/test_hardening_schedule_ui.py`, `tests/test_safety_fixes.py`: mock the
  newly automatic fetch, maintain draft/ABA and legacy-disabled regressions.
- `docs/operations/HARDENING_H0_H5.md`: mark the previous mount policy superseded.
- This document records the follow-up behavior and verification.
- `README.md`: link to this usage/verification note.

## Validation and limits

All UI tests use synthetic sessions/inbox, mock account enumeration and config
reads, and disposable fixture paths. The full suite uses `tests/run_offline.py`
to block external network and real runtime data. No live TikTok calls or runtime
credential/database access were made during this update.

Pilot layout checks cover 80×24, 100×35 and 140×45; search focus and filtering
preserve widget regions. On small terminals the sidebar/settings scroll; F2
opens settings without needing to scroll to its button.

Native terminal font/emoji rendering and Debian interaction require Owner testing.
Python 3.13 on this machine lacks Textual; AST and guarded CLI help checks run
there, while actual Textual pilot tests run under Windows Python 3.10.

Final Windows/Python 3.10 guarded regression: **538 total / 534 PASS / 4 SKIP /
0 FAIL / 0 ERROR**, 98.418 seconds. This adds 11 synthetic UI tests to the
previous 527-test baseline. Full execution output is retained locally at
`work/hardening-evidence/tui-final310.txt` (ignored evidence, no credentials).

The focused UI/dropdown run passed 12 tests. AST parsing passed for all 122
Python source/test files under Python 3.10 and 3.13. Nine guarded CLI help
commands passed under Python 3.13. SHA-256 comparison confirms all nine
previously protected storage/runtime/circuit modules are unchanged.

## Follow-up: schedule configuration

The schedule screen now has **Tạo lịch** and **Lịch đã lưu** tabs. Name/time and
start/end dates have individual labels and equal-width fields, preventing the
full-width first input from covering the remaining inputs in its row. Initial
time comes from the dashboard's current time field. Seven/thirty-day presets
calculate the end date inclusively from the selected start date; backend limits
on current/future dates and maximum duration are unchanged.

Numeric budgets, waiting bounds and paths are in a collapsed advanced section.
Empty budgets retain the existing backend defaults. Technical JSON is available
in collapsed details instead of being the default review interface. Human
summaries show exact consent time/date range, recipient IDs, actual fixed message
or template details, budgets and status. Plain-text rendering prevents message
markup from altering the displayed review.

Preview/authorize/close actions remain at the bottom of the modal, outside the
scrolling form. First preview, then explicitly authorize, then use the saved
schedule tab to enable/pause/revoke permission. Input changes invalidate the
preview. Confirmation freezes the existing review and rejects changed account
generation, database path or preview inputs. Existing backend fingerprint/version
validation still runs; no backend/schema changes were made. Reasons and exact
action words remain mandatory. Enabling permission does not start a worker or
systemd service, and production identity remains blocked.

Changed in this follow-up: `relttk/application/schedule_ui.py`,
`relttk/application/tui.py`, `tests/test_hardening_schedule_ui.py`,
`tests/test_tui_usability.py`, and this document. Four synthetic schedule UI tests
cover labelled field geometry at three terminal sizes, collapsed advanced paths,
fixed actions, presets, preview invalidation and stale open confirmation. Existing
fixture lifecycle tests still exercise authorize/activate/pause/revoke without
tick or transmission. Native Debian terminal rendering remains unverified.

Schedule follow-up validation: guarded full suite **542 total / 538 PASS / 4 SKIP /
0 FAIL / 0 ERROR**, 113.814 seconds. Evidence:
`work/hardening-evidence/schedule-ux-verified310.txt`. A final footer-width CSS
correction and the stronger horizontal-bounds assertion subsequently passed all
four new schedule UI cases plus the existing full authority lifecycle case
(5 focused tests, 16.796 seconds). Python 3.13 AST (122 files), nine guarded CLI
help checks, documentation links and nine protected module hashes also passed.
No actual session, runtime database, live API, Git or deployment operations were
used. Confirmations and writes in lifecycle tests use disposable fixtures only.
