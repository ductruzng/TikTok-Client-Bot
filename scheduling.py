"""Explicit bounded daily authority. No daemon, credential I/O or new sender."""
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re
import secrets
import sqlite3

import circuit_breaker as breaker
import ledger
import ledger_migrations as migrations
import ledger_requests as requests
import queue_service as queue
import readiness
import rotation
import runtime_paths as paths
import worker


class ScheduleHeld(worker.WorkerHeld):
    def __init__(self, code, grant_id=None):
        self.grant_id = grant_id
        super().__init__(code, 'Recurring authority held; review required')


@contextmanager
def readonly(db_path):
    paths.contained(db_path, private=True)
    before = readiness._stamp(Path(db_path))
    with closing(readiness.open_quiescent(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute('BEGIN')
        migrations.validate_schema(conn)
        yield conn
    if readiness._stamp(Path(db_path)) != before:
        raise ScheduleHeld('DATABASE_CHANGED')


def daily_key(uid, conv_id, day):
    return 'automation:v1:' + rotation.fingerprint([uid, conv_id, day])


def _integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name} must be an integer in [{low}, {high}]')
    return value


def _midnight(day):
    return int(datetime.combine(day, datetime.min.time(), ledger.TZ_HO_CHI_MINH).timestamp()*1000)


def _consent(conn, config, reference, schedule_id, *, time='08:00', valid_from=None,
             valid_through=None, window_minutes=60, daily_budget=None, total_budget=None, max_wait=300):
    cfg = queue.normalize_policy(config)
    uid = queue.binding(conn, cfg['session'])
    breaker.check(conn, uid, cfg['session'])
    if not isinstance(schedule_id, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', schedule_id):
        raise ValueError('schedule_id requires 1-64 ASCII name characters')
    if not isinstance(time, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', time):
        raise ValueError('Time must be HH:MM')
    today = requests.local_time(requests.utc_now_ms()).date()
    first = date.fromisoformat(valid_from) if valid_from else today
    last = date.fromisoformat(valid_through) if valid_through else first+timedelta(days=6)
    days = (last-first).days+1
    if first < today or not 1 <= days <= 31:
        raise ValueError('Consent requires 1-31 future/current local dates')
    count = len(cfg['targets'])
    _integer(count, 1, 100, 'recipient count')
    window_minutes = _integer(window_minutes, 1, 1440, 'window_minutes')
    max_wait = _integer(max_wait, 0, 86400, 'max_wait')
    daily_budget = _integer(count if daily_budget is None else daily_budget, 1, count, 'daily_budget')
    total_budget = _integer(count*days if total_budget is None else total_budget, 1, count*days, 'total_budget')
    return dict(schedule_id=schedule_id, uid=uid, session=cfg['session'],
        policy_reference=str(paths.contained(reference, private=True)),
        policy_fingerprint=queue.policy_fingerprint(cfg), policy=cfg,
        circuits=worker._circuits(conn, uid, cfg['session']), timezone='Asia/Ho_Chi_Minh',
        time=time, valid_from=first.isoformat(), valid_through=last.isoformat(),
        start_ms=_midnight(first), end_ms=_midnight(last+timedelta(days=1)),
        window_minutes=window_minutes, daily_budget=daily_budget, total_budget=total_budget, max_wait=max_wait)


def preview(config_path, schedule_id, *, db_path, **bounds):
    cfg = queue.read_policy(config_path)
    with readonly(db_path) as conn:
        c = _consent(conn, cfg, config_path, schedule_id, **bounds)
        return dict(consent=c, fingerprint=rotation.fingerprint(c), enabled=False,
                    identity='IDENTITY_CONTRACT_BLOCKED', selection='at enqueue; catalog shown, no random draw')


def _event(conn, gid, kind, reason):
    requests.require_reason(reason)
    last = conn.execute('SELECT version,at_ms FROM recurring_events WHERE grant_id=? ORDER BY version DESC LIMIT 1', (gid,)).fetchone()
    instant = requests.utc_now_ms()
    if last and instant < last['at_ms']:
        raise ScheduleHeld('CLOCK_SKEW', gid)
    conn.execute('INSERT INTO recurring_events(grant_id,version,event_type,at_ms,details_json) VALUES(?,?,?,?,?)',
                 (gid, last['version']+1 if last else 1, kind, instant, rotation.encode({'reason': reason})))


def _load(conn, gid):
    row = conn.execute('SELECT * FROM recurring_grants WHERE grant_id=?', (gid,)).fetchone()
    if not row:
        raise ScheduleHeld('GRANT_MISSING', gid)
    c = json.loads(row['consent_json'])
    if rotation.fingerprint(c) != row['fingerprint'] or c['schedule_id'] != row['schedule_id']:
        raise ScheduleHeld('GRANT_INVALID', gid)
    e = conn.execute('SELECT * FROM recurring_events WHERE grant_id=? ORDER BY version DESC LIMIT 1', (gid,)).fetchone()
    if not e:
        raise ScheduleHeld('GRANT_INVALID', gid)
    return c, row['fingerprint'], dict(e)


def _budgets(conn, c, day):
    ids = [t['conv_id'] for t in c['policy']['targets']]
    marks = conn.execute(f'''SELECT date FROM send_requests WHERE canonical_uid=? AND conv_id IN ({','.join('?' for _ in ids)})
        AND transmitted=1 AND transmission_started_at_ms>=? AND transmission_started_at_ms<?''',
        (c['uid'], *ids, c['start_ms'], c['end_ms'])).fetchall()
    return dict(daily_used=sum(r['date'] == day for r in marks), total_used=len(marks),
                daily_limit=c['daily_budget'], total_limit=c['total_budget'])


def _state(conn, gid):
    c, fp, e = _load(conn, gid)
    day = requests.local_time(requests.utc_now_ms()).date().isoformat()
    return dict(grant_id=gid, fingerprint=fp, consent=c, event=e, usage=_budgets(conn, c, day),
                identity='IDENTITY_CONTRACT_BLOCKED')


def status(gid, *, db_path):
    with readonly(db_path) as conn:
        result = _state(conn, gid)
        result['history'] = [dict(r) for r in conn.execute('SELECT * FROM recurring_events WHERE grant_id=? ORDER BY version', (gid,))]
        result['occurrences'] = [dict(r) for r in conn.execute('SELECT * FROM daily_occurrences WHERE grant_id=? ORDER BY local_date', (gid,))]
        return result


def authorize(review, reason, *, db_path):
    requests.require_reason(reason)
    c = review['consent']
    cfg = queue.read_policy(c['policy_reference'])
    with requests.transaction(db_path) as conn:
        actual = _consent(conn, cfg, c['policy_reference'], c['schedule_id'],
            **{k:c[k] for k in ('time','valid_from','valid_through','window_minutes','daily_budget','total_budget','max_wait')})
        if actual != c or rotation.fingerprint(c) != review['fingerprint']:
            raise ScheduleHeld('STALE_PREVIEW')
        gid = secrets.token_hex(16)
        conn.execute('INSERT INTO recurring_grants VALUES(?,?,?,?,?)',
            (gid, c['schedule_id'], review['fingerprint'], rotation.encode(c), requests.utc_now_ms()))
        _event(conn, gid, 'AUTHORIZED', reason)
        return gid


def _check_config(conn, gid, c):
    if queue.binding(conn, c['session']) != c['uid']:
        raise ScheduleHeld('IDENTITY_CHANGED', gid)
    try:
        breaker.check(conn, c['uid'], c['session'])
        if worker._circuits(conn, c['uid'], c['session']) != c['circuits']:
            raise ScheduleHeld('CIRCUIT_CHANGED', gid)
    except breaker.CircuitOpen:
        raise ScheduleHeld('CIRCUIT_CHANGED', gid) from None
    try:
        cfg = queue.read_policy(c['policy_reference'])
        if queue.policy_fingerprint(cfg) != c['policy_fingerprint']:
            raise ValueError()
    except (ValueError, OSError):
        raise ScheduleHeld('POLICY_CHANGED', gid) from None
    from unknown_resolution import unresolved_sql
    for target in c['policy']['targets']:
        if conn.execute('SELECT 1 FROM send_requests r WHERE r.canonical_uid=? AND r.conv_id=? AND '+unresolved_sql('r'),
                        (c['uid'], target['conv_id'])).fetchone():
            raise ScheduleHeld('UNKNOWN_BLOCKED', gid)
    return cfg


def change(gid, expected, kind, reason, *, db_path):
    if kind not in ('ACTIVATED','PAUSED','REVOKED'):
        raise ValueError('Unsupported grant action')
    requests.require_reason(reason)
    with requests.transaction(db_path) as conn:
        if _state(conn, gid) != {k:expected[k] for k in _state(conn,gid)}:
            raise ScheduleHeld('STALE_PREVIEW', gid)
        c, _, e = _load(conn,gid)
        allowed = {'ACTIVATED': ('AUTHORIZED',), 'PAUSED': ('ACTIVATED',), 'REVOKED': ('AUTHORIZED','ACTIVATED','PAUSED','HELD')}
        if e['event_type'] not in allowed[kind]:
            raise ScheduleHeld('GRANT_CLOSED', gid)
        if kind == 'ACTIVATED':
            _check_config(conn, gid, c)
            if requests.utc_now_ms() >= c['end_ms']:
                raise ScheduleHeld('GRANT_EXPIRED',gid)
            scope = {t['conv_id'] for t in c['policy']['targets']}
            for other in conn.execute('SELECT grant_id FROM recurring_grants WHERE grant_id!=?', (gid,)).fetchall():
                oc, _, oe = _load(conn,other[0])
                if oe['event_type'] == 'ACTIVATED' and oc['uid'] == c['uid'] and max(oc['start_ms'],c['start_ms']) < min(oc['end_ms'],c['end_ms']) and scope.intersection(t['conv_id'] for t in oc['policy']['targets']):
                    raise ScheduleHeld('OVERLAPPING_GRANT',gid)
        _event(conn,gid,kind,reason)


def _window(c, instant):
    local = requests.local_time(instant)
    hour, minute = map(int,c['time'].split(':'))
    start = int(local.replace(hour=hour,minute=minute,second=0,microsecond=0).timestamp()*1000)
    end = min(start+c['window_minutes']*60000, _midnight(local.date()+timedelta(days=1)), c['end_ms'])
    return local.date().isoformat(), start, end


def _gate(conn, gid, *, version=None, occurrence=None, claim=False):
    c, fp, e = _load(conn,gid)
    instant = requests.utc_now_ms()
    if instant < e['at_ms']:
        raise ScheduleHeld('CLOCK_SKEW',gid)
    if e['event_type'] != 'ACTIVATED' or (version is not None and e['version'] != version):
        raise ScheduleHeld('GRANT_INACTIVE',gid)
    cfg = _check_config(conn,gid,c)
    if instant < c['start_ms']:
        raise ScheduleHeld('NOT_DUE',gid)
    if instant >= c['end_ms']:
        raise ScheduleHeld('GRANT_EXPIRED',gid)
    day,start,end = _window(c,instant)
    if occurrence is not None:
        if day != occurrence['local_date'] or start != occurrence['start_ms'] or end != occurrence['end_ms']:
            raise ScheduleHeld('OCCURRENCE_EXPIRED',gid)
    if instant < start:
        raise ScheduleHeld('NOT_DUE',gid)
    if instant >= end:
        raise ScheduleHeld('MISSED',gid)
    used = _budgets(conn,c,day)
    if used['daily_used'] > c['daily_budget'] or used['total_used'] > c['total_budget'] or (claim and (used['daily_used'] >= c['daily_budget'] or used['total_used'] >= c['total_budget'])):
        raise ScheduleHeld('RECURRING_BUDGET',gid)
    return c,fp,e,cfg,day,start,end


def record_hold(exc, *, db_path):
    if not isinstance(exc, ScheduleHeld) or not exc.grant_id or exc.code not in ('POLICY_CHANGED','CIRCUIT_CHANGED','IDENTITY_CHANGED','UNKNOWN_BLOCKED','CLOCK_SKEW','PARENT_LINK_INVALID','OCCURRENCE_INVALID'):
        return
    with requests.transaction(db_path) as conn:
        _,_,e = _load(conn,exc.grant_id)
        if e['event_type'] == 'ACTIVATED':
            # Preserve observed invalidation even if the policy is subsequently restored.
            instant = max(requests.utc_now_ms(),e['at_ms'])
            conn.execute('INSERT INTO recurring_events(grant_id,version,event_type,at_ms,details_json) VALUES(?,?,?,?,?)',
                (exc.grant_id,e['version']+1,'HELD',instant,rotation.encode({'reason':exc.code})))


def _occurrence(conn, row):
    d = dict(row)
    expected = {k:d[k] for k in ('canonical_uid','schedule_id','local_date','grant_id','grant_version','run_id','start_ms','end_ms')}
    if rotation.fingerprint(expected) != d['fingerprint']:
        raise ScheduleHeld('OCCURRENCE_INVALID',d['grant_id'])
    consent = worker._load(conn,d['run_id'])
    members = conn.execute('SELECT request_id FROM daily_occurrence_requests WHERE occurrence_id=? ORDER BY ordinal', (d['occurrence_id'],)).fetchall()
    if [r[0] for r in members] != [m['request_id'] for m in consent['members']]:
        raise ScheduleHeld('PARENT_LINK_INVALID',d['grant_id'])
    c,_,_ = _load(conn,d['grant_id'])
    if (consent['uid'] != c['uid'] or consent['session'] != c['session'] or consent['circuits'] != c['circuits']
        or consent['expires_at_ms'] != d['end_ms'] or consent['max_jobs'] > c['daily_budget']
        or consent['max_wait'] != c['max_wait']):
        raise ScheduleHeld('PARENT_LINK_INVALID',d['grant_id'])
    for member in consent['members']:
        r = conn.execute('SELECT * FROM send_requests WHERE request_id=?', (member['request_id'],)).fetchone()
        if worker._expected(conn,r) != member or r['canonical_uid'] != c['uid'] or daily_key(c['uid'],r['conv_id'],d['local_date']) != r['idempotency_key']:
            raise ScheduleHeld('PARENT_LINK_INVALID',d['grant_id'])
        route=member['route']
        payload=json.loads(r['payload_json'])
        if (route['session_name'] != c['session'] or route['policy_reference'] != c['policy_reference']
            or route['policy_fingerprint'] != c['policy_fingerprint'] or payload['target'] not in c['policy']['targets']):
            raise ScheduleHeld('PARENT_LINK_INVALID',d['grant_id'])
        if 'rotation' in c['policy']:
            snapshot=json.loads(r['snapshot_json'])
            if snapshot['catalog'] != rotation.catalog(c['policy']) or payload['message'] != snapshot['template']['text']:
                raise ScheduleHeld('PARENT_LINK_INVALID',d['grant_id'])
        if 'rotation' not in c['policy'] and payload['message'] != c['policy']['message']:
            raise ScheduleHeld('PARENT_LINK_INVALID',d['grant_id'])
    return d


def check_parent(conn, *, row=None, run_id=None, claim=False):
    if row is not None:
        found = conn.execute('SELECT d.* FROM daily_occurrences d JOIN daily_occurrence_requests m USING(occurrence_id) WHERE m.request_id=?', (row['request_id'],)).fetchone()
        if not found:
            if row['idempotency_key'].startswith('automation:v1:'):
                raise ScheduleHeld('PARENT_LINK_MISSING')
            return
    else:
        found = conn.execute('SELECT * FROM daily_occurrences WHERE run_id=?', (run_id,)).fetchone()
        if not found:
            c = worker._load(conn,run_id)
            if any(conn.execute('SELECT 1 FROM daily_occurrence_requests WHERE request_id=?',(m['request_id'],)).fetchone() for m in c['members']):
                # Finite approval cannot override a daily request's original parent.
                for m in c['members']:
                    r = conn.execute('SELECT * FROM send_requests WHERE request_id=?',(m['request_id'],)).fetchone()
                    check_parent(conn,row=r,claim=claim)
            approved = conn.execute("SELECT details_json FROM worker_events WHERE run_id=? AND event_type='APPROVED' ORDER BY event_id LIMIT 1",(run_id,)).fetchone()
            if approved and json.loads(approved[0]).get('recurring_parent'):
                raise ScheduleHeld('PARENT_LINK_MISSING')
            return
    d = _occurrence(conn,found)
    _gate(conn,d['grant_id'],version=d['grant_version'],occurrence=d,claim=claim)


def _tick_preview(conn,gid):
    try:
        c,fp,e,cfg,day,start,end = _gate(conn,gid)
        existing = conn.execute('SELECT * FROM daily_occurrences WHERE canonical_uid=? AND schedule_id=? AND local_date=?',(c['uid'],c['schedule_id'],day)).fetchone()
        if existing:
            d = _occurrence(conn,existing)
            check_parent(conn,run_id=d['run_id'])
            run = worker._load(conn,d['run_id'])
            last = conn.execute('SELECT event_type FROM worker_events WHERE run_id=? ORDER BY event_id DESC LIMIT 1',(d['run_id'],)).fetchone()[0]
            return dict(state=last,occurrence=d,run_fingerprint=rotation.fingerprint(run))
        return dict(state='DUE',local_date=day,start_ms=start,end_ms=end,grant_version=e['version'],
                    grant_fingerprint=fp,usage=_budgets(conn,c,day),policy=cfg)
    except ScheduleHeld as exc:
        result=dict(state='HELD',reason=exc.code,grant_id=gid)
        if exc.code in ('NOT_DUE','MISSED','GRANT_EXPIRED','GRANT_INACTIVE'):
            result['state']=exc.code
        c,_,_= _load(conn,gid)
        result['usage']=_budgets(conn,c,requests.local_time(requests.utc_now_ms()).date().isoformat())
        _,start,end = _window(c,requests.utc_now_ms())
        result['retry_at_ms']=start if exc.code=='NOT_DUE' and start>=requests.utc_now_ms() else None
        return result


def tick_preview(gid, *, db_path):
    with readonly(db_path) as conn:
        return _tick_preview(conn,gid)


def enqueue(gid, fingerprint, *, db_path):
    try:
        with requests.transaction(db_path) as conn:
            c,fp,e,cfg,day,start,end = _gate(conn,gid)
            if fingerprint != fp:
                raise ScheduleHeld('GRANT_FINGERPRINT',gid)
            prior = conn.execute('SELECT * FROM daily_occurrences WHERE canonical_uid=? AND schedule_id=? AND local_date=?',(c['uid'],c['schedule_id'],day)).fetchone()
            if prior:
                d = _occurrence(conn,prior)
                check_parent(conn,run_id=d['run_id'])
                return dict(state='EXISTING',occurrence=d,run_fingerprint=rotation.fingerprint(worker._load(conn,d['run_id'])))
            _gate(conn,gid,claim=True)
            rows=[]
            for target in cfg['targets']:
                if conn.execute("SELECT 1 FROM send_requests WHERE canonical_uid=? AND conv_id=? AND status IN ('queued','pending')",(c['uid'],target['conv_id'])).fetchone():
                    raise ScheduleHeld('OLDER_QUEUED_REQUEST',gid)
                row,created = requests._create_request(conn,c['uid'],target['conv_id'],daily_key(c['uid'],target['conv_id'],day),
                    {'target':target,'message':cfg.get('message','')},rotation_config=cfg if 'rotation' in cfg else None,
                    session_name=c['session'],policy_reference=c['policy_reference'],policy_config=cfg)
                if not created:
                    raise ScheduleHeld('DAILY_KEY_EXISTS',gid)
                rows.append(row)
            review = worker._preview(conn,c['session'],[r['request_id'] for r in rows], min(len(rows),c['daily_budget']),c['max_wait'],end)
            oid=secrets.token_hex(16)
            run_id=worker._insert_authorization(conn,review,'Derived from explicitly activated recurring grant',parent={'grant_id':gid,'occurrence_id':oid,'version':e['version']})
            details=dict(canonical_uid=c['uid'],schedule_id=c['schedule_id'],local_date=day,grant_id=gid,grant_version=e['version'],run_id=run_id,start_ms=start,end_ms=end)
            conn.execute('INSERT INTO daily_occurrences VALUES(?,?,?,?,?,?,?,?,?,?)',
                (oid,c['uid'],c['schedule_id'],day,gid,e['version'],run_id,rotation.fingerprint(details),start,end))
            for ordinal,m in enumerate(review['consent']['members']):
                conn.execute('INSERT INTO daily_occurrence_requests VALUES(?,?,?)',(oid,m['request_id'],ordinal))
            d=dict(occurrence_id=oid,**details,fingerprint=rotation.fingerprint(details))
            return dict(state='ENQUEUED',occurrence=d,run_fingerprint=review['fingerprint'])
    except ScheduleHeld as exc:
        record_hold(exc,db_path=db_path)
        raise


async def tick(gid, fingerprint=None, *, db_path, execute=False, enqueue_only=False, stop_event=None):
    if not execute and not enqueue_only:
        return tick_preview(gid,db_path=db_path)
    if not fingerprint:
        raise ValueError('Exact recurring grant fingerprint required')
    result=enqueue(gid,fingerprint,db_path=db_path)
    if execute:
        d=result['occurrence']
        result['worker']=await worker.run(d['run_id'],result['run_fingerprint'],db_path=db_path,stop_event=stop_event)
    return result
