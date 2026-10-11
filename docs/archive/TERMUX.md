> RETIRED: Termux/Android is no longer a deployment or test target. This document is retained only as historical material; do not follow its deployment instructions for the current release. Use [Debian 13 operations](../operations/DEPLOY_DEBIAN.md). Identity Contract remains BLOCKED.

# Termux status

Samsung S21 Ultra / Android ARM64 execution has not been verified. The core CLI
uses requirements.txt; lz4 native installation and POSIX behavior need testing
on the device. A Python venv isolates dependencies, not security privileges.

Current Phase 4A authenticated-self verification is deliberately blocked pending
trusted protocol evidence. Do not use this release for real sending yet. See
[PHASE4A.md](../phases/PHASE4A.md) for the blocker and offline readiness commands.

Browser-issued WS auth capture remains Windows-only. Any future transfer must
preserve the exact private session/auth pair and use an explicit private runtime
root; never commit credentials or copy the upstream global key. Token validity
and streak credit are unconfirmed. Credential transfer/live operations require
separate Owner authorization. No on-device automation or scheduler is enabled.
