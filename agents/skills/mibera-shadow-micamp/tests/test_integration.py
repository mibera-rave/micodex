"""LOCAL fixtures only: no public login, public sockets or paid transactions."""
import datetime as dt, hashlib, json, os, sys, tempfile, threading, time, unittest, subprocess
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import requests, websocket
from websockets.sync.server import serve as ws_serve
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_abi import encode, decode
from eth_hash.auto import keccak
import mibera as m
from wallet_bridge import Vault,Wallet,serve,Guard

class Local:
    """Disposable wallet exists in memory only; emulates wallet extension transport.
    Mint RPC results are explicitly synthetic, NOT an EVM or paid chain execution.
    HTTP login and WebSocket protocols use real loopback sockets/signature recovery.
    """
    def __init__(self,v):
        self.key=Account.create();self.account=self.key.address;self.chain=80094;self.stop=False;self.sig_checks=0;self.sends=0;self.action_sends=0;self.bad_recovery=False;self.bad_welcome=False;self.no_ack=False
        self.code='0x6000';self.traits='mibera-shadow/v1|body=body/beige';self.tx=None;self.hash='0x'+'ab'*32
        self.b=serve(v,open_browser=False);threading.Thread(target=self.b.serve_forever,daemon=True).start()
        self.bridge=v.get('bridge');threading.Thread(target=self.poll,daemon=True).start()
        fixture=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def sendj(self,o):
                b=json.dumps(o).encode();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
            def do_GET(self):
                path=self.path
                if path=='/door/nonce':return self.sendj({'domain':'micamp.miberarave.xyz','uri':'https://micamp.miberarave.xyz','statement':'door.statement','chainId':80094,'nonce':'LOCALnonce1234','issuedAt':dt.datetime.now(dt.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')})
                if path=='/fires':
                    assert self.headers['Authorization']=='Bearer '+'LOCAL_FIXTURE_TICKET_'*2
                    return self.sendj({'fire':'local-fixture'})
                if path=='/api/registry':return self.sendj({'traits':[{'id':'body/beige','cat':'body','state':'shelf'}]})
                if path.startswith('/api/taken?'):return self.sendj({'taken':False})
                if path.startswith('/api/price?'):return self.sendj({'chainId':4663,'wei':'1000','ethUsd':2000,'usdCents':1,'updatedAt':time.time(),'maxPriceAge':60})
                if path.startswith('/api/shadow?'):return self.sendj({'ok':True,'shadow':{'chainId':4663,'tokenId':'7','contract':m.C,'traits':fixture.traits,'txHash':fixture.hash}})
                raise AssertionError(path)
            def do_POST(self):
                o=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.path=='/door/sign':
                    assert Account.recover_message(encode_defunct(text=o['message']),signature=o['signature']).lower()==fixture.account.lower()
                    fixture.sig_checks+=1
                    return self.sendj({'ticket':'LOCAL_FIXTURE_TICKET_'*2,'miberas':[1000007],'expires':time.time()*1000+120000})
                if self.path=='/api/permit':return self.sendj({'ok':True,'contract':m.C,'deadline':int(time.time())+120,'signature':'0x'+'12'*65})
                if self.path=='/api/vended':return self.sendj({'ok':True})
                raise AssertionError(self.path)
        self.http=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=self.http.serve_forever,daemon=True).start();self.url='http://127.0.0.1:'+str(self.http.server_port)
        def game(ws):
            q=json.loads(ws.recv());assert q['t']=='join' and q['ticket']=='LOCAL_FIXTURE_TICKET_'*2 and q['me']==1000007
            ws.send(json.dumps({'t':'welcome','you':'local-you','people':[{'id':'local-you','me':999 if fixture.bad_welcome else 1000007,'pos':[100,100]}]}))
            for raw in ws:
                o=json.loads(raw)
                if o['t']=='part':break
                fixture.action_sends+=1
                if fixture.no_ack:ws.close();break
                f={'t':{'emote':'emoted','say':'said','walk':'walked'}[o['t']],'id':'local-you'}
                f.update({k:v for k,v in o.items() if k!='t'})
                if o['t']=='say':
                    # Independent stable-contract fixture, not the client's helper.
                    import re
                    f['text']=re.sub(r'[\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]+',' ',o['text']).strip(' ')
                ws.send(json.dumps(f))
        self.ws=ws_serve(game,'127.0.0.1',0);threading.Thread(target=self.ws.serve_forever,daemon=True).start();self.wsurl='ws://127.0.0.1:'+str(self.ws.socket.getsockname()[1])
    def connect_ws(self,*args,**kwargs):return websocket.create_connection(self.wsurl,timeout=2,http_proxy_host=None)
    def poll(self):
        s=requests.Session();s.trust_env=False;headers={'Authorization':'Bearer '+self.bridge['token']}
        while not self.stop:
            try:
                r=s.get(self.bridge['url']+'/poll',headers=headers,timeout=2);q=r.json()
                if not q:time.sleep(.01);continue
                try:answer={'id':q['id'],'result':self.rpc(q['method'],q['params'])}
                except Exception:answer={'id':q['id'],'error':'local_fixture_failure'}
                s.post(self.bridge['url']+'/answer',headers=headers,json=answer,timeout=2)
            except requests.RequestException:break
    def rpc(self,method,args):
        if method in ('eth_accounts','eth_requestAccounts'):return [self.account]
        if method=='eth_chainId':return hex(self.chain)
        if method=='wallet_switchEthereumChain':self.chain=int(args[0]['chainId'],16);return None
        if method=='personal_sign':
            key=Account.create() if self.bad_recovery else self.key
            return '0x'+key.sign_message(encode_defunct(hexstr=args[0])).signature.hex()
        if method=='eth_getCode':return self.code
        if method=='eth_getTransactionCount':return '0x0'
        if method=='eth_gasPrice':return '0x1'
        if method=='eth_getBalance':return hex(10**18)
        if method=='eth_estimateGas':return hex(100000)
        if method=='eth_call':
            data=args[0]['data'];sel=data[:10]
            signatures={'priceWei()':(('uint256',),(1000,)),'paused()':(('bool',),(False,)),'areTraitsUsed(string)':(('bool',),(False,)),'ownerOf(uint256)':(('address',),(self.account,)),'tokenURI(uint256)':(('string',),('ipfs://LOCAL_FIXTURE_METADATA',))}
            for sig,(types,vals) in signatures.items():
                if sel=='0x'+keccak(sig.encode())[:4].hex():return '0x'+encode(types,vals).hex()
            if sel=='0x'+keccak(b'vend(string,uint256,bytes)')[:4].hex():
                vals=decode(('string','uint256','bytes'),bytes.fromhex(data[10:]));assert vals[0]==self.traits and vals[1]>time.time();return '0x'+encode(('uint256',),(7,)).hex()
            raise AssertionError('unexpected fixture call')
        if method=='eth_sendTransaction':
            tx=args[0];signed=self.key.sign_transaction(tx);assert Account.recover_transaction(signed.raw_transaction).lower()==self.account.lower()
            self.tx=tx;self.sends+=1;return self.hash
        if method=='eth_getTransactionByHash':return dict(self.tx,input=self.tx['data'])
        if method=='eth_getBlockByNumber':return {'hash':'0x'+'cd'*32,'number':'0xa' if args[0]!='latest' else '0xc'}
        if method=='eth_getTransactionReceipt':
            addr='0x'+self.account[2:].lower().zfill(64);tok='0x'+format(7,'064x');look=m.public.look_hash(self.traits)
            return {'status':'0x1','gasUsed':'0x186a0','effectiveGasPrice':'0x1','transactionHash':self.hash,'blockNumber':'0xa','blockHash':'0x'+'cd'*32,'logs':[{'address':m.C,'topics':['0x'+keccak(b'Transfer(address,address,uint256)').hex(),'0x'+'0'*64,addr,tok],'data':'0x'},{'address':m.C,'topics':['0x'+keccak(b'Vended(address,uint256,bytes32,string,address,uint256)').hex(),addr,tok,look],'data':'0x'+encode(('string','address','uint256'),(self.traits,'0x'+'0'*40,1010)).hex()}]}
        raise AssertionError(method)
    def close(self):
        self.stop=True;self.b.shutdown();self.b.server_close();self.http.shutdown();self.http.server_close();self.ws.shutdown()

class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'MIBERA_SESSION_PASSWORD':'local-test-only-passphrase'});self.env.start();self.v=Vault(self.temp.name);self.f=Local(self.v);self.w=Wallet(self.v);self.j=m.Journal(self.v)
        self.patches=[patch.object(m,'V',self.f.url),patch.object(m,'M',self.f.url),patch.object(m,'runtime_check',lambda:None)]
        for p in self.patches:p.start()
    def tearDown(self):
        self.j.db.close();self.f.close()
        for p in reversed(self.patches):p.stop()
        self.env.stop();self.temp.cleanup()
    def login(self):return m.login(self.v,self.w,self.j,self.f.account,'login-local-001',True)
    def action(self,kind,**kwargs):
        return m.participate(self.v,self.j,self.f.account,1000007,'Fixture-AI','action-local-001',{'kind':kind,**kwargs},socket_factory=self.f.connect_ws)
    def consent(self,**kwargs):
        c=dict(operation_id='mint-local-001',approved=True,count=1,account=self.f.account,chain=4663,contract=m.C,traits=self.f.traits,max_total_wei=10**12,max_gas_wei=10**10,reserve_wei=100,max_usd_cents=1000,max_quote_age=60,max_usd_age=60,expires=int(time.time())+120);c.update(kwargs);return m.Consent(**c)
    def mint(self,**kwargs):return m.mint(self.v,self.w,self.j,self.consent(**kwargs),{'body':'body/beige'},hashlib.sha256(bytes.fromhex(self.f.code[2:])).hexdigest())
    def test_concrete_connector_signature_http_ws_wave(self):
        self.assertTrue(self.login()['authenticated']);self.assertEqual(self.f.sig_checks,1);self.assertTrue(self.action('wave')['action']['acknowledged']);self.assertEqual(self.f.sends,0)
    def test_cli_secure_entrypoint_connect(self):
        script=Path(__file__).resolve().parents[1]/'scripts/secure_run.py'
        r=subprocess.run([sys.executable,str(script),'--state',str(self.v.path),'connect','--account',self.f.account,'--chain','80094'],capture_output=True,text=True,timeout=30)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertTrue(json.loads(r.stdout)['result']['connected'])
    def test_ws_chat_ack(self):self.login();self.assertEqual(self.action('chat',text='LOCAL ONLY',approved=True)['action']['ackType'],'said')
    def test_ws_normalized_chat_ack(self):
        self.login();self.assertTrue(self.action('chat',text='  hello\n\t camp  ',approved=True)['action']['acknowledged'])
        self.assertEqual(self.j.read('action-local-001')['state'],'VERIFIED')
    def test_ws_move_ack(self):self.login();self.assertEqual(self.action('move',dx=12,dy=0)['action']['ackType'],'walked')
    def test_join_no_action(self):self.login();self.assertTrue(m.participate(self.v,self.j,self.f.account,1000007,'Fixture',socket_factory=self.f.connect_ws)['joined']);self.assertEqual(self.f.action_sends,0)
    def test_local_paid_fixture_signature_receipt_owner(self):self.assertEqual(self.mint()['tokenId'],7);self.assertEqual(self.f.sends,1)
    def test_mint_dedupe(self):self.mint();self.assertRaises(Exception,self.mint);self.assertEqual(self.f.sends,1)
    def test_mint_reserve(self):self.assertRaises(Guard,self.mint,reserve_wei=10**19);self.assertEqual(self.f.sends,0)
    def test_mint_total_cap(self):self.assertRaises(Guard,self.mint,max_total_wei=100);self.assertEqual(self.f.sends,0)
    def test_mint_gas_cap(self):self.assertRaises(Guard,self.mint,max_gas_wei=1)
    def test_mint_usd_cap(self):self.assertRaises(ValueError,self.mint,max_usd_cents=0)
    def test_mint_count(self):self.assertRaises(ValueError,self.mint,count=2)
    def test_login_requires_consent(self):self.assertRaises(Guard,m.login,self.v,self.w,self.j,self.f.account,'login-0001',False)
    def test_recovery_mismatch(self):self.f.bad_recovery=True;self.assertRaises(Guard,self.login);self.assertEqual(self.f.sig_checks,0)
    def test_login_ambiguous_barrier(self):
        self.f.bad_recovery=True;self.assertRaises(Guard,self.login);self.assertRaises(Guard,m.login,self.v,self.w,self.j,self.f.account,'different-op-001',True)
    def test_wallet_account_mismatch(self):self.assertRaises(Guard,self.w.identity,'0x'+'01'*20,80094)
    def test_wallet_chain_mismatch(self):self.assertRaises(Guard,self.w.identity,self.f.account,4663)
    def test_vault_encrypted(self):
        self.login();b=(self.v.path/'session.enc').read_bytes();self.assertNotIn(b'LOCAL_FIXTURE_TICKET',b);self.assertNotIn(self.f.account.encode(),b)
    def test_vault_wrong_password(self):self.v.put('test',{'ticket':'secret'});self.v.password='different-password';self.assertRaises(Exception,self.v.get,'test')
    def test_bridge_auth(self):self.assertEqual(requests.get(self.f.bridge['url']+'/poll',timeout=2).status_code,403)
    def test_bridge_origin(self):self.assertEqual(requests.get(self.f.bridge['url']+'/poll',headers={'Authorization':'Bearer '+self.f.bridge['token'],'Origin':'https://evil.invalid'},timeout=2).status_code,403)
    def test_bridge_unknown_method(self):self.assertRaises(Guard,self.w.rpc,'eth_sign',[])
    def test_browser_capability_cannot_initiate_rpc(self):
        r=requests.post(self.f.bridge['url']+'/rpc',headers={'Authorization':'Bearer '+self.f.bridge['token']},json={'method':'personal_sign','params':[]},timeout=2)
        self.assertEqual(r.status_code,409)
    def test_bridge_arbitrary_sign_denied(self):
        self.assertRaises(Guard,self.w.rpc,'personal_sign',['0x68656c6c6f',self.f.account])
    def test_bridge_arbitrary_transaction_denied(self):
        self.assertRaises(Guard,self.w.rpc,'eth_sendTransaction',[{'to':self.f.account,'value':'0x1'}])
    def test_receipt_fee_mutation(self):
        original=self.f.rpc
        def rpc(method,args):
            r=original(method,args)
            if method=='eth_getTransactionByHash':r['gasPrice']='0x2'
            return r
        self.f.rpc=rpc;self.assertRaises(Guard,self.mint);self.assertEqual(self.j.read('mint-local-001')['state'],'SUBMITTED')
    def test_character_rejected(self):self.login();self.assertRaises(Guard,m.participate,self.v,self.j,self.f.account,42,'Fixture')
    def test_welcome_mismatch(self):self.login();self.f.bad_welcome=True;self.assertRaises(Guard,self.action,'wave');self.assertEqual(self.f.action_sends,0)
    def test_chat_consent(self):self.login();self.assertRaises(Guard,self.action,'chat',text='local',approved=False);self.assertEqual(self.f.action_sends,0)
    def test_move_bound(self):self.login();self.assertRaises(Guard,self.action,'move',dx=100,dy=0)
    def test_action_dedupe(self):self.login();self.action('wave');self.assertRaises(Guard,self.action,'wave');self.assertEqual(self.f.action_sends,1)
    def test_persistent_ambiguous_barrier(self):
        self.j.reserve('ambiguous-local',self.f.account,'mint',{'nonce':'0x0'});self.j.db.close();self.j=m.Journal(self.v);self.assertRaises(Guard,self.mint);self.assertEqual(self.f.sends,0)
    def test_expired_session(self):
        self.login();s=self.v.get('session');s['response']['expires']=0;self.v.put('session',s);self.assertRaises(Guard,self.action,'wave')
    def test_ambiguous_action_persistent(self):
        self.login();self.f.no_ack=True;self.assertRaises(Exception,self.action,'wave');self.assertEqual(self.j.read('action-local-001')['state'],'SENDING');self.assertRaises(Guard,self.action,'wave');self.assertEqual(self.f.action_sends,1)
    def test_runtime_hash_mismatch(self):
        self.assertRaises(Guard,m.mint,self.v,self.w,self.j,self.consent(),{'body':'body/beige'},'0'*64);self.assertEqual(self.f.sends,0)
    def test_simulation_revert_barrier(self):
        original=self.f.rpc
        def rpc(method,args):
            if method=='eth_estimateGas':raise RuntimeError('LOCAL_REVERT')
            return original(method,args)
        self.f.rpc=rpc;self.assertRaises(Guard,self.mint);self.assertEqual(self.f.sends,0);self.assertEqual(self.j.read('mint-local-001')['state'],'RESERVED')
    def test_broadcast_ambiguous_no_retry(self):
        original=self.f.rpc
        def rpc(method,args):
            if method=='eth_sendTransaction':original(method,args);raise RuntimeError('LOCAL_LOST_RESPONSE')
            return original(method,args)
        self.f.rpc=rpc;self.assertRaises(Guard,self.mint);self.assertEqual(self.f.sends,1);self.assertEqual(self.j.read('mint-local-001')['state'],'BROADCASTING');self.assertRaises(Guard,self.mint);self.assertEqual(self.f.sends,1)
    def test_wrong_owner_rejected(self):
        original=self.f.rpc
        def rpc(method,args):
            if method=='eth_call' and args[0]['data'][:10]=='0x6352211e':return '0x'+encode(('address',),('0x'+'01'*20,)).hex()
            return original(method,args)
        self.f.rpc=rpc;self.assertRaises(Guard,self.mint);self.assertEqual(self.j.read('mint-local-001')['state'],'SUBMITTED')
    def test_noncanonical_receipt(self):
        original=self.f.rpc
        def rpc(method,args):
            r=original(method,args)
            if method=='eth_getTransactionReceipt':r['blockHash']='0x'+'ef'*32
            return r
        self.f.rpc=rpc;self.assertRaises(Guard,self.mint)
    def test_wrong_receipt_calldata(self):
        original=self.f.rpc
        def rpc(method,args):
            r=original(method,args)
            if method=='eth_getTransactionByHash':r['input']='0xdeadbeef'
            return r
        self.f.rpc=rpc;self.assertRaises(Guard,self.mint)
    def test_expired_consent(self):self.assertRaises(ValueError,self.mint,expires=1);self.assertEqual(self.f.sends,0)
    def test_strict_private_acl(self):
        if os.name=='nt':
            import win32security
            sd=win32security.GetNamedSecurityInfo(str(self.v.path),win32security.SE_FILE_OBJECT,win32security.DACL_SECURITY_INFORMATION)
            self.assertEqual(sd.GetSecurityDescriptorDacl().GetAceCount(),1)
        else:self.assertEqual(self.v.path.stat().st_mode&0o777,0o700)
    def test_siwe_bindings(self):
        ch={'domain':'micamp.miberarave.xyz','uri':'https://micamp.miberarave.xyz','statement':'door.statement','chainId':80094,'nonce':'fixture1234','issuedAt':dt.datetime.now(dt.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')}
        for k,v in [('domain','evil.invalid'),('chainId',4663),('nonce','bad!'),('issuedAt','2020-01-01T00:00:00Z')]:
            with self.subTest(k=k):self.assertRaises(ValueError,m.siwe_message,{**ch,k:v},self.f.account)
if __name__=='__main__':unittest.main()
