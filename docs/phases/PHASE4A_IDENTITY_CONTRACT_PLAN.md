> Historical record: original phase decisions and test counts are retained. They do not certify the current release. Debian 13 is the sole current staging target; Identity Contract remains BLOCKED. Run repository command examples from the repository root. See [current operations](../operations/DEPLOY_DEBIAN.md) and [current security baseline](../evidence/EVIDENCE_PHASE4_SECURITY.md).

# Phase 4A — Authenticated-self identity contract plan

Task: phase4a-identity-contract-plan. Status: PLAN ONLY, pending review.
Date: 2026-10-11. No source changes, live HTTP, credential/session inspection,
runtime database access, SSH, Git or Phase 4B work authorized by this plan.
The current fail-closed verifier remains unchanged. Operational sending remains
blocked. This document specifies evidence gates, not a discovered TikTok schema.

## 1. Local audit and evidence options

Source reviewed: core/api.py, core/self_identity.py, identity_service.py,
qrlogin.py, ws_auth_capture.py, oneshot.py, tests/test_identity_bootstrap.py,
tests/test_circuit_breaker.py and PHASE4A.md. No captured authenticated-self
fixture with documented provenance was found in the reviewed identity tests.

| Existing source | What it demonstrates | Decision |
| --- | --- | --- |
| GET https://www.tiktok.com/messages?lang=es-419 in core/api.py | An existing first-party candidate page; fresh lookup passes only decoded HTML to verifier | Candidate for separately authorized observation, not an accepted identity contract |
| First regex odinId or .uid_cache.json | A candidate numeric identifier without authenticated-self ownership | Never accept for bootstrap or managed sending |
| IM user/profile with caller-supplied user_ids | Data about requested identities | Cannot establish who authenticated the request; cannot validate its own supplied UID |
| QR login sessionid and profile unique_id used as local filename | Credential acquisition and a display/session alias | Alias, cookie presence and login success do not prove canonical IM UID |
| WS 101, frame exchange, ttwid/access_key pairing | Transport/auth-pair viability | No demonstrated self UID contract; no DM probes for identity |
| Correlated server echo | Existing send confirmation using expected sender UID | Not bootstrap evidence: depends on the UID being proven and requires sending |
| Conversation members, settings, device IDs, cookie-derived IDs | Routing or caller/local claims | No fallback, inference or manual UID override |
| Browser-observed first-party self response | Potential request/response context with visible account cross-check | Acquisition option only; browser presence does not make arbitrary profile data self evidence |

Official authentication interfaces could be evaluated in a separately authorized
research task. No official API schema or mapping to the bot's canonical IM UID
has been verified locally. A different identity namespace is not interchangeable
without independently reviewed mapping evidence; adding OAuth now is outside scope.

Current fresh HTTP lookup uses default urllib redirect handling, a manually
constructed Cookie header, unbounded body read and replacement UTF-8 decoding.
It discards status, final URL and response media type. Therefore the future
verifier cannot prove response provenance from its present HTML-only signature.
Post-response origin checking alone would be too late to prevent credential
forwarding during an automatic redirect. No live experiment was performed.

The legacy cached lookup remains used for QR display-name/inbox enrichment.
These paths are not accepted identity evidence. Managed sending explicitly uses
use_cache=False and compares the result with the durable binding before WS/send.

## 2. Proposed minimum contract — approve before implementation

Use one small immutable response-evidence object built by the identity transport,
and one shared verifier for bootstrap and managed send. No general authentication
framework, alternate providers or configurable bypasses are needed.

Transport evidence must include:

- Explicit request method and reviewed exact HTTPS origin/path; sanitized query
  classification, not token-bearing URLs. Start from the existing candidate,
  but do not assume that page contains a valid self contract.
- Valid TLS and default certificate verification; no proxy/certificate bypass.
- Status, actual final origin/path, media type/charset, acquisition time and
  bounded body bytes. Use strict decoding and reject malformed/truncated input.
- Reject every redirect before a follow-up request is dispatched, initially
  including same-origin redirects. Any future redirect exception requires its
  own endpoint review. No credentials go to an alternate host, scheme or port.
- No automatic HTTP retries, login, refresh, cookie persistence, Set-Cookie
  application or browser bootstrap. No caller-provided URL, cache hit or UID.
- Bind acquisition to the selected credential generation in memory. Do not log
  cookies, credential hashes, raw response, QR/WS URLs or session tokens.
