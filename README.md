# TikTok Client Bot

This project uses **unofficial, reverse-engineered TikTok internal APIs**.
Whether messages sent through the bot count towards TikTok streaks **has not
been verified**. A correlated server echo confirms a server-side message
outcome, not that the recipient read the message or received a streak credit.

**Identity Contract remains BLOCKED.** Authenticated-self UID provenance has
not been established; real bootstrap and managed sending fail closed. Offline
Phase4 acceptance does not authorize live sending, production migration or deployment.

**Debian 13 is the only current staging target.** Termux/Android is retired.
Optional setup/TUI supports Windows and Debian; native browser and terminal
acceptance still needs Owner testing.

## Offline dry-run

Run commands from the repository root:

```sh
python -B main.py
```

The default command reads only the plan. It does not read session cookies, open
network connections, load plugins or open the ledger. The shipped `streak.json`
is intentionally unconfigured; validation messages and exit code1 are expected.

Copy the sample to a Git-ignored personal configuration before editing it:

```sh
cp streak.json streak.local.json
python -B main.py --config streak.local.json
```

Configure the selected session, exact conversation identifiers and message or
user-defined templates. Do not guess recipient IDs. Changes to a plan do not
send messages. CLI, retained TUI and future integrations use shared application
services; legacy mutation entrypoints remain guarded.

## Source layout and import compatibility

The 22 approved G1–G5 implementations now use the canonical `relttk` namespace:

```text
main.py / operational_entry.py     supported command entrypoints
relttk/
  config.py / log.py / runtime_paths.py / operations.py
  application/                    CLI, services, retained TUI
  transport/                      client, one-shot send, QR/auth tools
  storage/                        ledger, requests, migrations, queue
  runtime/                        worker, grants, rotation, UNKNOWN resolution
  identity/                       identity, readiness, circuits
  compat/legacy/                  22 fixed module aliases
core/ / signers/ / plugins/        retained protocol and legacy modules
tools/                            explicit manual Windows tools
requirements/                     optional dependency groups
```

For integrations, prefer canonical imports, for example
`from relttk.application import services`. Existing bare imports require explicit
bootstrap in each new process:

```python
from relttk.compat import enable

enable()
import operations  # same module object as relttk.operations
```

Official entrypoints and the guarded runner establish compatibility themselves.
The operational entry suppresses output before importing application modules.
Old moved filenames are not supported script entrypoints. Package initializers
are inert; importing a module does not authorize sending or initialize a database.
Root `__init__.py` preserves the legacy client export. `tools/browsercookies.py` and
`tools/test_ws_capture.py` remain manual REVIEW-only tools; do not run them as staging
checks. No runtime/session/database directory has moved.

Accepted G5 layout baseline: **451 total, 448 PASS, 3 SKIP, 0 FAIL/ERROR** on
Windows/Python 3.10. Python 3.13 AST checks alone do not certify runtime behavior.
See the [final layout verification report](docs/phases/PHASE5D_FINAL.md) for G6
results, import contracts, rollback evidence and Debian staging blockers.

Optional dependencies are installed explicitly when needed, for example
`python -m pip install -r requirements/tui.txt` for the full UI test fixture.
Browser authentication is an explicit optional dependency in
`requirements/auth-browser.txt`; `requirements/auth-windows.txt` is a compatibility
include. Windows cookie extraction remains separate from Debian requirements.
The former root manual filenames have moved: import the Windows cookie helper as
`from tools import browsercookies`. Browser diagnostics use
`python -B tools/test_ws_capture.py` only with separate live authorization;
these tools are not staging test commands. The capture profile location remains
unchanged. See [root hygiene evidence](docs/phases/PHASE5E.md).

## Documentation

