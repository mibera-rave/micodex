"""Actual official HTTP/SIWE/WebSocket client and native-only mint CLI."""
import argparse, datetime as dt, hashlib, json, math, os, re, sqlite3, time
from pathlib import Path
from decimal import Decimal, ROUND_CEILING
import requests, websocket
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_abi import encode, decode
from eth_hash.auto import keccak
from wallet_bridge import Vault, Wallet, Guard, need, serve
import public_client as public
from wallet_adapter import siwe_message, Consent, valid_consent
V='https://vending.miberarave.xyz';M='https://micamp.miberarave.xyz'
C='0x46FaB53A5Ef4E7d0B48ff3c9e4339E15A583F0aB'
ROOT=Path(__file__).resolve().parents[1]
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()
def address(a):need(isinstance(a,str) and re.fullmatch('0x[0-9a-fA-F]{40}',a),'account_format');return Account.from_key if False else a

def runtime_check():
    pins=json.loads((ROOT/'references/provenance.json').read_text())
    for key,host in [('vending',V),('micamp',M)]:
        got=public.asset(host);need(got['sha256']==pins[key]['sha256'] and got['url']==pins[key]['clientURL'],'official_client_drift_review_required')

class Journal:
    def __init__(self,vault):
        self.db=sqlite3.connect(vault.path/'operations.sqlite',timeout=5)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS ops(id TEXT PRIMARY KEY,account TEXT,kind TEXT,state TEXT,details TEXT,at REAL)');self.db.commit()
    def reserve(self,op,account,kind,details):
        need(re.fullmatch('[A-Za-z0-9_-]{8,128}',op),'operation_id')
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            need(not self.db.execute("SELECT 1 FROM ops WHERE account=? AND kind=? AND state!='VERIFIED'",(account.lower(),kind)).fetchone(),'unresolved_operation_reconcile_no_retry')
            if kind=='action':
                row=self.db.execute('SELECT max(at) FROM ops WHERE account=? AND kind=?',(account.lower(),kind)).fetchone()
                need(not row[0] or time.time()-row[0]>=5,'local_slow_mode')
            self.db.execute('INSERT INTO ops VALUES(?,?,?,?,?,?)',(op,account.lower(),kind,'RESERVED',json.dumps(details),time.time()))
    def update(self,op,state,details):
        with self.db:self.db.execute('UPDATE ops SET state=?,details=? WHERE id=?',(state,json.dumps(details),op))
    def read(self,op):
        row=self.db.execute('SELECT account,kind,state,details FROM ops WHERE id=?',(op,)).fetchone();need(row,'operation_missing');return {'account':row[0],'kind':row[1],'state':row[2],'details':json.loads(row[3])}

class HTTP:
    def __init__(self):self.s=requests.Session();self.s.trust_env=False
    def call(self,origin,path,data=None,ticket=None):
        need(origin in (M,V),'http_origin')
        headers={'Accept':'application/json','User-Agent':'MiberaAgentSkill/0.2'}
        if ticket:headers['Authorization']='Bearer '+ticket
        r=self.s.request('GET' if data is None else 'POST',origin+path,json=data,headers=headers,timeout=30,allow_redirects=False)
        need(r.status_code==200 and len(r.content)<4_000_000,'official_http_failed_ambiguous_if_write')
        obj=r.json();need(isinstance(obj,dict) and 'error' not in obj,'official_response_error');return obj

def session_validate(s,account,me=None):
    need(s['account'].lower()==account.lower(),'session_account')
    r=s['response'];need(isinstance(r.get('ticket'),str) and 16<len(r['ticket'])<16384,'session_ticket')
    need(type(r.get('expires')) in (int,float) and r['expires']>time.time()*1000,'session_expired')
    need(isinstance(r.get('miberas'),list) and all(type(x)==int for x in r['miberas']),'session_holdings')
    if me is not None:need(me in r['miberas'],'not_server_owned_character')
    return r

