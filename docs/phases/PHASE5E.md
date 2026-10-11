# Phase5E — Root hygiene

Status: REPORT; independent Technical Owner review pending.
Baseline: accepted Phase5D-G6, 451 total, 448 PASS, 3 SKIP, 0 FAIL/ERROR.

## Approved changes

| Previous path | Current path | Preservation |
|---|---|---|
| requirements-tui.txt | requirements/tui.txt | Byte-identical |
| requirements-auth-windows.txt | requirements/auth-windows.txt | Byte-identical |
| requirements-windows.txt | requirements/windows.txt | Byte-identical |
| browsercookies.py | tools/browsercookies.py | Byte-identical |
| test_ws_capture.py | tools/test_ws_capture.py | Only ROOT expression changes to parents[1] |

requirements.txt remains at root unchanged. Optional dependency groups remain
separate, without forcing Windows/browser/UI dependencies into Debian core.
tools/__init__.py is inert. No internal Python importer of either manual tool
was found; former root manual filenames are explicitly retired, not silently
promised as compatible. Use from tools import browsercookies for the optional
Windows library. Direct manual browser diagnostics use
python -B tools/test_ws_capture.py only under separate live authorization.
These manual commands were not executed during this phase.

The capture's ROOT and work/tiktok-browser-profile location remain the repository
root and previous private location, rather than tools/work. Cookie extraction
logic and platform refusal are unchanged. Synthetic Windows-platform import and
fake Playwright SDK fixtures prove import/path behavior without browser launch
or cookie access; actual Windows browser functionality remains unverified.

Technical Owner clarified the original keep-main-unchanged requirement: exactly
two dependency-path diagnostic strings in main.py and the corresponding string
in relttk/transport/qrlogin.py may change. Those are the only application edits;
AST equivalence after normalizing the three approved string replacements passes.
operational_entry.py, compatibility entrypoints and all sending/storage/auth
algorithms remain byte-identical. Identity Contract remains BLOCKED; schema V8,
FIFO, UNKNOWN, consent, budget, quota and circuit gates remain unchanged.

tests/source_checks.py adds tools to recursive allowlisted roots. Scanner discovery
was proved with a nested synthetic tools canary before relocation. Existing
private-directory and symlink rules remain. tests/test_root_hygiene.py adds six
guarded tests. No original assertion was removed or relaxed.

README and current architecture guide describe requirements/tools commands and
the actual tree. Dependency filenames and affected clickable tool links in other
documents now resolve to current locations. Historical descriptions and test
counts remain historical; updating path references does not claim those older
phases were rerun. The full changed-file list is preservation.json in evidence.

TERMUX.md is shortened to a minimal retirement/compatibility notice with Debian
and archive links. It remains because unchanged diagnostics still reference it;
removing it would break those references. Termux/Android is not supported.

## Private-data and ignore review

The existing .gitignore already covers work/, state/, sesion/, sessions/, .env
variants, local JSON, auth/credential/cookie files, private UID cache, profiles,
SQLite database variants and WAL/SHM/journal sidecars. It remains byte-identical.
The new regression checks literal coverage using synthetic names. This is an
ignore-policy review, not a claim that already tracked private files are untracked
or that every conceivable secret filename is excluded. No Git staging/index
operation or credential scan of actual private files was performed.

work and runtime private data were neither read, moved, deleted nor staged.
Ignored reviewed source evidence lives separately under work/phase5e-evidence;
it is not a browser profile, session backup or runtime migration. Before edits,
all 150 accepted G6 reviewed hashes matched and exact source bytes were frozen.
The three requirements and cookie helper retain original bytes at mapped paths.

## Verification

Full guarded suite: **457 total, 454 PASS, 3 SKIP, 0 FAIL/ERROR**, 57.945 seconds,
exit 0. The count increases by exactly six new root-hygiene cases. The same three
Windows skips remain: actual POSIX permissions and two SQLite no-checkpoint/WAL
capability tests. No additional skips or failures occurred.

Focused scanner/root-hygiene run: 14 total, 14 PASS, 0 SKIP/FAIL/ERROR, 1.313 seconds.
All 109 Python files parse on Python 3.10.11 and 3.13.3. Five guarded imports and
four CLI help commands pass from a disposable alternate cwd. Static comparison
proves the approved diagnostic-only edits and capture-only ROOT expression change.
Optional dependency files and core requirements contain the same dependencies as
before; no installation or network package resolution was performed.

New cases cover inert tools import, fake SDK import/direct-script namespace and
profile anchor, Windows cookie-helper import without extraction, recursive tools
security canary refusal, dependency/manual-path presence and ignore rule coverage.
Existing full-suite safety, alias, path, operational silence, concurrency, WAL,
UNKNOWN and consent tests remain. The runner installs network/runtime-data guards
before application imports. Local Markdown checks are recorded in links.json.

Evidence: before/after-hashes.json, moves.json, preservation.json, static.json,
python-paths.json, links.json and sanitized-tests.txt under work/phase5e-evidence.
C2C receives only the sanitized execution summary, not private data or raw logs.

## Remaining root and rollback

```text
main.py / operational_entry.py / __init__.py
requirements.txt / streak.json
README.md / CHANGELOG.md / LICENSE / TERMUX.md / .gitignore
requirements/ / tools/ / relttk/ / core/ / signers/ / plugins/
deploy/ / tests/ / docs/
```

Root private/ignored directories may still exist; their contents were intentionally
not inventoried or altered. Source counts: root 3, relttk 51, tools 3, tests 37,
core 5, signers 3, plugins 6, deploy 1 = 109 Python files. No claim that private
workspace clutter or previously committed history was deleted is made.

Rollback restores the five moved originals and all changed consumers/docs/scanner
from the verified G6 snapshot as one group. Remove only reviewed new tools/__init__.py,
canonical tool paths, new test/report and optional requirements destinations after
checking exact absolute targets and hashes. Do not remove private runtime data or
unknown Owner files. Restart interpreters and rerun accepted G6 guarded baseline.
No Git reset/clean, schema rollback or service operation is required.

Native Debian/Python 3.13 dependencies, permissions, locking and WAL capabilities
still need separate Owner-operated offline fixture testing. Unofficial TikTok APIs,
unverified streak credit, BLOCKED identity provenance and unmanaged legacy helpers
remain known limitations. No live TikTok, real credentials/session/runtime DB,
Git writes, SSH/VPS, systemd or deployment actions occurred.

STOP at REPORT. Owner commits/pushes manually after independent review.
