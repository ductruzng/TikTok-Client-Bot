> Documentation relocated during Phase5A. Commands assume the repository root. Debian 13 is the only current staging target; Identity Contract remains BLOCKED. Historical test counts below retain their original provenance.

# Phase 4D — Checklist bàn giao cho Owner

Task `phase4d-owner-handoff`: **chỉ soạn tài liệu và review offline**.
Phase 4C được Technical Owner nghiệm thu offline; checklist này chưa được thực
hiện trên Debian/VPS/TikTok. Không phải lệnh phê duyệt deploy, migration hay live.
Codex không truy cập SSH, session/database thật, HTTP/WS TikTok hoặc thao tác Git.

## 0. Trạng thái và nguyên tắc trước khi bắt đầu

| Bằng chứng hiện có | Kết luận được phép |
| --- | --- |
| Windows/Python3.10: 380 guarded tests, 377 PASS, 3 SKIP, 0 FAIL/ERROR | Core và artifact đã qua regression offline |
| Windows/Python3.13: 4 guarded backup tests PASS, gồm hai WAL test bị skip trên3.10 | Backup API và no-checkpoint capability đã kiểm chứng trên build này |
| AST7, CLI help4 PASS | Source parse và CLI help hợp lệ |
| Không có actual POSIX/systemd tests | Chưa chứng nhận quyền file/flock/timer/sandbox trên Debian |
| `verify_authenticated_self()` luôn raise CONTRACT_UNVERIFIED | **Identity BLOCKED; không có lệnh nào tự gỡ được** |
| Chưa gửi thật | Chưa biết người nhận nhận tin hoặc TikTok có tính chuỗi |

Chỉ Owner thực hiện các bước máy chủ/online sau khi duyệt từng cổng. Không chạy
toàn bộ tài liệu thành một script. Các tên `ABS_*`, `EXACT_*`, `RELEASE` là
placeholder cần thay bằng giá trị đã kiểm tra; không được chạy nguyên văn.
Giữ một bản kết quả riêng tư trên máy Owner, chỉ gửi báo cáo đã loại dữ liệu nhạy
cảm theo mẫu cuối tài liệu. Không chia sẻ credentials, HAR, nội dung inbox/raw HTML.

**Đang được phép:** đọc checklist, review source và kiểm thử fixture tách biệt.
**Đang bị chặn:** chứng nhận danh tính, gửi thật hoặc bật lịch trên production.
Không dùng UID nhập tay/cache/regex để vượt cổng danh tính.

## 1. Ghi nhận môi trường đích — chưa dùng dữ liệu thật

Owner chọn release, Debian version và kiến trúc cụ thể. Làm trong môi trường
disposable đã được phép, không mount credentials/runtime production. Không có
service/timer tự chạy, không có đường truy cập TikTok trong kiểm thử fixture.

Các lệnh đọc thông tin trên Linux:

```sh
cat /etc/os-release
uname -m
python3 --version
systemd --version
```

Chỉ báo cáo version/architecture, không hostname/IP/user ID thật. Dùng **Python
trong venv đích**, không suy ra từ `python3` hệ thống:

```sh
ABS_PYTHON -B -c 'import sys,sqlite3; from zoneinfo import ZoneInfo; print("python",sys.version.split()[0]); print("sqlite",sqlite3.sqlite_version); print("no_checkpoint",hasattr(sqlite3.Connection,"setconfig") and hasattr(sqlite3,"SQLITE_DBCONFIG_NO_CKPT_ON_CLOSE")); print("timezone",ZoneInfo("Asia/Ho_Chi_Minh").key); c=sqlite3.connect(":memory:"); print("json",c.execute("SELECT json_valid(?)",("{}",)).fetchone()[0]); c.close()'
ABS_PYTHON -m pip check
ABS_PYTHON -B -c 'from importlib.metadata import version; import lz4.block,websockets,qrcode; print({n:version(n) for n in ("websockets","lz4","qrcode","tzdata")}); assert lz4.block.decompress(lz4.block.compress(b"fixture"))==b"fixture"'
```

