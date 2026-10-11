# H0A: identity evidence and bounded schedule terminal fixes

Task: `post-live-h0a-evidence-encoding`. Owner approved evidence-first H0A only.
Baseline: `6b3ee1b`; 475 tests, 471 PASS, 4 SKIP, 0 FAIL/ERROR on Windows.
Status: implementation/test report; independent review required. STOP after H0A.

## Scope and exact changes

| File | Change |
| --- | --- |
| `main.py` | Schedule administration locally uses strict input and encoding-safe output helpers |
| `relttk/application/terminal.py` | Small stdlib-only terminal helper; no global stream mutation |
| `tests/test_terminal_encoding.py` | 13 tests using synthetic streams and disposable V8 grant fixtures |
| `tests/test_h0a_identity_evidence.py` | 14 observational/caller-boundary identity tests |
| `docs/operations/H0A_IDENTITY_ENCODING.md` | This evidence and limitation report |

Identity implementation, accepted verification behavior, generation binding,
circuit versions, readiness policy, schema, worker, scheduler, transport and
dependencies are unchanged. This report does not approve production identity
assurance or unattended deployment. The earlier planning report remains a
separate uncommitted document; it is not an H0A source change.

## Reproduced encoding failures and fix

Before H0A, schedule administration called `input()` directly and broadly
caught ValueError. UnicodeDecodeError is a ValueError, so an invalid byte read
could be reported only as `Schedule operation blocked: UnicodeDecodeError`.
EOFError and KeyboardInterrupt were not converted into a bounded schedule
refusal by that handler. A terminal unable to encode displayed characters
could raise UnicodeEncodeError. These are reproducible with synthetic streams.
The original Debian failure's actual locale/bytes/traceback were not supplied
for this task: its exact root cause remains a hypothesis, not a verified match.

The schedule handler now uses scoped helpers only; other CLI menus, TUI,
QR login and worker/identity administration were not refactored in H0A.

Input remains exact: no trim, replacement, ignored bytes or implicit locale
conversion. Decode failures, EOF, cancellation and prompt encoding errors
produce ASCII, credential-free reason codes and return the existing blocked
exit status 3. Streams configured with lossy decoding such as `replace` or
`ignore` are refused before reading. Standard POSIX `surrogateescape` is
allowed for valid input, but decoded surrogate bytes are explicitly refused
by strict UTF-8 representability validation. Exact fingerprint/version
challenges are unchanged; whitespace/case mismatches still return status 1.
The TTY gates and transaction freshness checks remain unchanged.

Output is encoded for the terminal before writing. Unrepresentable characters
use backslash escapes for display only, avoiding ASCII-terminal encoding
failure. Stored reason, exact message, policy snapshot, fingerprint and
confirmation input are not transformed. Existing schedule JSON previews remain
ASCII escaped. No global `sys.stdin`/`sys.stdout` reconfiguration occurs.
Generic I/O failures or a broken output pipe are not promised recoverable;
an operation already committed must be inspected rather than blindly repeated.

For a UTF-8 SSH/terminal fixture, explicitly configure a UTF-8 locale and
strict input decoding. For example, in an Owner-operated Debian shell where
`C.UTF-8` is installed:

```bash
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
export PYTHONIOENCODING=utf-8:strict
```

On Windows, an Owner-operated PowerShell can set
`$env:PYTHONIOENCODING = 'utf-8:strict'` before starting Python. These are
optional diagnostic settings, not actions performed by Codex. They cannot
recover malformed bytes already sent by a client. Use offline synthetic tests
before attempting real administration; do not copy raw credentials or logs.

## Identity evidence: observations, not new acceptance policy

All response HTML, cookies and metadata in the tests are invented fixtures.
The tests deliberately characterize current behavior. Permissive cases are
named `current_*` and must be reconsidered at H0B, not treated as guarantees
or as a requirement to retain those omissions forever.

