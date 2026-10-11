# Phase5F — Dependency consolidation blocked at offline preflight

Status: CANCELLED / REPORT. No dependency consolidation was applied.
Accepted Phase5E checkpoint remains intact: 457 total, 454 PASS, 3 SKIP,
0 FAIL/ERROR from its previously recorded guarded run. That suite was not rerun
or claimed as a new Phase5F result.

## Owner cancellation

Owner cancelled Phase5F and dependency-artifact work. No pyproject.toml will be
implemented under this task. All four accepted Phase5E requirements files remain.
The original BLOCKED report below is historical, not an active resume request.

The interrupted second download command completed in the background before
cancellation was received. It retained 24 wheel artifacts under the ignored
work/phase5f-artifacts-evidence/wheelhouse. The first attempt failed Playwright
hash validation; the unchanged retry completed pip's download checks. No artifact
was installed or executed, and clean offline install/extras were not tested.
The downloader is no longer running. No further downloads or package validation
are authorized by this cancelled task. Existing logs and artifact hashes are
retained in cancelled-artifact-manifest.json; no evidence was deleted.

All 153 accepted Phase5E reviewed file hashes remain unchanged. No new source,
test or dependency edits occurred. The historical accepted test result remains
457 total, 454 PASS, 3 SKIP, 0 FAIL/ERROR; it was not rerun for cancellation.
Only this report adds the cancellation note. No Git/VPS/TikTok/private-data action.
STOP at cancellation REPORT. Any future packaging work needs a new approved task.

## Verified blocker

The task requires a clean disposable offline installation and says to STOP on
an offline-install blocker rather than deleting requirements prematurely.
All 153 accepted Phase5E reviewed hashes were verified before checks.

The ordinary local pip wheel cache lists no wheels for websockets, lz4, qrcode,
tzdata or the optional dependency groups. Existing installed packages in the
verification venv are not wheel artifacts for installation into a clean venv.
Its installed setuptools is 65.5.0 and wheel is absent; a suitable offline build
toolchain also needs verification. No network download or broad HTTP-cache
inspection was attempted, and this is not a claim about every possible package
artifact elsewhere on the machine.

A clean disposable venv was created under work/phase5f-evidence/offline-venv.
An explicit local wheelhouse was empty because no matching distributable wheels
were supplied or found in the ordinary wheel-cache inventory. The probe was:

```powershell
.\work\phase5f-evidence\offline-venv\Scripts\python.exe -B -m pip --disable-pip-version-check install --no-index --find-links work/phase5f-evidence/wheelhouse -r requirements.txt
```

Result: exit 1, no matching distribution for
websockets>=15.0.1,<16.0.0. The resolver stopped at the first core dependency;
the probe does not establish independent install results for later dependencies.
No-index, local-only links and disabled version checks prevented remote package
resolution. No TikTok, credential/session/runtime database or browser was accessed.

## Changes and checks not performed

Only this report and ignored local evidence/venv were created. Application source,
tests, entrypoints, dependency files, docs from prior phases, schema and templates
remain unchanged. All four requirements files remain at their accepted Phase5E
paths. No pyproject.toml was created and no legacy requirements were deleted.

Wheel/sdist build, content inspection, clean project installation, extras isolation,
installed module/resource paths, and full Phase5F guarded regression remain
unverified. No PASS is asserted for those acceptance gates. No supported workflow
was removed to work around missing artifacts. No Git, SSH/VPS, systemd, Debian
staging or publishing operation occurred. Identity Contract remains BLOCKED.

## Required next decision

Provide a reviewed local wheelhouse for the selected Python/platform containing
the unchanged core constraints, relevant optional groups/transitive dependencies,
and a PEP 621-capable build toolchain (including wheel), or explicitly approve a
separate dependency-acquisition step. This phase does not authorize downloads.
Debian/Python 3.13 wheels and native fixture acceptance remain separate from this
Windows/Python 3.10 preflight.

After artifacts are available and resumption is approved, implement pyproject
package discovery and verify all required relttk/root/core/signers/plugins/tools
and non-Python resources in wheel/sdist. Preserve repository/private anchors,
optional markers and explicit legacy aliases; do not infer that successful wheel
building alone proves installed runtime compatibility. Requirements removal must
wait until the approved install/import/resource and guarded-suite checks pass.

Evidence: work/phase5f-evidence/before-hashes.json, preservation.json,
offline-install.txt and sanitized-tests.txt. Only the sanitized local package
error/summary is published through C2C. To roll back this report-only checkpoint,
remove only this new report if Owner requests; no source/dependency rollback is
needed. Preserve accepted Phase5E and unrelated/private files.

STOP at REPORT, awaiting Owner resolution of the offline-install blocker.
