"""Loopback EIP-1193 connector. Keys remain in the user's browser wallet."""
import base64, hashlib, json, os, re, secrets, threading, time, webbrowser
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import requests
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class Guard(Exception): pass
def need(ok, code):
    if not ok: raise Guard(code)

def private_dir(path):
    p=Path(path).expanduser().resolve();p.mkdir(parents=True,exist_ok=True)
    if os.name=='nt':
        import win32api,win32con,win32security,ntsecuritycon
        token=win32security.OpenProcessToken(win32api.GetCurrentProcess(),win32con.TOKEN_QUERY)
        sid=win32security.GetTokenInformation(token,win32security.TokenUser)[0]
        acl=win32security.ACL();acl.AddAccessAllowedAceEx(win32security.ACL_REVISION,3,ntsecuritycon.FILE_ALL_ACCESS,sid)
        win32security.SetNamedSecurityInfo(str(p),win32security.SE_FILE_OBJECT,win32security.DACL_SECURITY_INFORMATION|win32security.PROTECTED_DACL_SECURITY_INFORMATION,None,None,acl,None)
    else:
        p.chmod(0o700);need(p.stat().st_uid==os.getuid(),'state_owner')
    return p

class Vault:
    def __init__(self, path):
        self.path=private_dir(path)
        self.password=os.environ.get('MIBERA_SESSION_PASSWORD','')
        need(len(self.password)>=16,'set_MIBERA_SESSION_PASSWORD_minimum_16_characters')
    def put(self,name,obj):
        need(name.isidentifier(),'vault_name')
        salt=os.urandom(16);iv=os.urandom(12)
        key=Scrypt(salt=salt,length=32,n=2**14,r=8,p=1).derive(self.password.encode())
        blob=salt+iv+AESGCM(key).encrypt(iv,json.dumps(obj).encode(),name.encode())
        p=self.path/(name+'.enc');tmp=self.path/(name+'.'+secrets.token_hex(8)+'.tmp')
        fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:f.write(blob);f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
    def get(self,name):
        need(name.isidentifier(),'vault_name')
        b=(self.path/(name+'.enc')).read_bytes()
        key=Scrypt(salt=b[:16],length=32,n=2**14,r=8,p=1).derive(self.password.encode())
        return json.loads(AESGCM(key).decrypt(b[16:28],b[28:],name.encode()))

ALLOWED={'eth_requestAccounts','eth_accounts','eth_chainId','wallet_switchEthereumChain','personal_sign','eth_getCode','eth_call','eth_estimateGas','eth_gasPrice','eth_getBalance','eth_getTransactionCount','eth_sendTransaction','eth_getTransactionReceipt','eth_getTransactionByHash','eth_getBlockByNumber'}
def request_scope(method,params):
    # Enforce write scope at the transport too, not just in the CLI.
    if method=='wallet_switchEthereumChain':
        need(len(params)==1 and set(params[0])=={'chainId'} and int(params[0]['chainId'],16) in (4663,80094),'switch_scope')
    if method=='personal_sign':
        from wallet_adapter import siwe_message
        need(len(params)==2 and isinstance(params[0],str) and params[0].startswith('0x'),'sign_scope')
        text=bytes.fromhex(params[0][2:]).decode('utf-8');lines=text.split('\n')
        need(len(lines)==10 and lines[1]==params[1] and lines[8].startswith('Nonce: ') and lines[9].startswith('Issued At: '),'sign_scope')
        ch={'domain':'micamp.miberarave.xyz','uri':'https://micamp.miberarave.xyz','chainId':80094,'statement':'door.statement','nonce':lines[8][7:],'issuedAt':lines[9][11:]}
        need(siwe_message(ch,params[1])==text,'sign_scope')
    if method=='eth_sendTransaction':
        need(len(params)==1 and isinstance(params[0],dict),'send_scope');tx=params[0]
        need(set(tx)=={'from','to','chainId','nonce','value','data','gas','gasPrice'} and tx['to'].lower()=='0x46fab53a5ef4e7d0b48ff3c9e4339e15a583f0ab' and int(tx['chainId'],16)==4663,'send_scope')
        from eth_hash.auto import keccak
        need(tx['data'].startswith('0x'+keccak(b'vend(string,uint256,bytes)')[:4].hex()),'send_calldata_scope')