| Observation | What is demonstrated | What is not demonstrated |
| --- | --- | --- |
| One app-context script; matching odinId/user.uid/nonempty secUid | Current parser accepts this shape; rejects plain guest/challenge HTML without it | Authenticated account provenance |
| Synthetic isLogin=false or challenge marker outside matching context | Parser still accepts the candidate | Real TikTok guest/challenge response format or a live exploit |
| Matching full-cookie and sessionid-only candidates | Fresh API checks consistency and returns matching UID without UID-cache I/O | Independent identity authority; the same endpoint serves both |
| Conflicting full/isolated candidates | Current API refuses SELF_IDENTITY_COOKIE_CONFLICT | Completeness of all conflicting-cookie cases |
| Response with synthetic wrong final URL/type/status | API caller itself does not inspect final URL, headers or returned status | Real HTTP 403 acceptance: urllib normally raises HTTPError before returning such a response |
| Missing session in direct API | One mocked call precedes AUTHENTICATED_SESSION_REQUIRED | No transport for every direct caller |
| Invalid session type in direct API | AttributeError occurs before mocked transport | A typed, user-facing protocol error |
| Empty cookies argument and synthetic global config | Direct API falls back to configured cookies | That managed callers intentionally authorize global fallback |
| ASCII vs non-ASCII decimal UID | ASCII values roundtrip; malformed values reject; Arabic decimal digit currently accepts | Canonical ASCII-only validation |
| Identity service missing session | Explicit binding service stops before identity provider and writes no event | Uniform behavior of legacy/default-cache paths |
| Changed sessionid between verify and apply | Credential generation check refuses binding with no new event | Tracking changes to every cookie other than sessionid |

Existing full-suite tests continue covering session/account circuit ABA,
concurrent binding, cache refusal on fresh verification, stale previews,
transaction rollback and managed transport comparison to the verified ledger
UID. H0A leaves them in place. The cached helper used for inbox naming still
does not have the same authority as the fresh managed-send path.

README/readiness/operational labels remain BLOCKED/UNVERIFIED while the pilot
parser can execute. H0A does not resolve that discrepancy. A successful pilot
or synthetic parser test does not establish production safety, recipient
receipt or TikTok streak credit. Only an explicitly approved H0B can change
the verification contract or readiness policy.

## Tests and evidence

Final full guarded suite, Windows/Python 3.10.11: **502 total, 498 PASS,
4 SKIP, 0 FAIL, 0 ERROR**, 66.225 seconds, exit code 0. The 27 new tests
all pass; four existing platform-specific skips remain.

Targeted guarded tests on Windows:

- Python 3.10.11: 27 total, 27 PASS, 0 SKIP/FAIL/ERROR, 0.787 seconds.
- Python 3.13.3: 27 total, 27 PASS, 0 SKIP/FAIL/ERROR, 0.657 seconds.
- AST: 115 Python files parse on both interpreters.
- Guarded CLI help/import smoke: authorize, activate, pause and revoke PASS
  on both interpreters.
- Preservation hashes: all 112 pre-H0A Python files unchanged except the
  single schedule-scoped import in `main.py`; new helper and tests are explicit.

Terminal tests use real disposable SQLite fixtures to check zero grants/events
on failed authorization, unchanged existing history on decode failure during
activate/pause/revoke, exact versioned confirmations, Vietnamese/emoji reason
storage, multiline snapshot preservation and stale-policy rejection. Additional
stream tests exercise strict UTF-8, POSIX surrogateescape, lossy decoders,
ASCII output fallback, EOF, cancellation and prompt encoding failure.

Final full guarded suite results are recorded in the sanitized execution
summary under `work/h0a-evidence/` and published through C2C. Source-level
evidence is available in `full-final.txt`, `targeted310.txt`, `targeted313.txt`,
`checks310.txt` and `checks313.txt`. Raw application stdout stays suppressed by
the runner. No credential-bearing artifact is included.

Native Debian/Python 3.13 was not run locally; Windows stream simulations do
not certify native SSH locale behavior. Browser capture, live TikTok, actual
credentials/session/database, remote hosts, Git writes and services were not
used. Test-only database initialization is restricted to disposable fixtures.

## H0B decisions requiring separate approval

1. Independently review sanitized authenticated/guest/challenge contract
   evidence and decide whether candidate parsing can be promoted to verified
   identity; matching cookie responses alone are insufficient.
2. Decide missing/invalid session validation before all direct API transport,
   removal of implicit global-cookie fallback in the fresh path, canonical
   ASCII UID rules and bounded response size/metadata/origin handling.
3. Decide generation tracking for credential context beyond sessionid,
   appropriate refusal of guest/challenge responses and how evidence freshness
   is tied to binding. Do not invent unverified TikTok protocol fields.
4. Align enforceable identity gates and public readiness/operational status;
   no label-only production approval or silent override.

None of those acceptance changes were implemented here. Identity and all
consent, quota, idempotency, UNKNOWN, snapshot and audit safeguards remain as
audited. No unconditional refusal was restored and no new acceptance bypass
was introduced. Stop for independent review and a new Owner decision.