PASS: Python>=3.10, JSON/TZ/native lz4 hoạt động và dependencies đúng
requirements.txt. WAL backup cần `no_checkpoint=True`; Python3.10 thiếu capability
phải dừng phần backup WAL, không đổi journal mode production để né cổng.
Venv chỉ tổ chức dependency, không phải lớp cách ly bảo mật. Không cần TUI,
Playwright/Chromium Windows cho CLI Debian. Không nâng dependencies tùy ý.

## 2. Quyền file và isolation — chỉ fixture/staging

Owner provision riêng user không đặc quyền `relttk`, release thật dưới
`/opt/relttk/releases/RELEASE`, runtime riêng tư. Đây là thay đổi host cần Owner
quyết định; Codex không thực hiện. Không dùng root để chạy bot.

- Code/release root-owned, không group/world writable; unit trỏ release thật,
  không `current` symlink. Venv dùng `--copies` vì symlink interpreter bị từ chối.
- Runtime/subdirectory thuộc user chạy, 0700; config/session/auth/DB/sidecars0600.
  Không có ancestor writable bởi user khác hoặc symlink.
- Đặt `TIKTOK_RUNTIME_DIR` trước import; mọi route/config/DB dùng path tuyệt đối
  trong runtime. Không giữ fallback sang session/runtime repo cũ.
- Đảm bảo service chỉ ghi runtime, không sửa code. Xem `id`, `stat` và `namei -l`
  cục bộ khi cần; không đưa danh sách đường dẫn/user/session thật vào báo cáo.

PASS: kiểm tra bằng **chính user service** thành công; tests POSIX không còn skip
vì platform. FAIL: chỉ test bằng root, NTFS chmod hoặc có path/symlink bị từ chối.
Không chmod/chown hàng loạt để chữa lỗi chưa hiểu; kiểm tra từng path trước.

## 3. Smoke tests guard trước mọi production data

Trong release copy tách biệt và môi trường không có quyền/network production:

```sh
ABS_PYTHON -B tests/run_offline.py
ABS_PYTHON -B main.py schedule-tick --help
ABS_PYTHON -B main.py operational-status --help
ABS_PYTHON -B main.py ledger-backup --help
ABS_PYTHON -B deploy/render_units.py --help
```

Guard chặn external DNS/connect và session/runtime paths thật. Không tắt guard
để làm test PASS. Ghi tổng PASS/SKIP/FAIL và lý do từng skip; không yêu cầu Linux
phải có đúng skip của Windows. Chọn interpreter đủ WAL capability để chạy hai
test WAL, không đánh dấu skip là đã kiểm chứng.

PASS: không FAIL/ERROR, permission/flock/concurrency và WAL tests thực sự chạy.
Một skip Windows-only renderer refusal là bình thường trên POSIX; skip còn lại
phải được giải thích cụ thể. Network thật hay truy cập dữ liệu thật => STOP.

### Fixture grant để render trên Linux

Đây là synthetic binding **chỉ được dùng trên fixture mới**, không phải phương
pháp bootstrap production. Có thể bỏ bước này nếu đã có fixture tương đương
được review. Không thay `fixture-only` bằng danh tính/người nhận thật.

Trong shell riêng, từ release copy, tạo thư mục mới:

```sh
export FROOT="$(mktemp -d /tmp/relttk-fixture-XXXXXX)"
ABS_PYTHON -B - <<'PY'
import runpy, os, json
from pathlib import Path
# Install guard while original runtime (if set) still remains protected.
runpy.run_path('tests/run_offline.py', run_name='fixture_guard')
os.environ['TIKTOK_RUNTIME_DIR'] = os.environ['FROOT']
import ledger_migrations, circuit_breaker, scheduling
base=Path(os.environ['FROOT']); (base/'state').mkdir(mode=0o700)
db=base/'state'/'fixture.db'; policy=base/'fixture-policy.json'
ledger_migrations.initialize(db)
cfg={'session':'fixture-only','message':'fixture only','targets':[{'conv_id':'fixture-only','conv_short_id':1,'conv_type':1}]}
with os.fdopen(os.open(policy,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w',encoding='utf-8') as f: json.dump(cfg,f)
circuit_breaker.bind_session('111','fixture-only',db_path=db)
review=scheduling.preview(policy,'fixture-only',db_path=db,time='08:00',window_minutes=60,max_wait=300)
gid=scheduling.authorize(review,'isolated synthetic fixture only',db_path=db)
with os.fdopen(os.open(base/'selectors.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f: json.dump({'grant_id':gid,'fingerprint':review['fingerprint']},f)
print('FIXTURE_CREATED_INACTIVE; no credentials; no transmission')
PY
export TIKTOK_RUNTIME_DIR="$FROOT"
mkdir -m 700 "$FROOT/unit-artifacts"
```

