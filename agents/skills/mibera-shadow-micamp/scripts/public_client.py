"""Public GET-only helpers. No wallet, auth challenge, permit or socket calls."""
import argparse,hashlib,html,json,re,time
from pathlib import Path
from urllib.parse import quote,urlsplit
from urllib.request import Request,urlopen
V='https://vending.miberarave.xyz'
M='https://micamp.miberarave.xyz'
ORDER='body hair eyes eyebrows mouth shirt necklace hat glasses mask earrings face_accessory tattoo item background sticker'.split()

def get(url):
    if urlsplit(url).scheme!='https' or urlsplit(url).hostname not in {'vending.miberarave.xyz','micamp.miberarave.xyz'}:
        raise ValueError('unapproved public origin')
    with urlopen(Request(url,headers={'User-Agent':'MiberaAgentSkill/0.2.3 (public read-only)','Accept':'application/json,text/html,*/*'}),timeout=30) as r:
        if urlsplit(r.url).hostname!=urlsplit(url).hostname: raise ValueError('redirect origin')
        b=r.read(8_000_001)
        if len(b)>8_000_000: raise ValueError('response too large')
        return b

def jsonget(url): return json.loads(get(url))

def traitmap(reg):
    out={}
    for t in reg['traits']:
        if t['id'] not in out or t.get('src')=='custom': out[t['id']]=t
    return out

def canonical(reg,picks):
    if not isinstance(picks,dict) or set(picks)-set(ORDER): raise ValueError('unknown category')
    if not picks.get('body'): raise ValueError('body required')
    if picks.get('hat') and picks.get('mask'): raise ValueError('hat/mask conflict')
    tm=traitmap(reg)
    for cat,tid in picks.items():
        if not tid: continue
        t=tm.get(tid)
        if not t or t['cat']!=cat or t['state']!='shelf': raise ValueError('not a shelf trait in category')
        if any(c in picks and picks[c] or c in picks.values() for c in reg.get('conflicts',{}).get(tid,[])):
            raise ValueError('registry conflict')
        if any(c in tid for c in '|=\r\n'): raise ValueError('unsafe trait identifier')
    return 'mibera-shadow/v1'+''.join('|'+c+'='+picks[c] for c in ORDER if picks.get(c))

def look_hash(traits):
    try: from eth_hash.auto import keccak
    except ImportError as e: raise RuntimeError('Optional dependency: pip install "eth-hash[pycryptodome]"; never substitute SHA3') from e
    return '0x'+keccak(traits.encode('utf-8')).hex()

def preview(reg,picks):
    traits=canonical(reg,picks);tm=traitmap(reg);layers=[]
    for cat in ORDER:
        if picks.get(cat):
            for part,l in enumerate(tm[picks[cat]]['layers']): layers.append((l['z'],ORDER.index(cat),part,l['f']))
    tags=[]
    for _,_,_,f in sorted(layers):
        if not isinstance(f,str) or any(s in f for s in ['..',':','\\','?','#']) or f.startswith('/'):
            raise ValueError('unsafe layer path')
        url=V+'/layers/'+'/'.join(quote(s,safe='') for s in f.split('/'))
        tags.append('<img alt="base layer" src="'+html.escape(url,quote=True)+'">')
    return '<!doctype html><meta charset="utf-8"><title>Base-layer study — not final NFT</title><h1>Base-layer study, NOT final NFT</h1><p>Random overlays excluded. Hair/shirt substitutions are not reproduced. Use official Maker for exact base preview.</p><pre>'+html.escape(traits)+'</pre><style>.art{position:relative;width:450px;height:609px}.art img{position:absolute;width:100%;height:100%;object-fit:contain}</style><div class="art">'+''.join(tags)+'</div>'

def asset(host):
    page=get(host).decode('utf-8');paths=re.findall(r'<script[^>]+src="([^"]+\.js)"',page)
    if len(paths)!=1 or not paths[0].startswith('/assets/'): raise ValueError('changed client asset discovery')
    url=host+paths[0];return {'url':url,'sha256':hashlib.sha256(get(url)).hexdigest()}

def preflight():
    reg=jsonget(V+'/api/registry');price=jsonget(V+'/api/price?chain=4663')
    if price['chainId']!=4663 or price['maxPriceAge']<0 or price['updatedAt']>time.time()+30: raise ValueError('price schema/time')
    if price['wei'] is None or time.time()-price['updatedAt']>price['maxPriceAge']: raise ValueError('native quote unavailable/stale')
    response=jsonget(V+'/api/shadow?chain=4663&token=1')
    if response.get('ok') is not True or not isinstance(response.get('shadow'),dict): raise ValueError('shadow response schema')
    sample=response['shadow']
    if sample.get('chainId')!=4663 or str(sample.get('tokenId'))!='1' or sample.get('contract','').lower()!='0x46fab53a5ef4e7d0b48ff3c9e4339e15a583f0ab': raise ValueError('shadow target mismatch')
    world=jsonget(M+'/gen/maps/micamp/map.json')
    return {'mode':'PUBLIC_READ_ONLY','registryVersion':reg['version'],'shelfTraits':sum(t['state']=='shelf' for t in traitmap(reg).values()),'price':price,'sampleExistingToken':{k:sample.get(k) for k in ['chainId','contract','tokenId','traits','txHash']},'mapKeys':sorted(world.keys()),'clients':{'vending':asset(V),'micamp':asset(M)},'writes':0,'signatures':0,'gameActions':0}

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['preflight','preview']);p.add_argument('--picks');p.add_argument('--out',default='preview.html');a=p.parse_args()
    if a.command=='preflight': print(json.dumps(preflight(),indent=2))
    else:
        reg=jsonget(V+'/api/registry');picks=json.loads(a.picks);s=canonical(reg,picks);Path(a.out).write_text(preview(reg,picks),encoding='utf-8');print(json.dumps({'traits':s,'preview':a.out,'finalArt':False}))
if __name__=='__main__': main()