def login(v,w,j,account,op,approved,http=None):
    address(account);need(approved,'explicit_login_approval_required');runtime_check();w.connect(account,80094)
    j.reserve(op,account,'login',{'domain':'micamp.miberarave.xyz'})
    h=http or HTTP();ch=h.call(M,'/door/nonce');text=siwe_message(ch,account,max_age=60)
    # Permanent nonce barrier even when a caller supplies another operation id.
    noncekey='nonce_'+digest([account.lower(),ch['nonce']])
    j.reserve(noncekey,account,'nonce:'+digest(ch['nonce']),{})
    j.update(op,'SIGNING',{'messageSHA256':digest(text)})
    w.identity(account,80094);need(text==siwe_message(ch,account,max_age=60),'challenge_changed')
    sig=w.rpc('personal_sign',['0x'+text.encode().hex(),account])
    need(isinstance(sig,str) and re.fullmatch('0x[0-9a-fA-F]{130}',sig),'signature_format')
    need(Account.recover_message(encode_defunct(text=text),signature=sig).lower()==account.lower(),'signature_recovery')
    need(text==siwe_message(ch,account,max_age=60),'challenge_expired_after_prompt')
    w.identity(account,80094);j.update(op,'SUBMITTING',{'messageSHA256':digest(text)})
    r=h.call(M,'/door/sign',{'message':text,'signature':sig})
    saved={'account':account,'response':r,'cookies':h.s.cookies.get_dict()};v.put('session',saved)
    session_validate(saved,account);j.update(op,'VERIFIED',{'expires':r['expires'],'holdingCount':len(r['miberas'])});j.update(noncekey,'VERIFIED',{})
    return {'authenticated':True,'miberas':r['miberas'],'expires':r['expires'],'paidTransaction':False}

def participate(v,j,account,me,name,op=None,action=None,http=None,socket_factory=None):
    runtime_check();s=v.get('session');r=session_validate(s,account,me)
    need(isinstance(name,str) and 1<=len(name)<=16 and not any(ord(c)<32 for c in name),'name')
    h=http or HTTP();h.s.cookies.update(s.get('cookies',{}));fire=h.call(M,'/fires',ticket=r['ticket']).get('fire')
    need(isinstance(fire,str) and re.fullmatch('[A-Za-z0-9_-]{1,64}',fire),'no_valid_allocated_room')
    sock=(socket_factory or websocket.create_connection)('wss://micamp.miberarave.xyz/fire/'+fire,origin=M,timeout=20,enable_multithread=True)
    def send(o):sock.send(json.dumps(o))
    def receive_until(predicate):
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            sock.settimeout(max(0.1,deadline-time.monotonic()))
            need(r['expires']>time.time()*1000,'session_expired');raw=sock.recv();need(isinstance(raw,str) and len(raw)<131072,'websocket_frame_size')
            f=json.loads(raw);need(isinstance(f,dict),'websocket_frame_schema');need(f.get('t') not in ('error','kick','ban','kicked'),'server_stop')
            if predicate(f):return f
        raise Guard('ack_timeout_ambiguous_no_retry')
    try:
        send({'t':'join','ticket':r['ticket'],'name':name,'me':me,'crew':[],'tz':0})
        welcome=receive_until(lambda f:f.get('t')=='welcome');you=welcome.get('you')
        own=next((p for p in welcome.get('people',[]) if p.get('id')==you),None)
        need(own and own.get('me')==me and isinstance(you,str),'welcome_ownership')
        result={'joined':True,'me':me,'room':fire}
        if action:
            need(op is not None,'action_operation_required');kind=action['kind']
            if kind=='wave':out={'t':'emote','e':'wave'};ack='emoted';matches=lambda f:f.get('e')=='wave'
            elif kind=='chat':
                text=action['text'];need(isinstance(text,str) and 1<=len(text)<=240 and not any(ord(c)<32 for c in text),'chat_bounds')
                need(action.get('approved') is True,'explicit_public_chat_approval');out={'t':'say','text':text};ack='said';matches=lambda f:f.get('text')==text
            elif kind=='move':
                pos=own.get('pos');dx=action['dx'];dy=action['dy'];need(isinstance(pos,list) and len(pos)==2 and all(type(x) in (int,float) and math.isfinite(x) for x in pos+[dx,dy]) and 0<math.hypot(dx,dy)<=24,'short_relative_move_only')
                to=[round(pos[0]+dx),round(pos[1]+dy)];out={'t':'walk','to':to};ack='walked';matches=lambda f:f.get('to')==to
            else:raise Guard('unknown_action')
            j.reserve(op,account,'action',{'kind':kind,'payloadSHA256':digest(out),'me':me})
            j.update(op,'SENDING',{'kind':kind,'payloadSHA256':digest(out),'me':me});send(out)
            f=receive_until(lambda f:f.get('t')==ack and f.get('id')==you and matches(f))
            receipt={'acknowledged':True,'kind':kind,'ackType':f['t'],'me':me,'payloadSHA256':digest(out)}
            j.update(op,'VERIFIED',receipt);result['action']=receipt
        return result
    finally:
        try:send({'t':'part'})
        finally:sock.close()

