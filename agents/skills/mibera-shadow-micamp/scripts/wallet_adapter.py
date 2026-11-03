"""Strict one-mint consent and official SIWE validation; no abstract adapter."""
from dataclasses import dataclass
import datetime as dt,re,time
CONTRACT='0x46FaB53A5Ef4E7d0B48ff3c9e4339E15A583F0aB'
ADDRESS=re.compile(r'^0x[0-9a-fA-F]{40}$')
STATEMENT='henlo. sign in to micamp. no fee, no transaction.'
@dataclass(frozen=True)
class Consent:
    operation_id:str
    approved:bool
    count:int
    account:str
    chain:int
    contract:str
    traits:str
    max_total_wei:int
    max_gas_wei:int
    reserve_wei:int
    max_usd_cents:int
    max_quote_age:int
    max_usd_age:int
    expires:int

def valid_consent(c,now):
    if c.approved is not True or type(c.count)!=int or c.count!=1 or c.chain!=4663 or c.contract.lower()!=CONTRACT.lower():raise ValueError('one_mint_consent')
    if not ADDRESS.fullmatch(c.account) or not re.fullmatch('[A-Za-z0-9_-]{8,128}',c.operation_id):raise ValueError('account_operation')
    if not c.traits.startswith('mibera-shadow/v1|body=') or any(x in c.traits for x in '\r\n'):raise ValueError('canonical_traits')
    vals=[c.max_total_wei,c.max_gas_wei,c.max_usd_cents,c.max_quote_age,c.max_usd_age]
    if any(type(x)!=int or x<=0 for x in vals) or type(c.reserve_wei)!=int or c.reserve_wei<0 or type(c.expires)!=int or not now<c.expires:raise ValueError('budget_expiry')

def siwe_message(ch,account,now=None,max_age=60):
    now=time.time() if now is None else now
    if not ADDRESS.fullmatch(account):raise ValueError('account')
    if set(ch)!={'domain','uri','chainId','statement','nonce','issuedAt'}:raise ValueError('challenge_schema')
    if ch['domain']!='micamp.miberarave.xyz' or ch['uri']!='https://micamp.miberarave.xyz' or ch['chainId']!=80094 or ch['statement']!='door.statement':raise ValueError('challenge_binding')
    if not isinstance(ch['nonce'],str) or not re.fullmatch('[A-Za-z0-9]{8,128}',ch['nonce']):raise ValueError('nonce')
    issued=ch['issuedAt']
    if not isinstance(issued,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z',issued):raise ValueError('issuedAt')
    stamp=dt.datetime.fromisoformat(issued.replace('Z','+00:00')).timestamp()
    if not 0<=now-stamp<=max_age or not 0<max_age<=60:raise ValueError('challenge_expired')
    issued=dt.datetime.fromtimestamp(stamp,dt.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
    return f'micamp.miberarave.xyz wants you to sign in with your Ethereum account:\n{account}\n\n{STATEMENT}\n\nURI: https://micamp.miberarave.xyz\nVersion: 1\nChain ID: 80094\nNonce: {ch["nonce"]}\nIssued At: {issued}'