Không ACTIVATE fixture grant bằng lịch thật. Mở selectors.json **cục bộ** để lấy
EXACT_ID/EXACT_FP cho render; không cần gửi chúng vào ChatGPT. Fixture có schemaV8
và grant AUTHORIZED/inactive, identity synthetic, không session/auth thật.
Dùng output path và runtime tương ứng FROOT cho renderer trong DEPLOY_DEBIAN.md.
Không tự lưu fixture này vào runtime production hoặc chỉnh history để tái sử dụng.

## 4. Unit validation trước cài đặt

Render artifact bằng `deploy/render_units.py` với Python/operational_entry thật,
DB/policy fixture, selector chính xác và private output directory mới. Renderer
chỉ chấp nhận POSIX, một recipient, daily_budget1, wait<=300, window>=10min,
còn ít nhất10min trước local midnight. Multi-recipient/path injection phải bị từ
chối; không được giảm recipients/budget trong consent cũ để làm render PASS.

Đọc unit artifact và kiểm tra:

- ExecStart gọi operational_entry.py -> schedule-tick với exact ID/fingerprint,
  --execute --yes --operational-output; không gọi CLI legacy/HTTP endpoint khác.
- User/Group relttk, UMask0077, Type=oneshot, Restart=no, TimeoutStart600,
  TimeoutStop90, KillSignalSIGTERM; writable paths chỉ runtime; sandbox đúng mẫu.
- Timer OnCalendar `*-*-* *:*:00 Asia/Ho_Chi_Minh`, Persistent=false,
  AccuracySec1s, RandomizedDelaySec0; Unit trỏ đúng service.
- Không cookie/token/auth URL, shell expansion, `%`/`$` hoặc install/preset hooks.

Lệnh kiểm tra artifact, không load/activate:

```sh
systemd-analyze verify ABS_FIXTURE_SERVICE ABS_FIXTURE_TIMER
systemd-analyze calendar '*-*-* *:*:00 Asia/Ho_Chi_Minh'
```

PASS: directive được **installed systemd** chấp nhận; lịch đúng khi host ở UTC;
artifact không làm service/timer active. Nếu User/Exec/path chưa provision, phải
ghi là staging chưa đủ, không bỏ cảnh báo hoặc sửa unit mất sandbox.
Container không boot systemd chỉ chứng minh parsing, chưa chứng minh timer.

## 5. Identity gate — hiện tại STOP trước production

`core/self_identity.py` hiện luôn từ chối. `identity-verify --live` có thể tạo HTTP
và failure/circuit audit; nó **không phải smoke test offline hoặc lệnh mở khóa**.
Không chạy trên account thật chỉ để thử xem có hết lỗi không.

Trước live cần workstream riêng, review evidence và implementation riêng theo
PHASE4A_IDENTITY_CONTRACT_PLAN.md. Owner cần tối thiểu:

1. Bằng chứng response từ exact first-party origin/path được duyệt, TLS/status/
   media type hợp lệ, không tự theo redirect hoặc chuyển Cookie sang host khác.
2. Context chỉ rõ **currently authenticated self**, không profile người khác,
   members/inbox/odinId đầu tiên hoặc user_ids do caller tự cung cấp.
3. Một UID authoritative và bằng chứng namespace phù hợp IM; numeric syntax,
   cookie tồn tại, QR login, nickname hay WebSocket101 đều chưa đủ.
4. Negative controls anonymous/login/challenge/other-user/conflicting UID và
   payload sai format đều bị từ chối; freshness và credential-generation được
   ràng buộc khi apply và khi gửi.
5. Fixture đã sanitize và provenance report được review; parser/transport được
   triển khai, regression PASS. Không gửi raw HTML/HAR, Cookie headers hoặc token
   vào ChatGPT; inbox capture nếu cần phải có phạm vi/privacy approval riêng.

