"""Disposable LOCAL HTTP wire regression; never public authentication."""
import base64, json, os, sys, tempfile, threading, time, unittest
from pathlib import Path
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import mibera as m
from wallet_bridge import Vault, Guard
from eth_account import Account

class Recovery(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'MIBERA_SESSION_PASSWORD':'disposable-local-recovery-password'});self.env.start()
        self.v=Vault(self.t.name);self.j=m.Journal(self.v);self.account=Account.create().address;self.op='login-recovery-001'
    def tearDown(self):self.j.db.close();self.env.stop();self.t.cleanup()
    def response(self,**kw):
        r={'ticket':'DISPOSABLE_FIXTURE_TICKET_123','miberas':[1000007],'expires':time.time()*1000+60000};r.update(kw);return r
    def stage(self,r=None,**kw):
        nk='nonce_'+m.digest([self.account.lower(),'LOCALnonce1234'])
        self.j.reserve(self.op,self.account,'login',{});self.j.reserve(nk,self.account,'nonce:'+m.digest('LOCALnonce1234'),{})
        d={'messageSHA256':m.digest('local-message'),'nonceKey':nk};self.j.update(self.op,'SUBMITTING',d)
        raw={'account':self.account.lower(),'operation':self.op,'messageSHA256':d['messageSHA256'],'nonceKey':nk,'status':200,'headers':[['Content-Type','application/json']],'cookies':{'fixture':'local'},'body':base64.b64encode(json.dumps(r or self.response()).encode()).decode(),'receivedAt':time.time(),'truncated':False};raw.update(kw)
        self.v.put('login_raw_'+m.digest(self.op),raw);return raw
    def ack(self):return m.login_reconcile(self.v,self.j,self.account,self.op)
    def test_wire_capture_before_json_failure(self):
        raw=b'{broken-json';captured=[]
        class H(BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']));self.send_response(200);self.send_header('Set-Cookie','fixture=local; Path=/');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        s=ThreadingHTTPServer(('127.0.0.1',0),H);th=threading.Thread(target=s.serve_forever,daemon=True);th.start();origin='http://127.0.0.1:'+str(s.server_port)
        try:
            with patch.object(m,'M',origin):
                h=m.HTTP()
                with self.assertRaises(Exception):h.call(origin,'/door/sign',{},capture=captured.append)
                h.s.close()
            self.assertEqual(len(captured),1);self.assertEqual(base64.b64decode(captured[0]['body']),raw);self.assertEqual(captured[0]['cookies']['fixture'],'local')
        finally:s.shutdown();s.server_close();th.join()
    def test_accepted_recovery_idempotent_without_network_or_wallet(self):
        self.stage()
        with patch.object(m.HTTP,'call',side_effect=AssertionError('network forbidden')):
            self.assertTrue(self.ack()['authenticated']);before=self.v.get('session');self.assertTrue(self.ack()['authenticated']);self.assertEqual(before,self.v.get('session'))
        self.assertEqual(self.j.read(self.op)['state'],'VERIFIED')
    def test_missing_raw_stops(self):
        self.j.reserve(self.op,self.account,'login',{});self.assertRaises(Exception,self.ack);self.assertEqual(self.j.read(self.op)['state'],'RESERVED')
    def test_invalid_envelopes_stop(self):
        raw=self.stage()
        variants=[{'operation':'wrong'},{'account':Account.create().address},{'nonceKey':'wrong'},{'messageSHA256':'wrong'},{'status':500},{'truncated':True},{'body':base64.b64encode(b'{broken').decode()},{'receivedAt':float('inf')}]
        for v in variants:
            with self.subTest(v=list(v)):
                self.v.put('login_raw_'+m.digest(self.op),dict(raw,**v));self.assertRaises(Exception,self.ack);self.assertEqual(self.j.read(self.op)['state'],'SUBMITTING')
    def test_invalid_response_fields_stop(self):
        raw=self.stage()
        for changes in [{'expires':float('inf')},{'expires':float('nan')},{'expires':True},{'expires':-1},{'miberas':[]},{'miberas':[True]},{'miberas':[-7]},{'miberas':[7,7]},{'miberas':'wrong'},{'ticket':'short'},{'error':'denied'}]:
            with self.subTest(fields=list(changes)):
                r=self.response(**changes);self.v.put('login_raw_'+m.digest(self.op),dict(raw,body=base64.b64encode(json.dumps(r).encode()).decode()));self.assertRaises(Exception,self.ack)
    def test_expired_accepted_finalizes_without_restoring_session(self):
        self.stage(self.response(expires=time.time()*1000-5000),receivedAt=time.time()-10);self.assertFalse(self.ack()['authenticated']);self.assertEqual(self.j.read(self.op)['state'],'VERIFIED');self.assertFalse((self.v.path/'session.enc').exists());self.assertFalse(self.ack()['authenticated'])
    def test_nonfinite_session_expiry_rejected(self):
        for x in [float('inf'),float('nan'),True]:
            with self.subTest(x=x):self.assertRaises(Guard,m.session_validate,{'account':self.account,'response':self.response(expires=x)},self.account)
    def test_new_operation_after_complete_old_never_reused(self):
        self.stage();self.ack();self.j.reserve('login-recovery-002',self.account,'login',{});self.assertEqual(self.j.read(self.op)['state'],'VERIFIED');self.assertRaises(Exception,self.j.reserve,self.op,self.account,'login',{})
    def test_expired_at_receipt_is_not_proven_accepted(self):
        self.stage(self.response(expires=time.time()*1000-1000));self.assertRaises(Guard,self.ack);self.assertEqual(self.j.read(self.op)['state'],'SUBMITTING')
    def test_wrong_journal_account_or_nonce_stops(self):
        raw=self.stage();self.assertRaises(Guard,m.login_reconcile,self.v,self.j,Account.create().address,self.op)
        self.j.update(raw['nonceKey'],'SIGNING',{});self.assertRaises(Guard,self.ack);self.assertEqual(self.j.read(self.op)['state'],'SUBMITTING')
    def test_local_session_write_failure_preserves_consumption_for_ack(self):
        self.stage();put=self.v.put
        with patch.object(self.v,'put',side_effect=PermissionError('LOCAL disk fault')):self.assertRaises(PermissionError,self.ack)
        self.assertEqual(self.j.read(self.op)['state'],'SUBMITTING');self.assertTrue(self.ack()['authenticated'])
    def test_cli_ack_without_bridge_and_no_secret_output(self):
        import subprocess
        self.stage()
        for command in ['loginack','login-reconcile']:
            r=subprocess.run([sys.executable,str(Path(m.__file__)), '--state',str(self.v.path),command,'--account',self.account,'--op',self.op],capture_output=True,text=True,timeout=20)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertTrue(json.loads(r.stdout)['result']['authenticated']);self.assertNotIn(self.response()['ticket'],r.stdout+r.stderr);self.assertNotIn('local-recovery-password',r.stdout+r.stderr)

if __name__=='__main__':unittest.main()

# Full concrete connector, disposable signer and real loopback HTTP. Inject only
# a post-response parser failure; production never substitutes fixture success.
import test_integration as fixtures
class Wire(unittest.TestCase):
    def test_parser_failure_then_ack_then_new_login(self):
        f=fixtures.Tests();f.setUp()
        try:
            orig=m.HTTP.call;calls=[];signs=[];rpc=f.f.rpc
            def counted_rpc(method,args):
                if method=='personal_sign':signs.append(method)
                return rpc(method,args)
            f.f.rpc=counted_rpc
            def call(h,origin,path,*a,**kw):
                calls.append(path);r=orig(h,origin,path,*a,**kw)
                if path=='/door/nonce':r['nonce']+='N'+str(calls.count(path))
                if path=='/door/sign' and calls.count(path)==1:raise ValueError('LOCAL parser fault after persisted response')
                return r
            with patch.object(m.HTTP,'call',call):
                self.assertRaises(ValueError,m.login,f.v,f.w,f.j,f.f.account,'login-wire-001',True)
                self.assertEqual(f.j.read('login-wire-001')['state'],'SUBMITTING');before=list(calls)
                for _ in range(3):self.assertTrue(m.login_reconcile(f.v,f.j,f.f.account,'login-wire-001')['authenticated'])
                self.assertEqual(calls,before);self.assertEqual(len(signs),1);self.assertEqual(f.f.sig_checks,1)
                saved=f.v.get('session');saved['response']['expires']=time.time()*1000-1;f.v.put('session',saved)
                self.assertTrue(m.login(f.v,f.w,f.j,f.f.account,'login-wire-002',True)['authenticated'])
                self.assertEqual(len(signs),2);self.assertEqual(f.f.sig_checks,2)
                # Old ack must not roll a newer accepted session backwards.
                newer=f.v.get('session');m.login_reconcile(f.v,f.j,f.f.account,'login-wire-001');self.assertEqual(newer,f.v.get('session'))
                self.assertRaises(Exception,m.login,f.v,f.w,f.j,f.f.account,'login-wire-001',True)
                self.assertEqual(len(signs),2);self.assertEqual(calls.count('/door/nonce'),2)
        finally:f.tearDown()
