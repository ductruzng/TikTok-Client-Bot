"""Disposable schedule fixtures and synthetic transport only; no live authentication."""
import asyncio
from contextlib import closing, redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta
import io
import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import circuit_breaker as cb
import ledger
import ledger_migrations as migrations
import ledger_requests as requests
import main
import oneshot
import rotation
import scheduling as schedule
import services
import worker


def competing_tick(db,gid,fp,clock,barrier,out):
    with patch.object(requests,'utc_now_ms',return_value=clock):
        barrier.wait(timeout=15)
        try:
            result=schedule.enqueue(gid,fp,db_path=db)
            out.put(result['occurrence']['run_id'])
        except Exception as exc: out.put(type(exc).__name__)


def competing_claim(db,rid,cfg,reference,clock,barrier,out):
    with patch.object(requests,'utc_now_ms',return_value=clock):
        barrier.wait(timeout=15)
        try:
            result=requests.start_transmission(rid,db_path=db,session_name=cfg['session'],policy_config=cfg,
                policy_reference=reference,**requests.settings_from_config(cfg))
            if result:
                r=requests.get_request(rid,db_path=db)
                requests.finish(r['canonical_uid'],r['conv_id'],r['date'],r['client_msg_id'],db_path=db,
                    status='confirmed',reason='fixture',server_id='1',result_date=r['date'])
            out.put(bool(result))
        except ledger.LedgerError: out.put(False)


class ScheduleTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.db=str(Path(self.tmp.name)/'ledger.db'); self.policy=str(Path(self.tmp.name)/'policy.json')
        migrations.initialize(self.db)
        self.cfg=dict(session='fixture',message='precise text',targets=[dict(conv_id=c,conv_short_id=1,conv_type=1) for c in ('a','b')],
            allow_repeat_same_day=True,max_sends_per_conversation_per_day=10,min_send_interval_seconds=0,max_sends_per_window=100)
        self.save()
        self.clock=int(datetime(2026,10,11,8,0,tzinfo=ledger.TZ_HO_CHI_MINH).timestamp()*1000)
        self.addCleanup(patch.stopall)
        patch.object(requests,'utc_now_ms',side_effect=lambda:self.clock).start()
        patch.object(cb,'now_ms',side_effect=lambda:self.clock).start()
        cb.bind_session('111','fixture',db_path=self.db)

    def save(self):
        Path(self.policy).write_text(json.dumps(self.cfg),encoding='utf-8'); os.chmod(self.policy,0o600)

    def review(self,**bounds):
        return schedule.preview(self.policy,'daily',db_path=self.db,**bounds)

    def grant(self,active=True,**bounds):
        review=self.review(**bounds)
        gid=schedule.authorize(review,'fixture owner',db_path=self.db)
        if active: schedule.change(gid,schedule.status(gid,db_path=self.db),'ACTIVATED','fixture owner',db_path=self.db)
        return gid,review['fingerprint']

    def sql(self,query,args=()):
        with closing(sqlite3.connect(self.db)) as conn: return conn.execute(query,args).fetchall()

    def batch(self,**bounds):
        gid,fp=self.grant(**bounds)
        return gid,fp,schedule.enqueue(gid,fp,db_path=self.db)

    def rows(self):
        return [requests.get_request(r[0],db_path=self.db) for r in self.sql('SELECT request_id FROM send_requests ORDER BY rowid')]

    def claim(self,row,context=None):
        return requests.start_transmission(row['request_id'],db_path=self.db,session_name='fixture',
            policy_reference=self.policy,policy_config=self.cfg,rotation_config=self.cfg,worker_context=context,
            **requests.settings_from_config(self.cfg))

    def finish(self,row,status='confirmed'):
        r=requests.get_request(row['request_id'],db_path=self.db)
        requests.finish('111',r['conv_id'],r['date'],r['client_msg_id'],db_path=self.db,status=status,
            reason='fixture',server_id='1' if status=='confirmed' else None,result_date=r['date'],
            failure=cb.Failure('UNKNOWN','echo','fixture') if status=='failed_unknown' else None)

    def manual(self,conv='a'):
        target=next(t for t in self.cfg['targets'] if t['conv_id']==conv)
        return requests.create_request('111',conv,'manual-'+conv,{'target':target,'message':self.cfg['message']},
            db_path=self.db,session_name='fixture',policy_reference=self.policy,policy_config=self.cfg)[0]

    def test_default_bounds_and_preview_no_side_effects(self):
        before={p.name:(p.read_bytes(),p.stat().st_mtime_ns,p.stat().st_mode) for p in Path(self.tmp.name).iterdir()}
        with patch.object(rotation,'choose',side_effect=AssertionError('RNG')),patch.object(oneshot,'load_session',side_effect=AssertionError('credentials')):
            r=self.review()
        after={p.name:(p.read_bytes(),p.stat().st_mtime_ns,p.stat().st_mode) for p in Path(self.tmp.name).iterdir()}
        self.assertEqual(before,after); self.assertFalse(r['enabled'])
        self.assertEqual(r['consent']['valid_through'],'2026-10-17'); self.assertEqual(r['consent']['window_minutes'],60)
        self.assertEqual(r['identity'],'IDENTITY_CONTRACT_BLOCKED')

    def test_invalid_bounds(self):
        for b in ({'time':'25:00'},{'window_minutes':0},{'window_minutes':True},{'daily_budget':3},{'total_budget':15},{'max_wait':-1},{'valid_from':'2026-10-10'},{'valid_through':'2026-11-11'}):
            with self.subTest(b=b),self.assertRaises(ValueError): self.review(**b)

    def test_authorize_inactive_activate_separate(self):
        gid,fp=self.grant(False)
        self.assertEqual(schedule.tick_preview(gid,db_path=self.db)['state'],'GRANT_INACTIVE')
        with self.assertRaises(schedule.ScheduleHeld): schedule.enqueue(gid,fp,db_path=self.db)
        self.assertFalse(self.rows())

    def test_activation_stale_pause_no_reactivation_and_revoke(self):
        gid,fp=self.grant(False); old=schedule.status(gid,db_path=self.db)
        schedule.change(gid,old,'ACTIVATED','fixture',db_path=self.db)
        with self.assertRaises(schedule.ScheduleHeld): schedule.change(gid,old,'REVOKED','fixture',db_path=self.db)
        schedule.change(gid,schedule.status(gid,db_path=self.db),'PAUSED','fixture',db_path=self.db)
        with self.assertRaises(schedule.ScheduleHeld): schedule.change(gid,schedule.status(gid,db_path=self.db),'ACTIVATED','fixture',db_path=self.db)
        schedule.change(gid,schedule.status(gid,db_path=self.db),'REVOKED','fixture',db_path=self.db)
        self.assertEqual(schedule.status(gid,db_path=self.db)['event']['event_type'],'REVOKED')

    def test_overlapping_active_grant_refused(self):
        self.grant(); gid,_=self.grant(False)
        with self.assertRaises(schedule.ScheduleHeld): schedule.change(gid,schedule.status(gid,db_path=self.db),'ACTIVATED','fixture',db_path=self.db)

    def test_daily_enqueue_replay_same_ids_no_rotation_redraw(self):
        self.cfg.pop('message'); self.cfg.update(campaign_id='c',rotation={'mode':'random_no_immediate_repeat','templates':[{'id':'x','text':'A'},{'id':'y','text':'B'}]});self.save()
        gid,fp,out=self.batch()
        before=self.sql('SELECT * FROM send_requests'); run=out['occurrence']['run_id']
        with patch.object(rotation,'choose',side_effect=AssertionError('redraw')):
            replay=schedule.enqueue(gid,fp,db_path=self.db)
        self.assertEqual(replay['occurrence']['run_id'],run); self.assertEqual(before,self.sql('SELECT * FROM send_requests'))

    def test_atomic_batch_failure_and_rerun(self):
        self.cfg.pop('message');self.cfg.update(campaign_id='c',rotation={'templates':[{'id':'x','text':'A'}]});self.save()
        gid,fp=self.grant(); original=requests._create_request
        def fail(conn,uid,conv,*args,**kw):
            if conv=='b': raise RuntimeError('fixture crash')
            return original(conn,uid,conv,*args,**kw)
        with patch.object(requests,'_create_request',side_effect=fail),self.assertRaises(RuntimeError): schedule.enqueue(gid,fp,db_path=self.db)
        for table in ('send_requests','rotation_state','worker_runs','daily_occurrences'): self.assertFalse(self.sql('SELECT * FROM '+table))
        schedule.enqueue(gid,fp,db_path=self.db); self.assertEqual(len(self.rows()),2)

    def test_failed_cancelled_not_recreated(self):
        gid,fp,_=self.batch(); a,b=self.rows()
        requests.fail_pretransmit(a['request_id'],db_path=self.db)
        requests.cancel_request(b['request_id'],'fixture',db_path=self.db)
        before=self.sql('SELECT * FROM send_requests');schedule.enqueue(gid,fp,db_path=self.db)
        self.assertEqual(before,self.sql('SELECT * FROM send_requests'))

    def test_older_queued_scope_not_adopted(self):
        self.manual();gid,fp=self.grant()
        with self.assertRaises(schedule.ScheduleHeld) as err: schedule.enqueue(gid,fp,db_path=self.db)
        self.assertEqual(err.exception.code,'OLDER_QUEUED_REQUEST');self.assertFalse(self.sql('SELECT * FROM worker_runs'))

    def test_manual_claim_respects_pause_parent(self):
        gid,_,_=self.batch()
        schedule.change(gid,schedule.status(gid,db_path=self.db),'PAUSED','fixture',db_path=self.db)
        with self.assertRaises(schedule.ScheduleHeld): self.claim(self.rows()[0])
        self.assertFalse(self.sql('SELECT * FROM send_requests WHERE transmitted=1'))

    def test_revoke_and_expiry_parent_claim(self):
        gid,_,_=self.batch()
        schedule.change(gid,schedule.status(gid,db_path=self.db),'REVOKED','fixture',db_path=self.db)
        with self.assertRaises(schedule.ScheduleHeld): self.claim(self.rows()[0])

    def test_window_closes_and_no_next_day_claim(self):
        gid,fp,_=self.batch(); self.clock+=3600000
        self.assertEqual(schedule.tick_preview(gid,db_path=self.db)['state'],'MISSED')
        with self.assertRaises(schedule.ScheduleHeld): self.claim(self.rows()[0])
        self.clock+=23*3600000
        with self.assertRaises(schedule.ScheduleHeld): self.claim(self.rows()[0])
        with self.assertRaises(schedule.ScheduleHeld): schedule.enqueue(gid,fp,db_path=self.db)

    def test_before_due_today_missed_and_future_grant(self):
        gid,_=self.grant(time='09:00');r=schedule.tick_preview(gid,db_path=self.db)
        self.assertEqual(r['state'],'NOT_DUE');self.assertIsNotNone(r['retry_at_ms'])
        self.clock+=2*3600000;self.assertEqual(schedule.tick_preview(gid,db_path=self.db)['state'],'MISSED')

    def test_midnight_window_clamped_and_leap_day(self):
        self.clock=int(datetime(2028,2,29,23,30,tzinfo=ledger.TZ_HO_CHI_MINH).timestamp()*1000)
        gid,_=self.grant(time='23:30',window_minutes=120)
        r=schedule.tick_preview(gid,db_path=self.db)
        self.assertEqual(r['local_date'],'2028-02-29');self.assertEqual(r['end_ms']-r['start_ms'],30*60000)

    def test_clock_rollback_holds_durably(self):
        gid,fp=self.grant();self.clock-=1
        with self.assertRaises(schedule.ScheduleHeld): schedule.enqueue(gid,fp,db_path=self.db)
        self.clock+=1;self.assertEqual(schedule.status(gid,db_path=self.db)['event']['event_type'],'HELD')

    def test_policy_drift_hold_not_revived_by_restoring(self):
        gid,_,_=self.batch();old=deepcopy(self.cfg);self.cfg['message']='changed';self.save()
        with self.assertRaises(schedule.ScheduleHeld): self.claim(self.rows()[0])
        self.cfg=old;self.save()
        self.assertEqual(schedule.status(gid,db_path=self.db)['event']['event_type'],'HELD')
        with self.assertRaises(schedule.ScheduleHeld): self.claim(self.rows()[0])

    def test_circuit_aba_invalidates_parent(self):
        gid,_,_=self.batch()
        cb.record_failure(cb.Failure('NETWORK','handshake','fixture'),db_path=self.db,uid='111')
        cb.reset('account','111',cb.inspect(db_path=self.db,uid='111')[0],'fixture',db_path=self.db)
        with self.assertRaises(schedule.ScheduleHeld): self.claim(self.rows()[0])
        self.assertEqual(schedule.status(gid,db_path=self.db)['event']['event_type'],'HELD')

    def test_daily_key_cross_campaign_session_and_schedule(self):
        self.assertEqual(schedule.daily_key('111','a','2026-10-11'),schedule.daily_key('111','a','2026-10-11'))
        self.assertNotEqual(schedule.daily_key('111','a','2026-10-11'),schedule.daily_key('111','a','2026-10-12'))
        gid,_,_=self.batch();a,b=self.rows();requests.cancel_request(a['request_id'],'fixture',db_path=self.db);requests.cancel_request(b['request_id'],'fixture',db_path=self.db)
        schedule.change(gid,schedule.status(gid,db_path=self.db),'REVOKED','fixture',db_path=self.db)
        new,fp=self.grant()
        with self.assertRaises(schedule.ScheduleHeld):schedule.enqueue(new,fp,db_path=self.db)
        self.assertEqual(len(self.rows()),2)

    def test_manual_markers_use_daily_and_total_budget(self):
        manual=self.manual();self.claim(manual);self.finish(manual)
        gid,fp=self.grant(daily_budget=1,total_budget=1)
        with self.assertRaises(schedule.ScheduleHeld) as err:schedule.enqueue(gid,fp,db_path=self.db)
        self.assertEqual(err.exception.code,'RECURRING_BUDGET')

    def test_manual_before_grant_still_counts_validity_interval(self):
        manual=self.manual();self.claim(manual);self.finish(manual)
        gid,_=self.grant();used=schedule.status(gid,db_path=self.db)['usage']
        self.assertEqual((used['daily_used'],used['total_used']),(1,1))

    def test_unknown_keeps_marker_and_blocks_parent(self):
        gid,fp,_=self.batch();a,b=self.rows();self.claim(a);self.finish(a,'failed_unknown')
        self.assertEqual(schedule.status(gid,db_path=self.db)['usage']['daily_used'],1)
        with self.assertRaises(schedule.ScheduleHeld):self.claim(b)
        self.assertEqual(requests.get_request(a['request_id'],db_path=self.db)['status'],'failed_unknown')

    def test_finite_worker_consent_cannot_override_paused_daily_parent(self):
        gid,_,out=self.batch();ids=[r['request_id'] for r in self.rows()]
        review=worker.preview('fixture',ids,db_path=self.db,expires_at_ms=self.clock+60000)
        new=worker.authorize(review,'fixture finite',db_path=self.db)
        schedule.change(gid,schedule.status(gid,db_path=self.db),'PAUSED','fixture',db_path=self.db)
        with requests.transaction(self.db) as conn:
            with self.assertRaises(schedule.ScheduleHeld):worker.check_authorization(conn,None,worker.RunContext(new,review['fingerprint']))

    def test_json_parent_label_without_durable_link_rejected(self):
        row=self.manual();review=worker.preview('fixture',[row['request_id']],db_path=self.db)
        with requests.transaction(self.db) as conn:
            run=worker._insert_authorization(conn,review,'fixture',parent={'grant_id':'fake'})
        with requests.transaction(self.db) as conn:
            with self.assertRaises(schedule.ScheduleHeld):worker.check_authorization(conn,None,worker.RunContext(run,review['fingerprint']))

    async def test_tick_default_never_sends_and_explicit_requires_fingerprint(self):
        gid,fp=self.grant()
        with patch.object(worker,'run',side_effect=AssertionError('send')):
            self.assertEqual((await schedule.tick(gid,db_path=self.db))['state'],'DUE')
            await schedule.tick(gid,fp,db_path=self.db,enqueue_only=True)
        with self.assertRaises(ValueError):await schedule.tick(gid,db_path=self.db,execute=True)

    async def test_worker_reuses_snapshot_and_completes_after_echo(self):
        gid,fp,out=self.batch()
        async def fake_send(reference,request_id,_worker_context,**kw):
            row=requests.get_request(request_id,db_path=self.db);self.claim(row,_worker_context);self.finish(row)
            return {'results':[{'status':'confirmed','request_id':request_id}]}
        with patch.object(oneshot,'run_oneshot_send',side_effect=fake_send):
            result=await schedule.tick(gid,fp,db_path=self.db,execute=True)
        self.assertEqual(result['worker']['state'],'COMPLETE');self.assertEqual(len(self.sql('SELECT * FROM worker_runs')),1)

    async def test_gates_before_complete_for_exhausted_manifest(self):
        gid,fp,out=self.batch();a,b=self.rows();self.claim(a);self.finish(a);self.claim(b);self.finish(b)
        schedule.change(gid,schedule.status(gid,db_path=self.db),'PAUSED','fixture',db_path=self.db)
        result=await worker.run(out['occurrence']['run_id'],out['run_fingerprint'],db_path=self.db)
        self.assertEqual(result['state'],'NEEDS_OWNER_REVIEW')

    def test_concurrent_ticks_one_occurrence_manifest(self):
        gid,fp=self.grant();ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(2);out=ctx.Queue()
        ps=[ctx.Process(target=competing_tick,args=(self.db,gid,fp,self.clock,barrier,out)) for _ in range(2)]
        for p in ps:p.start()
        results=[out.get(timeout=25) for _ in ps]
        for p in ps:p.join(20);self.assertEqual(p.exitcode,0)
        self.assertEqual(results[0],results[1]);self.assertEqual(len(self.sql('SELECT * FROM daily_occurrences')),1)

    def test_concurrent_final_budget_claim(self):
        gid,fp,out=self.batch(daily_budget=1,total_budget=1);ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(2);output=ctx.Queue()
        ps=[ctx.Process(target=competing_claim,args=(self.db,r['request_id'],self.cfg,self.policy,self.clock,barrier,output)) for r in self.rows()]
        for p in ps:p.start()
        results=[output.get(timeout=25) for _ in ps]
        for p in ps:p.join(20);self.assertEqual(p.exitcode,0)
        self.assertEqual(sum(results),1);self.assertEqual(self.sql('SELECT count(*) FROM send_requests WHERE transmitted=1')[0][0],1)

    def test_cli_preview_apply_and_execution_noninteractive_guards(self):
        with patch('sys.argv',['main.py','schedule-authorize','--db',self.db,'--config',self.policy,'--schedule-id','daily','--apply']),patch('sys.stdin.isatty',return_value=False),redirect_stdout(io.StringIO()):
            self.assertEqual(main.main(),3)
        self.assertFalse(self.sql('SELECT * FROM recurring_grants'))
        gid,fp=self.grant()
        with patch('sys.argv',['main.py','schedule-tick','--db',self.db,'--grant-id',gid,'--execute']),redirect_stdout(io.StringIO()):self.assertEqual(main.main(),3)

    def test_missing_db_no_creation_and_wrong_schema(self):
        missing=str(Path(self.tmp.name)/'missing.db')
        with self.assertRaises((ValueError,OSError)):schedule.preview(self.policy,'daily',db_path=missing)
        self.assertFalse(Path(missing).exists())
        with closing(sqlite3.connect(self.db)) as conn:conn.execute('PRAGMA user_version=7')
        with self.assertRaises(ValueError):self.review()

    def test_legacy_tui_timer_and_scheduler_source_cannot_send(self):
        import importlib.util
        if importlib.util.find_spec('textual') is None:
            self.skipTest('Full TUI coverage requires requirements/tui.txt; core-only run is not full acceptance')
        from tiktok_tui import TikTokTUI
        fake=type('Fake',(),{'call_from_thread':lambda *_:None,'_activity':lambda *_:None})()
        with patch.object(services,'send_plan',side_effect=AssertionError('unattended')):
            self.assertFalse(hasattr(TikTokTUI,'_check_schedule'))
            # Textual decorator exposes the original coroutine/function through __wrapped__.
            TikTokTUI._run_send.__wrapped__(fake,'Scheduler')

    async def test_pause_during_rate_wait_rechecks_parent_after_releasing_resources(self):
        self.cfg['min_send_interval_seconds']=60;self.save()
        manual=self.manual();self.claim(manual);self.finish(manual)
        gid,fp,out=self.batch()
        waits=[]
        async def pause_wait(stop,seconds):
            # Acquire the same lock/transaction while the worker sleeps.
            with ledger.RunLock(str(Path(self.db).parent/'run.lock')):
                schedule.change(gid,schedule.status(gid,db_path=self.db),'PAUSED','fixture',db_path=self.db)
            waits.append(seconds);self.clock+=int(seconds*1000)
        with patch.object(oneshot,'run_oneshot_send',side_effect=AssertionError('no send')):
            result=await worker.run(out['occurrence']['run_id'],out['run_fingerprint'],db_path=self.db,wait=pause_wait)
        self.assertEqual(waits,[60]);self.assertEqual(result['state'],'NEEDS_OWNER_REVIEW')
        self.assertEqual(self.sql('SELECT count(*) FROM send_requests WHERE transmitted=1')[0][0],1)

    async def test_actual_fake_ws_echo_finishes_after_parent_revocation(self):
        from test_streak import MockWebSocket,_build_synthetic_echo_frame
        self.cfg['targets']=self.cfg['targets'][:1];self.save()
        gid,fp,out=self.batch();row=self.rows()[0];owner=self
        class RevokingWS(MockWebSocket):
            async def send(self,packet):
                await super().send(packet)
                if requests.get_request(row['request_id'],db_path=owner.db)['transmitted']:
                    schedule.change(gid,schedule.status(gid,db_path=owner.db),'REVOKED','fixture',db_path=owner.db)
        ws=RevokingWS([b'hi',_build_synthetic_echo_frame('a','111',row['client_msg_id'],'precise text')])
        with patch.object(oneshot,'load_session',return_value={'sessionid':'synthetic'}),patch.object(oneshot,'get_own_user_id',return_value='111'),\
             patch.object(oneshot,'load_ws_auth',return_value={'device_id':'0'}),patch.object(oneshot,'validate_against_server_inbox'),\
             patch.object(oneshot,'_prepare_ws',return_value=({},'wss://fixture.invalid')),patch.object(oneshot,'_open_ws',return_value=ws):
            await schedule.tick(gid,fp,db_path=self.db,execute=True)
        self.assertEqual(requests.get_request(row['request_id'],db_path=self.db)['status'],'confirmed')
        self.assertEqual(len(ws.sent_packets),2)
        with self.assertRaises(schedule.ScheduleHeld):schedule.enqueue(gid,fp,db_path=self.db)

    async def test_expiry_and_stop_after_marker_allow_finish_no_retransmit(self):
        gid,fp,out=self.batch();stop=asyncio.Event()
        async def echo_after_expiry(reference,request_id,_worker_context,**kw):
            row=requests.get_request(request_id,db_path=self.db);self.claim(row,_worker_context)
            self.clock+=3600000;stop.set();self.finish(row)
            return {'results':[{'status':'confirmed','request_id':request_id}]}
        with patch.object(oneshot,'run_oneshot_send',side_effect=echo_after_expiry):
            result=await schedule.tick(gid,fp,db_path=self.db,execute=True,stop_event=stop)
        self.assertEqual(result['worker']['state'],'STOPPED')
        self.assertEqual(self.sql('SELECT count(*) FROM send_requests WHERE transmitted=1')[0][0],1)
        self.assertEqual(self.rows()[0]['status'],'confirmed')

    def test_crash_after_marker_recovers_unknown_without_recreation(self):
        gid,fp,_=self.batch();row=self.rows()[0];self.claim(row)
        with ledger.RunLock(str(Path(self.db).parent/'run.lock')) as lock:requests.recover_pending(db_path=self.db,run_lock=lock)
        self.assertEqual(requests.get_request(row['request_id'],db_path=self.db)['status'],'failed_unknown')
        with self.assertRaises(schedule.ScheduleHeld):schedule.enqueue(gid,fp,db_path=self.db)
        self.assertEqual(len(self.rows()),2)

    async def test_rotation_success_advances_once_and_replay_never_redraws(self):
        self.cfg.pop('message');self.cfg['targets']=self.cfg['targets'][:1]
        self.cfg.update(campaign_id='c',rotation={'templates':[{'id':'x','text':'A'},{'id':'y','text':'B'}]});self.save()
        gid,fp,out=self.batch()
        async def echo(reference,request_id,_worker_context,**kw):
            r=requests.get_request(request_id,db_path=self.db);self.claim(r,_worker_context);self.finish(r)
            return {'results':[{'status':'confirmed','request_id':request_id}]}
        with patch.object(oneshot,'run_oneshot_send',side_effect=echo):
            self.assertEqual((await schedule.tick(gid,fp,db_path=self.db,execute=True))['worker']['state'],'COMPLETE')
        self.assertEqual(self.sql('SELECT success_seq FROM rotation_state')[0][0],1)
        with patch.object(rotation,'choose',side_effect=AssertionError('redraw')):schedule.enqueue(gid,fp,db_path=self.db)
        self.clock+=86400000
        schedule.enqueue(gid,fp,db_path=self.db)
        self.assertEqual(json.loads(self.rows()[-1]['snapshot_json'])['template']['id'],'y')

    def test_expired_grant_has_no_old_date_backfill(self):
        gid,fp=self.grant(valid_through='2026-10-11');self.clock+=86400000
        self.assertEqual(schedule.tick_preview(gid,db_path=self.db)['state'],'GRANT_EXPIRED')
        with self.assertRaises(schedule.ScheduleHeld):schedule.enqueue(gid,fp,db_path=self.db)
        self.assertFalse(self.rows())

    def test_random_failed_pretransmit_snapshot_reused_next_day(self):
        self.cfg.pop('message');self.cfg.update(campaign_id='c',rotation={'mode':'random_no_immediate_repeat','templates':[{'id':'x','text':'A'},{'id':'y','text':'B'}]});self.save()
        gid,fp,_=self.batch();before={r['conv_id']:r['snapshot_json'] for r in self.rows()}
        for r in self.rows():requests.fail_pretransmit(r['request_id'],db_path=self.db)
        self.clock+=86400000
        with patch.object(rotation,'choose',side_effect=AssertionError('redraw')):schedule.enqueue(gid,fp,db_path=self.db)
        for r in self.rows()[-2:]:self.assertEqual(r['snapshot_json'],before[r['conv_id']])

    def test_readonly_tick_and_status_no_writes_or_credentials(self):
        gid,fp,out=self.batch();before={p.name:(p.read_bytes(),p.stat().st_mtime_ns,p.stat().st_mode) for p in Path(self.tmp.name).iterdir()}
        with patch('os.chmod',side_effect=AssertionError('chmod')),patch('os.makedirs',side_effect=AssertionError('mkdir')),patch.object(oneshot,'load_session',side_effect=AssertionError('credentials')):
            schedule.tick_preview(gid,db_path=self.db);schedule.status(gid,db_path=self.db)
        self.assertEqual(before,{p.name:(p.read_bytes(),p.stat().st_mtime_ns,p.stat().st_mode) for p in Path(self.tmp.name).iterdir()})

    def test_identical_queue_rebind_invalidates_derived_parent(self):
        import queue_service as queue
        gid,_,_=self.batch();row=self.rows()[0]
        queue.bind_request(row['request_id'],self.cfg,self.policy,queue.preview_bind(row['request_id'],self.cfg,self.policy,db_path=self.db),'fixture rebind',db_path=self.db)
        with self.assertRaises(schedule.ScheduleHeld):self.claim(row)
        self.assertEqual(schedule.status(gid,db_path=self.db)['event']['event_type'],'HELD')

    def test_session_circuit_aba_fails_closed(self):
        gid,_,_=self.batch()
        cb.record_failure(cb.Failure('NETWORK','handshake','fixture'),db_path=self.db,session='fixture')
        cb.reset('session','fixture',cb.inspect(db_path=self.db,session='fixture')[0],'fixture',db_path=self.db)
        with self.assertRaises(schedule.ScheduleHeld):self.claim(self.rows()[0])
        self.assertEqual(schedule.status(gid,db_path=self.db)['event']['event_type'],'HELD')

    def test_missing_binding_before_authorize_never_guesses_uid(self):
        self.cfg['session']='unbound';self.save()
        with self.assertRaises(ledger.LedgerError):self.review()
        self.assertFalse(self.sql('SELECT * FROM recurring_grants'))

    def test_nonempty_wal_preview_refuses_without_side_effects(self):
        gid,_=self.grant();conn=sqlite3.connect(self.db)
        try:
            conn.execute('PRAGMA journal_mode=WAL');conn.execute('CREATE TABLE disposable_extra(x)');conn.commit()
            before={p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in Path(self.tmp.name).iterdir()}
            with self.assertRaises(ValueError):schedule.status(gid,db_path=self.db)
            self.assertEqual(before,{p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in Path(self.tmp.name).iterdir()})
        finally:conn.close()

    async def test_identity_failure_stops_real_send_adapter_before_ws_or_marker(self):
        gid,fp,_=self.batch()
        with patch.object(oneshot,'load_session',return_value={'sessionid':'synthetic'}),\
             patch.object(oneshot,'get_own_user_id',side_effect=cb.ProtocolFailure('AUTHENTICATED_SELF_CONTRACT_UNVERIFIED')),\
             patch.object(oneshot,'_open_ws',side_effect=AssertionError('WS bypass')):
            result=await schedule.tick(gid,fp,db_path=self.db,execute=True)
        self.assertEqual(result['worker']['state'],'NEEDS_OWNER_REVIEW')
        self.assertFalse(self.sql('SELECT * FROM send_requests WHERE transmitted=1'))