PASS gate này chỉ khi Technical Owner chấp nhận contract và implementation,
rồi Owner xác minh account thật theo scope online riêng. Hiện **NOT MET**.
UID nhập tay, cache, regex fallback, cookie-derived UID hoặc bind_session trực
tiếp trên production => FAIL/STOP. Không thêm --force hoặc bỏ verifier.
Các bước 6–10 dưới đây là bàn giao cho tương lai, **không được kích hoạt hiện tại**.

## 6. Production storage gate — Owner duyệt riêng

Sau khi các cổng trước đạt, Owner quyết định private runtime/session thật.
Không copy cả workspace, logs hoặc browser profile vào release. Không dùng
config/runtime fixture làm production. Credentials không xuất vào terminal/log.

- Trước mọi migration, source phải được xác định đúng và schema preflight được
  review. Không tự tạo DB vì đường dẫn sai. Không migrate tại tick/service start.
- Giữ DB legacy và mọi request/event/marker. V8 được yêu cầu; dữ liệu không hợp
  lệ dừng apply. Schema migration là phê duyệt riêng, không nằm trong checklist
  execution đã ủy quyền cho Codex.
- Linux policy paths cần reviewed routing/new consent; không sửa JSON snapshot,
  request ID, client ID hoặc history Windows để khớp path mới.
- UNKNOWN chưa giải quyết, circuit mở, expired/held backlog cần Owner xem xét.
  Không xóa ledger, hoàn quota, tự advance rotation hay reset breaker để chạy.

## 7. Lệnh local đọc trạng thái và expected output

Chạy dưới đúng user/runtime, service đã dừng yên; không checkpoint/delete WAL
để làm status hết lỗi. `TIKTOK_RUNTIME_DIR` và mọi ABS_* phải được Owner kiểm tra.

```sh
ABS_PYTHON -B ABS_RELEASE/operational_entry.py operational-status --db ABS_DB --grant-id EXACT_ID --operational-output
ABS_PYTHON -B ABS_RELEASE/main.py runtime-preflight --runtime-dir ABS_RUNTIME --db ABS_DB --config ABS_CONFIG
```

Expected hiện tại: operational-status return2, stateBLOCKED,
reasonIDENTITY_CONTRACT_BLOCKED khi DB quiescent/grant hợp lệ; có usage/counts,
không payload. Nonempty WAL => UNKNOWN/DATABASE_NOT_QUIESCENT; missing/wrong
schema/selector => UNKNOWN/LOCAL_CHECK_FAILED, không tạo DB. Không coi UNKNOWN
là healthy. Runtime-preflight có thể return1 UNVERIFIED hoặc2 BLOCKED; **không có
exit0 chứng nhận live**. Không thêm --check-credentials trong vòng metadata-only.

`schedule-tick` không --execute/--enqueue là local read-only preview:

```sh
ABS_PYTHON -B ABS_RELEASE/operational_entry.py schedule-tick --db ABS_DB --grant-id EXACT_ID --operational-output
```

DUE/NOT_DUE có thể return0 vì cửa sổ thời gian, **không chứng nhận identity/delivery**.
Khi output được lưu log hoặc dùng để giám sát, dùng operational_entry.py như
ví dụ trên: bootstrap chặn stdout/stderr trước khi import CLI. Không coi flag
--operational-output trên main.py trực tiếp là bảo vệ cho lỗi import ban đầu.
MISSED/GRANT_EXPIRED/HELD return2; refusal return3. Default read-only tick không
ghi observed drift thành HELD audit. Modifying tick/claim mới ghi hold bền vững.
Schedule-status, queue-list, request-show, unknown-show có thể lộ nội dung/UID
trong output human; chỉ dùng cục bộ, không đưa thẳng vào journal/báo cáo.
Ledger-preflight đọc SQLite mode=ro, có thể ảnh hưởng sidecar bookkeeping; không
nhầm với quiescent immutable health không tạo sidecar.

## 8. Backup và recovery gate — fixture trước, production sau approval

```sh
ABS_PYTHON -B ABS_RELEASE/operational_entry.py ledger-backup --db ABS_FIXTURE_DB --destination NEW_ABS_FIXTURE_BACKUP --operational-output
```