- [Current module architecture and maintenance contracts](docs/architecture/MODULES.md)
- [Sending safety and limits](#sending-safety-and-limits)
- [Guarded offline checks](#dependencies-and-guarded-checks)
- [Debian operations and backup](docs/operations/DEPLOY_DEBIAN.md)
- [H0–H5 changes and combined Debian test](docs/operations/HARDENING_H0_H5.md)
- [TUI automatic inbox, time input and F2 send settings](docs/operations/TUI_USABILITY.md)
- [Owner-operated Debian fixture checklist](docs/operations/PHASE4D_OWNER_CHECKLIST.md)
- [Current security regression evidence](docs/evidence/EVIDENCE_PHASE4_SECURITY.md)
- [Cleanup audit and approval plan](docs/phases/PHASE5_REPO_CLEANUP_PLAN.md)
- [Historical security/architecture review](docs/security/REVIEW.md)
- Phase records: [Ledger V2](docs/phases/PHASE2.md),
  [rate limits](docs/phases/PHASE3A.md), [rotation](docs/phases/PHASE3B.md),
  [circuits](docs/phases/PHASE3C.md), [queue/UNKNOWN](docs/phases/PHASE3D.md),
  [finite worker](docs/phases/PHASE3E.md), [readiness](docs/phases/PHASE4A.md),
  [identity design](docs/phases/PHASE4A_IDENTITY_CONTRACT_PLAN.md),
  [bounded recurring grants](docs/phases/PHASE4B.md),
  [offline deployment artifacts](docs/phases/PHASE4C.md).
- [Termux retirement notice](TERMUX.md); [archived guide](docs/archive/TERMUX.md)
  is historical only.

Older phase documents preserve their original decisions and test counts. They
are not claims that the current release was retested at those earlier milestones.

## Dependencies and guarded checks

Core CLI requirements remain separate from optional components:

```sh
python -m pip install -r requirements.txt
python -B main.py --help
python -m pip install -r requirements/tui.txt  # full guarded UI coverage
python -B tests/run_offline.py
```

Historical Phase4 security baseline on Windows/Python3.10: **390 total, 387 PASS,
3 SKIP, 0 FAIL/ERROR**. The skips cover POSIX permissions and two SQLite WAL
capability tests. The [evidence record](docs/evidence/EVIDENCE_PHASE4_SECURITY.md)
contains the original result/provenance. The full baseline includes optional
Textual UI coverage; a core-only environment with additional UI skips is not
an equivalent result. `requirements/tui.txt` is available for the disposable
full-test fixture. Browser-auth extras are in `requirements/auth-browser.txt`;
Windows cookie extras are in `requirements/windows.txt`. Install neither for
ordinary guarded core tests.

For Debian core-only installation, Textual is still optional. Install
`requirements/tui.txt` in the disposable full-test venv before claiming the full
regression baseline; otherwise the TUI execution case is explicitly skipped.
See [Debian staging harness fix](docs/operations/DEBIAN13_STAGING_FIX.md).

Use the guarded runner rather than an unrestricted test discovery command.
It blocks external networking and protected runtime-data access while tests
use synthetic fixtures and fake WebSockets. Debian13/Python3.13 permissions,
locking, dependency builds and SQLite WAL capabilities require separate offline
fixture verification. A venv isolates dependencies, **not security privileges**.
No scheduler/service is installed or activated by these source artifacts.

## Sending safety and limits

- `send_requests` is the durable source of quota and transmission markers;
  account/day and conversation/day use `Asia/Ho_Chi_Minh`. Defaults are local
  policy, not TikTok-guaranteed thresholds for avoiding bot detection.
- Idempotency is independent of intentional repeat. Replay does not reserve or
  send again; repeat requires explicit settings and remains subject to limits.
- UNKNOWN consumes quota and blocks further requests until reviewed, across days.
  Resolution does not manufacture SUCCESS, refund quota or advance rotation.
- Template snapshots are immutable. SUCCESS advances rotation; FAILED/CANCELLED
  do not randomize another selection. Stale snapshots need separate confirmation.
- FIFO/atomic claim and all binding, budget, circuit and consent gates apply to
  managed CLI/TUI/worker paths. The finite worker processes existing approved
  requests only; it does not auto-enqueue or retry UNKNOWN.
- Preview/status/dry-run never imply authorization. Recurring grants require
  explicit authorization/activation. Old TUI schedule preferences do not grant
  permission to send automatically. Identity BLOCKED prevents live use.

## Credentials, services and remaining risks

QR login/inbox/profile/message helpers reference TikTok web/internal endpoints,
including www.tiktok.com, web-sg.tiktok.com, im-api-sg.tiktok.com and
im-ws-sg.tiktok.com. Signing runs locally. Retained media helpers reference
TikTok CDNs; legacy media mutations remain unsupported by the Safety Layer.
Sample plugins/stranger automation are disabled; the former external video
upload plugin is inert and protected by regression tests.

Session/auth JSON is plaintext sensitive material. Existing private writes,
POSIX permissions, symlink checks and session binding remain necessary;
Windows chmod alone does not establish NTFS ACLs. No real credential, cookie,
auth URL, runtime DB, browser profile or private capture belongs in source/Git.
The inherited manual browser diagnostic is not an offline test or staging command.

The embedded upstream WS key and its fallback were removed. URL construction
requires an explicit valid key and matching ttwid; URL/config authentication
parameters are rejected. This preserves session-bound auth; it does not establish
the Identity Contract. Live auth/capture/probe/login commands contact TikTok and
must not be invoked during offline staging or cleanup.

Previously published Git history/clones may retain the old literal. Its owner
should revoke/rotate it if possible. History cleanup needs separate coordinated
approval; ignore rules do not sanitize already tracked or historical content.
No history rewrite is performed by this project cleanup.

## License

MIT. See [LICENSE](LICENSE).