- Proposed limits for review: 10-second transport timeout, 2 MiB response body
  cap and 60-second evidence-to-apply lifetime measured monotonically in-process.
  These bound resource use/freshness; they do not establish authenticity by themselves.

Authenticated-self semantics must be demonstrated by reviewed first-party
evidence before writing any parser acceptance rule:

1. A precise response context representing the currently authenticated account,
   rather than an arbitrary profile, conversation member, recommendation or
   caller-supplied UID. Name the exact observed structure and its provenance in
   the later evidence report; no hypothetical JSON keys in this plan.
2. A positive authenticated-state condition belonging to that same context,
   plus exactly one authoritative canonical UID with demonstrated IM namespace.
   Numeric syntax alone is insufficient. A visible account name is a cross-check,
   not a replacement for server self semantics or namespace proof.
3. Reject missing, conflicting, duplicate authoritative records/JSON keys,
   wrong types, logged-out/challenge/error responses and unsupported variants.
   Extra unrelated user IDs need not fail if the reviewed contract unambiguously
   separates them; they must never become fallback candidates.
4. Negative controls must show why the same extraction cannot accept another
   user's profile or an anonymous page. If one candidate cannot demonstrate
   these properties, keep it unsupported rather than combine weak hints.

An evidence object is not a signed server attestation. Trust derives from the
controlled verified transport and reviewed semantics; serialized owner-supplied
objects and test fixtures must not authorize runtime binding.

## 3. Freshness, concurrency and authority

Retain current credential-generation comparison, session/account audit versions,
interactive reason/challenge and atomic bind. Extend the in-memory verified
result with contract version, acquisition monotonic deadline and safe provenance
metadata. Apply must recheck generation, deadline and both circuit versions under
existing locking/transaction rules. Expired or changed previews require a fresh
verification and confirmation; no silent refresh or stale bind.

The same transport/verifier must run for managed sends and compare the fresh UID
to the persisted binding. A mismatch fails before WebSocket or transmission.
Never migrate, reset breaker, enqueue, refund quota, advance rotation or mark
SUCCESS as a consequence of identity verification. Retain existing typed failure
and audit behavior; an evidence-observation tool must be separate from
identity-verify --live because that command may record a circuit failure.

Proposal: keep schema V7. Its existing append-only breaker event evidence_json
can record contract version and sanitized method/origin/context identifiers on
new binds without storing a raw payload or credential-derived hashes. Do not
retroactively certify or rewrite prior bindings. Existing bindings still require
fresh verification on send. A metadata migration is not justified by this plan.
Review exact audit serialization before implementation; if V7 cannot express the
agreed evidence safely, stop and propose a separately approved schema change.

## 4. Separate privacy-safe evidence acquisition proposal

No live acquisition is authorized now. After plan review, obtain separate human
authorization specifying account/session alias, candidate destination, read-only
request scope, maximum attempts, retention and whether a browser is allowed.
Do not request blanket permission to inspect all sessions or capture a full HAR.

Preferred sequence:

1. Offline review the transport and sanitization design first. A new narrowly
   scoped observation tool, if approved later, must neither open runtime SQLite
   nor call identity apply/send. Do not run existing QR/WS capture as a substitute.
2. With separate live-read permission, observe one chosen account's candidate
   response. Stop on redirect, login/challenge, ambiguous identity or unsupported
   media type. No inbox scraping, message-body capture, DM, WS probe or endpoint
   enumeration. The messages page itself may contain private inbox material;
   any permission must explicitly cover that possibility, or choose another
   separately reviewed self endpoint before acquisition.
3. Retain raw material in memory only by default. Extract the minimum relevant
   context locally; never print or send cookies/headers/raw body/full URLs to
   ChatGPT or C2C. Do not store whole-page hashes as public identity proofs.
4. Owner reviews the privacy-sensitive observation locally. Produce a sanitized
   fixture with consistent synthetic UID/name replacements, retained structural
   relationships and an explicit redaction description. Record only safe origin,
   method, status/media type, observation time, contract candidate and sanitized
   fixture checksum in the shareable evidence report. Remove unrelated inbox data.
5. Obtain authenticated/logged-out and another-account controls only within
   explicit permissions. Do not log out or switch the real session automatically;
   separate temporary browser contexts require their own approved scope and
   cannot persist cookies. Synthetic negative tests supplement genuine controls,
   but cannot substitute for demonstrating self semantics.