def calldata(signature,types,args):return '0x'+keccak(signature.encode())[:4].hex()+encode(types,args).hex()
def call(w,signature,types=(),args=(),returns=('uint256',)):
    raw=w.rpc('eth_call',[{'to':C,'data':calldata(signature,types,args)},'latest']);return decode(returns,bytes.fromhex(raw[2:]))[0]
def nonce(w,account):
    a=w.rpc('eth_getTransactionCount',[account,'latest']);b=w.rpc('eth_getTransactionCount',[account,'pending']);need(a==b,'pending_wallet_transaction');return a

def mint(v,w,j,c,picks,expected_runtime,http=None):
    valid_consent(c,int(time.time()));address(c.account);runtime_check();w.connect(c.account,4663)
    h=http or HTTP();reg=h.call(V,'/api/registry');need(public.canonical(reg,picks)==c.traits,'approved_traits_mismatch')
    code=w.rpc('eth_getCode',[C,'latest']);need(code!='0x' and hashlib.sha256(bytes.fromhex(code[2:])).hexdigest()==expected_runtime,'contract_runtime_mismatch')
    need(expected_runtime and re.fullmatch('[0-9a-f]{64}',expected_runtime),'reviewed_runtime_hash_required')
    look=public.look_hash(c.traits);taken=h.call(V,'/api/taken?look='+look+'&buyer='+c.account)
    need(taken.get('taken') is False and call(w,'areTraitsUsed(string)',('string',),(c.traits,),('bool',)) is False,'look_used')
    need(call(w,'paused()',returns=('bool',)) is False,'contract_paused')
    price=h.call(V,'/api/price?chain=4663');t=time.time()
    need(price.get('chainId')==4663 and 0<=t-price['updatedAt']<=min(c.max_quote_age,c.max_usd_age,price['maxPriceAge']),'price_stale')
    p=call(w,'priceWei()');need(int(price['wei'])==p and p>0,'chain_quote_mismatch');value=p*10100//10000
    n=nonce(w,c.account);gasprice=int(w.rpc('eth_gasPrice',[]),16)
    need(gasprice>0 and value<=c.max_total_wei,'price_cap')
    j.reserve(c.operation_id,c.account,'mint',{'nonce':n,'traitsSHA256':digest(c.traits),'runtimeSHA256':expected_runtime})
    permit=h.call(V,'/api/permit',{'chainId':4663,'buyer':c.account,'traits':c.traits})
    deadline=int(permit['deadline']);sig=permit.get('signature','')
    need(permit.get('ok') is True and permit.get('contract','').lower()==C.lower() and time.time()<deadline and re.fullmatch('0x(?:[a-fA-F0-9]{2})+',sig),'permit_scope')
    tx={'from':c.account,'to':C,'chainId':hex(4663),'nonce':n,'value':hex(value),'data':calldata('vend(string,uint256,bytes)',('string','uint256','bytes'),(c.traits,deadline,bytes.fromhex(sig[2:])))}
    w.rpc('eth_call',[tx,'pending']);gas=int(w.rpc('eth_estimateGas',[tx]),16)*120//100
    fee=gas*gasprice;balance=int(w.rpc('eth_getBalance',[c.account,'pending']),16)
    usd=Decimal(str(price['ethUsd']));need(usd>0,'USD_quote')
    cents=int(((Decimal(value+fee)/Decimal(10**18))*usd*100).to_integral_value(rounding=ROUND_CEILING))
    need(fee<=c.max_gas_wei and value+fee<=c.max_total_wei and cents<=c.max_usd_cents and balance-value-fee>=c.reserve_wei,'mint_budget_or_reserve')
    tx.update(gas=hex(gas),gasPrice=hex(gasprice))
    # Recheck exact runtime, pending nonce, price, quote/permit/consent expiry immediately before wallet prompt.
    w.identity(c.account,4663);valid_consent(c,int(time.time()))
    need(nonce(w,c.account)==n and call(w,'priceWei()')==p and not call(w,'paused()',returns=('bool',)) and w.rpc('eth_getCode',[C,'latest'])==code,'mint_state_drift')
    need(time.time()<deadline and 0<=time.time()-price['updatedAt']<=min(c.max_quote_age,c.max_usd_age,price['maxPriceAge']),'expired_before_send')
    w.rpc('eth_call',[tx,'pending'])
    need(int(w.rpc('eth_getBalance',[c.account,'pending']),16)-value-fee>=c.reserve_wei,'reserve_changed')
    need(int(w.rpc('eth_gasPrice',[]),16)<=gasprice,'gas_price_increased_reapprove')
    j.update(c.operation_id,'BROADCASTING',{'nonce':n,'transaction':tx,'runtimeSHA256':expected_runtime,'look':look,'traits':c.traits,'value':value})
    txhash=w.rpc('eth_sendTransaction',[tx]);need(isinstance(txhash,str) and re.fullmatch('0x[0-9a-fA-F]{64}',txhash),'broadcast_ambiguous_no_retry')
    d=j.read(c.operation_id)['details'];d['txHash']=txhash;j.update(c.operation_id,'SUBMITTED',d)
    return reconcile(v,w,j,c.operation_id,http=h)