PASS: BACKUP_COMPLETE/exit0, new backup+private manifest, SHA256 hợp lệ, V8 schema,
integrity/FKs/history+marker counts đúng. Test DELETE và WAL; committed rows có
trong backup, uncommitted rows không có. Competing writer phải busy/refuse trong
timeout, không publish partial. Persistent WAL/main không checkpoint hoặc mất
khi last connection đóng. SHM read bookkeeping có thể thay đổi.

Python thiếu NO_CKPT_ON_CLOSE => exit3 với fixed capability reason trước mutable
open. Không đổi WAL=>DELETE trên runtime để chạy backup. Collision/new-file alias,
unsafe permissions/symlink, disk/publication error => refuse; source history còn
nguyên; incomplete artifact không được dùng làm backup hoàn thành.

Recovery **fixture**: mở bản copy mới, validate V8/integrity/FKs và so sánh request/
audit/grant/worker/rotation histories cùng markers. Không overwrite source. Tạo
marker mới sau backup và chứng minh backup cũ không đủ để rollback runtime.
Production restore không có CLI tự động: isolate/drain writers, giữ original
DB/WAL/journal/SHM evidence, review chronology rồi mới quyết định riêng. Nếu có
khả năng gửi sau thời điểm backup, không thay runtime bằng snapshot cũ.

## 9. Grant, install và activation là các phê duyệt khác nhau

Chỉ sau Identity gate đạt và Owner cho phép online/staging:

1. **Preview** một recipient, message/snapshot, exact Linux route, Settings,
   HCM dates/time/window/daily+totalbudget, max_wait và versions; không gửi.
2. **AUTHORIZE** bằng schedule-authorize --apply trên TTY, lý do không chứa
   credentials và challenge fingerprint. Grant còn inactive; chưa có tin gửi.
3. **Render/review/install** exact grant artifacts. Owner copy units và
   daemon-reload riêng; không enable/start/preset tại installation. Xác nhận
   timer disabled/inactive bằng systemctl cục bộ. Install không ACTIVATE grant.
4. **ACTIVATE** grant bằng riêng CLI confirmation ID/fingerprint/currentversion.
   Thao tác này không gửi ngay, nhưng cấp authority cho tick; phải giữ timer
   stopped trong lúc kiểm tra.
5. **One-shot live** chỉ sau Owner duyệt đúng một người nhận/nội dung/giờ/1marker
   và trạng thái sạch; dùng cùng schedule-tick service/gates, không legacy bypass.
   Không bật timer chỉ để test handshake hoặc identity.
6. **Enable/start timer** là quyết định production riêng sau one-shot/stop/backup
   verification và review kết quả. Không tự gia hạn grant, tăng budget hoặc tạo
   lại requests/manifests. Timer hết authority thì dừng việc gửi.

Mọi thao tác có --execute, --enqueue, --apply, authorize/activate, systemctl
install/enable/start/stop/reboot là **mutation**, không nằm trong local read-only
check. Owner tự thực hiện khi scope được duyệt; Codex không được tự làm theo doc.

## 10. Ma trận thử vận hành — ưu tiên fixture, live chỉ scope riêng

| Scenario | Cách kiểm chứng | PASS / điều kiện dừng |
| --- | --- | --- |
| Lặp tick/cùng key | fixture tick lại occurrence | Cùng request/manifest/snapshot; không marker thứ hai |
| Hai tiến trình/manual tick | fixture concurrency | FIFO/atomic claim giữ quota, không bypass parent |
| Pause/revoke/ABA | fixture thay version giữa preview/claim | Consent cũ bị chặn, reset không làm nó hợp lệ lại |
| SIGTERM trước marker | fake WS/service fixture | Không marker/no quota, không tin mới sau stop |
| SIGTERM sau marker | delayed synthetic echo | Commit correlated echo hoặc UNKNOWN trong bounded handling, không retransmit |
| Forced kill/power loss | process fixture đã marker, restart dưới lock | UNKNOWN giữ marker/quota, không dựng request mới |
| Reboot trong window | disposable systemd host/fixture | Chỉ current-date window; đã truyền không truyền lại; chưa chứng nhận chỉ bằng Windows signal simulation |
| Downtime hết window/qua ngày | clock/timer fixture | MISSED/expiry, không prior-day catch-up |
| Clock skew | clock fixture | Fail closed, không bỏ cooldown/window |
| UNKNOWN | fixture rồi đọc history | Chặn hội thoại xuyên ngày; resolution không SUCCESS/refund/rotation/reset |
| Expiry giữa marker/echo | fake transport | Bounded completion, không retransmit vì hết hạn |
| Lịch/current workload | actual isolated systemd | Parsing/sandbox/cadence/drain đúng; quá watchdog giữ history, dừng production approval |
| Journald | fixture arbitrary secrets/native stderr/import error | Không token/URL/UID/message/path/raw trace; missing safe envelope không healthy |
| Recipient/streak | Owner live với scope1 tin sau identity gate | Ghi riêng server echo, recipient receipt và streak UI; không đánh đồng |