6. Technical review accepts or rejects the observed contract. Insufficient
   evidence means identity remains BLOCKED. Do not broaden endpoint access
   automatically. Separate offline implementation approval follows acceptance.

Do not commit private captures. Fixtures must not contain usable credentials,
real identifiers, private messages or token-bearing URLs. Windows ACL/secure
erasure cannot be claimed from chmod; any optional private artifact retention
requires an approved private location and disposal policy.

## 5. Proposed implementation file scope (future approval required)

| File | Minimal future change |
| --- | --- |
| core/api.py | Controlled identity-only transport; no redirect/retry; response context/body bounds; preserve unrelated APIs |
| core/self_identity.py | Evidence value type and parser for exactly the subsequently accepted contract |
| identity_service.py | Carry contract provenance/deadline; stale checks and safe public output |
| circuit_breaker.py | Safe evidence_json on new binding events if existing V7 audit supports it |
| oneshot.py | Verify shared fresh identity boundary and reject before WS/marker; avoid duplicate parsing |
| tests/test_identity_bootstrap.py | Positive reviewed-fixture verification; freshness/generation/version/apply tests |
| tests/test_circuit_breaker.py | Fresh transport/identity failures, safe audit and no cache fallback |
| tests/test_self_identity.py (new) | Contract fixtures, ambiguity, duplicate/type and negative-context cases |
| tests/test_identity_transport.py (new) | Redirect/TLS/status/media/body cap/strict decoding/privacy tests |
| tests/fixtures/self_identity/ (new) | Only reviewed sanitized fixtures and acquisition/redaction manifest |
| PHASE4A.md / this document | Evidence decision, limitations and revised readiness status |

An observation utility would be a separately reviewed file/scope, not a hidden
addition to sending or bootstrap. main.py/services.py changes are needed only
if that separately approved tool gets a CLI. No new dependency is proposed.

## 6. Offline acceptance matrix

- Reviewed authenticated-self positive fixture returns precisely its canonical
  UID; anonymous, login/challenge/error, profile-for-other-user, bare odinId,
  guessed login-shaped JSON, conflicting/duplicate records and wrong namespace
  cannot return a verified result.
- Strict numeric string/type validation, duplicate JSON keys, invalid UTF-8,
  truncation, unsupported charset/media type, status failures and body caps.
- Same/cross-origin redirects, downgrade, alternate port, deceptive hostname and
  redirect loops issue zero follow-up requests; no forwarded credentials.
- No certificate bypass/retry/cache/config/cookie/device/alias UID fallback.
- Freshness deadline, monotonic clock anomalies, credential rotation, stale
  session/account versions including OPEN -> RESET ABA, concurrent bind and
  replay. Existing binding conflict cannot be repaired by overwriting history.
- Bootstrap and send consume the same accepted contract; mismatch or rejected
  evidence causes no WS connection, transmission marker or quota charge.
  Existing typed circuit failures may append audit only on explicit execution.
- Secret sentinels absent from public output/audit/errors; no raw payload/hash
  leakage, session write, cookie persistence, implicit DB setup/migration or
  preflight sidecar/permission changes.
- Preserve full guarded offline suite, V7/Worker 3E admission and historical
  rotation/UNKNOWN/consent invariants. Fixtures/mock transport only; zero live I/O.

## 7. Gates and requested decisions

G0: review this PLAN, transport/freshness/resource defaults and evidence options.
G1: separate human authorization for bounded live-read acquisition, including
private data exposure and retention; this plan is not that authorization.
G2: review actual sanitized first-party evidence and namespace/self semantics.
G3: separately approve offline parser/transport implementation and test scope.
G4: guarded regression report and independent review. Tests do not certify live
credential validity or deployment. Any live verification/bind/deployment/send
requires its own applicable authorization after the contract is accepted.

Tradeoff: rejecting redirects and undocumented variants may reject valid TikTok
sessions. This is preferable to asserting identity without evidence; changes
require observation/review, not heuristics. A browser may help provenance
investigation but introduces private-data and platform dependencies, so it is
not proposed as a per-send runtime dependency. Failure to find a defensible
self/IM-namespace contract is a legitimate blocker, not grounds to infer UID.

Work in this task: source audit and this plan document only. No new tests or
regression rerun because no executable code changed. Prior reviewed baseline:
310 tests, 309 PASS, 1 POSIX SKIP, 0 FAIL/ERROR; not a new execution claim.
STOP at PLAN. No implementation or Phase 4B progression.