def reconcile(v,w,j,op,http=None):
    row=j.read(op);need(row['kind']=='mint','mint_operation_required');d=row['details'];need('txHash' in d,'no_hash_ambiguous_reconcile_account_nonce_manually_do_not_retry')
    w.identity(row['account'],4663);txhash=d['txHash'];r=w.rpc('eth_getTransactionReceipt',[txhash]);need(r is not None,'receipt_pending_no_retry')
    need(int(r['status'],16)==1 and r['transactionHash'].lower()==txhash.lower(),'receipt_not_success')
    block=w.rpc('eth_getBlockByNumber',[r['blockNumber'],False]);need(block['hash'].lower()==r['blockHash'].lower(),'noncanonical_receipt')
    head=w.rpc('eth_getBlockByNumber',['latest',False]);need(int(head['number'],16)-int(r['blockNumber'],16)>=2,'wait_two_confirmations_no_retry')
    actual=w.rpc('eth_getTransactionByHash',[txhash]);wanted=d['transaction']
    for k in ('from','to'):need(actual[k].lower()==wanted[k].lower(),'receipt_transaction_identity')
    for k in ('nonce','value','chainId'):need(int(actual[k],16)==int(wanted[k],16),'receipt_transaction_value')
    need(actual['input'].lower()==wanted['data'].lower(),'receipt_calldata')
    need(int(actual['gas'],16)==int(wanted['gas'],16) and int(actual['gasPrice'],16)==int(wanted['gasPrice'],16),'receipt_gas_terms_changed')
    need(int(r['gasUsed'],16)<=int(wanted['gas'],16) and int(r['effectiveGasPrice'],16)<=int(wanted['gasPrice'],16),'receipt_fee_exceeds_approved')
    transfer='0x'+keccak(b'Transfer(address,address,uint256)').hex();vended='0x'+keccak(b'Vended(address,uint256,bytes32,string,address,uint256)').hex()
    ids=[];events=[]
    for log in r['logs']:
        if log['address'].lower()!=C.lower() or log.get('removed'):continue
        topics=log['topics']
        if len(topics)==4 and topics[0].lower()==transfer and int(topics[1],16)==0 and topics[2][-40:].lower()==row['account'][2:].lower():ids.append(int(topics[3],16))
        if len(topics)==4 and topics[0].lower()==vended and topics[1][-40:].lower()==row['account'][2:].lower() and topics[3].lower()==d['look'].lower():
            traits,currency,paid=decode(('string','address','uint256'),bytes.fromhex(log['data'][2:]));need(traits==d['traits'] and int(currency,16)==0 and 0<paid<=d['value'],'vended_log_binding');events.append(int(topics[2],16))
    need(len(ids)==1 and ids==events,'mint_event_pair');token=ids[0]
    need(call(w,'ownerOf(uint256)',('uint256',),(token,),('address',)).lower()==row['account'],'ownerOf_mismatch')
    # Journal reporting separately: ambiguous reporting is not automatically replayed.
    if row['state'] not in ('REPORTING','VERIFIED'):
        j.update(op,'REPORTING',d);(http or HTTP()).call(V,'/api/vended',{'chainId':4663,'txHash':txhash})
    envelope=(http or HTTP()).call(V,'/api/shadow?chain=4663&token='+str(token))
    need(envelope.get('ok') is True and isinstance(envelope.get('shadow'),dict),'indexed_shadow_envelope')
    shadow=envelope['shadow']
    need(int(shadow['tokenId'])==token and int(shadow['chainId'])==4663 and shadow['contract'].lower()==C.lower() and shadow['traits']==d['traits'] and shadow['txHash'].lower()==txhash.lower(),'indexed_shadow_mismatch')
    uri=call(w,'tokenURI(uint256)',('uint256',),(token,),('string',));need(isinstance(uri,str) and len(uri)<16384,'tokenURI_shape')
    d.update(tokenId=token,encodedCharacter=1000000+token,metadataURI_SHA256=digest(uri));j.update(op,'VERIFIED',d)
    return {'verified':True,'txHash':txhash,'tokenId':token,'encodedCharacter':1000000+token,'metadataURI_SHA256':digest(uri),'reportingMayBeAmbiguous':row['state']=='REPORTING'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--state',default=str(Path.home()/'.mibera-agent-v2'))
    sub=p.add_subparsers(dest='cmd',required=True)
    sub.add_parser('preflight');q=sub.add_parser('preview');q.add_argument('--picks',required=True);q.add_argument('--out',default='preview.html')
    sub.add_parser('wallet-bridge');q=sub.add_parser('connect');q.add_argument('--account',required=True);q.add_argument('--chain',type=int,choices=[4663,80094],required=True)
    q=sub.add_parser('inspect');q.add_argument('--account',required=True)
    q=sub.add_parser('mint');q.add_argument('--consent',required=True);q.add_argument('--picks',required=True);q.add_argument('--runtime-sha256',required=True)
    q=sub.add_parser('reconcile');q.add_argument('--op',required=True)
    q=sub.add_parser('login');q.add_argument('--account',required=True);q.add_argument('--op',required=True);q.add_argument('--approve-login',action='store_true')
    for cmd in ('join','wave','chat','move'):
        q=sub.add_parser(cmd);q.add_argument('--account',required=True);q.add_argument('--me',type=int,required=True);q.add_argument('--name',default='Agent-AI')
        if cmd!='join':q.add_argument('--op',required=True)
        if cmd=='chat':q.add_argument('--text',required=True);q.add_argument('--approve-public-chat',action='store_true')
        if cmd=='move':q.add_argument('--dx',type=float,required=True);q.add_argument('--dy',type=float,required=True)
    q=sub.add_parser('actionack');q.add_argument('--op',required=True)
    a=p.parse_args()
    try:
        if a.cmd=='preflight':result=public.preflight();runtime_check();result['version']='0.2.0'
        elif a.cmd=='preview':
            reg=public.jsonget(V+'/api/registry');picks=json.loads(a.picks);Path(a.out).write_text(public.preview(reg,picks),encoding='utf-8');result={'preview':a.out,'finalArt':False}
        else:
            v=Vault(a.state);w=Wallet(v);j=Journal(v)
            if a.cmd=='wallet-bridge':
                server=serve(v);print(json.dumps({'bridge':'running','browserOpened':True,'secretsPrinted':False}),flush=True);server.serve_forever();return
            if a.cmd=='connect':address(a.account);w.connect(a.account,a.chain);result={'connected':True,'chain':a.chain}
            elif a.cmd=='inspect':
                address(a.account);w.connect(a.account,4663);code=w.rpc('eth_getCode',[C,'latest']);result={'contract':C,'runtimeSHA256':hashlib.sha256(bytes.fromhex(code[2:])).hexdigest(),'priceWei':str(call(w,'priceWei()')),'pendingNonce':nonce(w,a.account),'notice':'Review deployed runtime independently before approving its hash.'}
            elif a.cmd=='mint':result=mint(v,w,j,Consent(**json.loads(Path(a.consent).read_text())),json.loads(a.picks),a.runtime_sha256)
            elif a.cmd=='reconcile':result=reconcile(v,w,j,a.op)
            elif a.cmd=='login':result=login(v,w,j,a.account,a.op,a.approve_login)
            elif a.cmd=='actionack':
                row=j.read(a.op);need(row['kind']=='action','action_operation_required');result={'state':row['state'],'receipt':row['details']}
            else:
                action=None
                if a.cmd=='wave':action={'kind':'wave'}
                if a.cmd=='chat':action={'kind':'chat','text':a.text,'approved':a.approve_public_chat}
                if a.cmd=='move':action={'kind':'move','dx':a.dx,'dy':a.dy}
                result=participate(v,j,a.account,a.me,a.name,getattr(a,'op',None),action)
        print(json.dumps({'ok':True,'result':result}))
    except Exception as e:
        # Never print remote exception strings, arguments, signatures or credentials.
        code=str(e) if isinstance(e,Guard) else 'operation_failed_private_state_preserved_no_automatic_retry'
        print(json.dumps({'ok':False,'code':code}));raise SystemExit(1)
if __name__=='__main__':main()