PAGE='''<!doctype html><meta charset="utf-8"><title>Mibera own-wallet bridge</title><h1>Mibera wallet bridge</h1><p>Connect only your own browser wallet. Inspect every wallet prompt. Keep this tab open. No keys are imported.</p><button id="start">Connect wallet and start</button><p id="status">Stopped</p><script src="/bridge.js"></script>'''
SCRIPT='''const token=location.hash.slice(1);history.replaceState(null,'','/');
const headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'};
document.getElementById('start').onclick=async()=>{if(!window.ethereum){document.getElementById('status').textContent='Install an EIP-1193 wallet extension in this browser first';return;}
await ethereum.request({method:'eth_requestAccounts'});document.getElementById('status').textContent='Connected; waiting for agent requests';
while(true){try{let r=await fetch('/poll',{headers});if(!r.ok)throw Error();let q=await r.json();if(!q){await new Promise(r=>setTimeout(r,250));continue;}let answer={id:q.id};try{answer.result=await ethereum.request({method:q.method,params:q.params});}catch(e){answer.error='wallet_rejected_or_failed';}await fetch('/answer',{method:'POST',headers,body:JSON.stringify(answer)});}catch(e){document.getElementById('status').textContent='Bridge stopped';break;}}};'''

def serve(vault,port=0,open_browser=True):
    token=secrets.token_urlsafe(32);rpc_token=secrets.token_urlsafe(32);lock=threading.Lock();pending={}; active=[None]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,obj,status=200,kind='application/json'):
            b=(json.dumps(obj) if kind=='application/json' else obj).encode()
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(b)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers();self.wfile.write(b)
        def check(self,auth=True):
            need(self.headers.get('Host')=='127.0.0.1:'+str(self.server.server_port),'bridge_host')
            origin=self.headers.get('Origin');need(not origin or origin=='http://127.0.0.1:'+str(self.server.server_port),'bridge_origin')
            if auth:
                expected=rpc_token if self.path=='/rpc' else token
                need(secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+expected),'bridge_auth')
        def do_GET(self):
            try:
                self.check(self.path not in ('/','/bridge.js'))
                if self.path=='/':return self.reply(PAGE,kind='text/html')
                if self.path=='/bridge.js':return self.reply(SCRIPT,kind='text/javascript')
                need(self.path=='/poll','bridge_path')
                with lock:
                    q=active[0]
                    if q and not q.get('dispatched'):q['dispatched']=True;obj={k:q[k] for k in ('id','method','params')}
                    else:obj=None
                self.reply(obj)
            except Exception:self.reply({'error':'bridge_denied'},403)
        def do_POST(self):
            try:
                self.connection.settimeout(5)
                n=int(self.headers.get('Content-Length','0'));need(0<n<131072,'bridge_size');body=self.rfile.read(n)
                self.check();obj=json.loads(body)
                if self.path=='/answer':
                    with lock:
                        q=pending.get(obj.get('id'));need(q is not None and 'answer' not in q,'bridge_answer');q['answer']=obj;q['event'].set()
                    return self.reply({'ok':True})
                need(self.path=='/rpc' and obj.get('method') in ALLOWED and isinstance(obj.get('params'),list),'bridge_method')
                request_scope(obj['method'],obj['params'])
                with lock:
                    need(active[0] is None,'bridge_busy');q={'id':secrets.token_hex(16),'method':obj['method'],'params':obj['params'],'event':threading.Event()};active[0]=q;pending[q['id']]=q
                try:
                    need(q['event'].wait(110),'bridge_timeout_ambiguous');self.reply(q['answer'])
                finally:
                    with lock:active[0]=None;pending.pop(q['id'],None)
            except Exception:self.reply({'error':'bridge_failed_do_not_retry_write'},409)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    base='http://127.0.0.1:'+str(server.server_port)
    vault.put('bridge',{'url':base,'token':token,'rpcToken':rpc_token})
    if open_browser:webbrowser.open(base+'/#'+token)
    return server

class Wallet:
    def __init__(self,vault):self.vault=vault
    def rpc(self,method,params):
        need(method in ALLOWED,'wallet_method');b=self.vault.get('bridge');u=urlsplit(b['url'])
        need(u.scheme=='http' and u.hostname=='127.0.0.1' and u.path=='','bridge_address')
        s=requests.Session();s.trust_env=False
        r=s.post(b['url']+'/rpc',json={'method':method,'params':params},headers={'Authorization':'Bearer '+b['rpcToken']},timeout=120,allow_redirects=False)
        need(r.status_code==200,'wallet_transport_ambiguous');o=r.json();need('error' not in o and 'result' in o,'wallet_failed_ambiguous');return o['result']
    def identity(self,account,chain):
        accounts=self.rpc('eth_accounts',[])
        need(isinstance(accounts,list) and accounts and accounts[0].lower()==account.lower(),'wallet_account_changed')
        need(int(self.rpc('eth_chainId',[]),16)==chain,'wallet_chain_changed')
    def connect(self,account,chain):
        self.rpc('eth_requestAccounts',[])
        self.rpc('wallet_switchEthereumChain',[{'chainId':hex(chain)}]);self.identity(account,chain)