Không reboot/kill production hoặc cố ý gây UNKNOWN bằng gửi thật chỉ để thỏa
ma trận; dùng fixture. SUCCESS chỉ correlated server echo, không phải người nhận
đã đọc hoặc chuỗi tăng. Ngưỡng rate limit là policy nội bộ, không bảo đảm tránh
TikTok phát hiện bot. API nội bộ không chính thức, hợp đồng có thể đổi.

## 11. Immediate STOP và rollback không phá dữ liệu

STOP nếu có secret trong log, identity ambiguous/BLOCKED, gửi sai recipient/
snapshot, duplicate marker/message, quota bypass, schema/path drift, source
history mất, UNKNOWN hoặc watchdog/live timing không phù hợp. Không bấm retry.

Owner: stop/disable timer trước, gửi SIGTERM để drain service trong grace90s;
nếu buộc kill, coi marker liên quan là chưa xác định. Giữ DB và sidecars, không
unlink run.lock hoặc force-unlock khi chưa biết tiến trình giữ lock. Không chạy
SQLite sửa rows hoặc restore snapshot để xóa lỗi. Audit quyết định/lý do riêng tư.
Raw log có secret thì hạn chế truy cập và review credential exposure riêng;
không dán log hoặc tự đổi credentials qua Codex.

Rollback code: giữ V8 DB, chọn reviewed V8-compatible release cùng safety gates,
kiểm tra fixture/readiness/unit lại. Release preV8 hoặc restore cũ mất marker =>
FAIL. Không tự downgrade schema, reset circuits, activate grant hay restart timer.
Quá trình recovery uncertain => runtime tiếp tục non-operational.

## 12. Mẫu báo cáo đã sanitize cho Owner

```text
PHASE4D OWNER REPORT (không kèm raw logs/credentials)
Scope approved: [fixture-only / host-staging / separately-approved live]
Release label: [alias]; Debian / architecture / Python / SQLite / systemd versions:
Isolation: [credential-free fixture; network guard result]
POSIX permissions / flock / dependency tests: [PASS/FAIL/NOT RUN]
Guarded suite: [total, PASS, SKIP + reasons, FAIL/ERROR, duration]
WAL no-checkpoint capability / persistent-WAL backup / restore validation:
Unit parse / calendar / sandbox / actual lifecycle: [separate results]
Identity contract review + implementation evidence: [approved reference / BLOCKED]
Production storage / migration approval: [reference / NOT AUTHORIZED]
Grant preview / AUTHORIZE / install / ACTIVATE / timer start: [each separately]
Signal / crash / reboot / missed window / expiry / UNKNOWN: [fixture evidence]
Live scope (only if separately approved): [one-recipient alias, date, marker count]
Server echo / recipient receipt / streak credit: [each PASS/FAIL/UNVERIFIED]
Logs privacy / safe-envelope freshness: [PASS/FAIL]
History preserved / rollback performed / unresolved holds:
STOP conditions observed and Owner decisions:
Next requested approval: [one concrete action]
```

Không đưa UID/conversation/session/client/key/QR/WS URL, Cookie/token, raw
request/response, tin nhắn, profile/HAR hay full file paths vào report. Dùng alias
và fixed reason codes. Evidence nhạy cảm giữ riêng trên máy Owner; fixture logs
đã sanitize có thể được review riêng. Một cổng NOT RUN/BLOCKED không được báo PASS.

Tài liệu được đối chiếu source hiện có và DEPLOY_DEBIAN.md; không chạy thêm tests,
không xác minh Linux hoặc TikTok trong task này. Chỉ tạo file checklist.
**STOP PLAN/REPORT — chờ Technical Owner review.**
