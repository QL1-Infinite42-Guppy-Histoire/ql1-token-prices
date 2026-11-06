import json
ql1=json.load(open('/tmp/ql1_pairs.json')); bs=json.load(open('/tmp/ql1_tokens.json'))
qmeta={k.lower():v for k,v in ql1['tokens'].items()}
bsmeta={t['address_hash'].lower(): t for t in bs}
holders={t['address_hash'].lower(): int(t['holders_count'] or 0) for t in bs}
pair_addrs=set(p['pair'].lower() for p in ql1['pairs'])
WQOM="0xa26dfbf98dd1a32fae56a3d2b2d60a8a41b0bdf0"; QUSDT="0xc276b91c0e8d10260af7b67009d2683bb7776308"; QUSDC="0xb0a125e9673dc8e12bbcd0769c1257cf4a836d54"; QDAI="0x8cb00ee173ae1c35d66118b7e08a69a0d4da06f2"
QOM_USD=7.741590213761138e-10
ANCHORS={WQOM:(QOM_USD,'Infiniteアンカー'), QUSDT:(1.0,'$1固定'), QUSDC:(1.0,'$1固定'), QDAI:(1.0,'$1固定')}
def dec(a):
    m=qmeta.get(a) or bsmeta.get(a) or {}; d=m.get('decimals'); return int(d) if d is not None else 18
def sym(a):
    m=qmeta.get(a) or bsmeta.get(a) or {}; return m.get('symbol') or '?'
def name(a):
    m=qmeta.get(a) or bsmeta.get(a) or {}; return m.get('name') or ''
def supply(a):
    m=qmeta.get(a)
    if m and m.get('totalSupply'): return int(m['totalSupply'])/10**dec(a)
    t=bsmeta.get(a)
    if t and t.get('total_supply'): return int(t['total_supply'])/10**dec(a)
    return None
pairs=[]
for p in ql1['pairs']:
    t0=p['token0'].lower(); t1=p['token1'].lower()
    pairs.append(dict(pair=p['pair'].lower(),t0=t0,t1=t1,r0=int(p['reserve0'])/10**dec(t0),r1=int(p['reserve1'])/10**dec(t1)))

def direct_prices(anchor_map):
    # returns addr -> best cand + all cands
    best={}; allc={}
    for pr in pairs:
        for known,unk,rk,ru in [(pr['t0'],pr['t1'],pr['r0'],pr['r1']),(pr['t1'],pr['t0'],pr['r1'],pr['r0'])]:
            if known in anchor_map and rk>0 and ru>0:
                kusd, kroute = anchor_map[known]
                liq=rk*kusd
                if liq<0.5: continue
                cand=dict(usd=kusd*rk/ru, route=f"{sym(unk)}→{sym(known)}", liq=liq, pair=pr['pair'], via=sym(known))
                allc.setdefault(unk,[]).append(cand)
                if unk not in best or liq>best[unk]['liq']: best[unk]=cand
    return best, allc

best, allc = direct_prices(ANCHORS)
# divergence check
for addr in list(best):
    cs=allc[addr]
    if len(cs)>=2:
        ps=[c['usd'] for c in cs]
        if max(ps)/min(ps)>3:
            best[addr]=dict(best[addr]); best[addr]['diverge']=[(c['via'],c['usd'],c['liq']) for c in cs]
# second hop via reliable intermediates (liq>=500, not divergent)
inter={a:(best[a]['usd'],'2段') for a in best if best[a]['liq']>=500 and a not in ANCHORS and not best[a].get('diverge')}
anchor2=dict(ANCHORS); anchor2.update(inter)
best2, allc2 = direct_prices(anchor2)
for a,c in best2.items():
    if a not in best and a not in ANCHORS:
        c=dict(c); c['hop']=2; best[a]=c
for a in ANCHORS:
    best[a]=dict(usd=ANCHORS[a][0], route=ANCHORS[a][1], liq=None, pair=None, via='アンカー')
rows=[]
for addr,info in best.items():
    s=supply(addr); rows.append(dict(addr=addr,sym=sym(addr),name=name(addr),price=info['usd'],route=info.get('route'),liq=info.get('liq'),supply=s,mcap=info['usd']*s if s else None,holders=holders.get(addr),isLP=addr in pair_addrs,diverge=info.get('diverge'),hop=info.get('hop',1)))
rows.sort(key=lambda x:-(x['mcap'] or 0))
for r in rows[:50]:
    print(f"{r['sym']:12} ${r['price']:.6g} mcap=${r['mcap']:,.0f}" if r['mcap'] is not None else f"{r['sym']:12} ${r['price']:.6g}", f"liq=${r['liq']:,.0f}" if r['liq'] else "anchor", r['route'], "DIV" if r['diverge'] else "", "hop2" if r['hop']==2 else "", "holders", r['holders'])
print("priced total", len(rows))
# LP token values
print("--- top direct WQOM liq pairs ---")
wq=[p for p in pairs if WQOM in (p['t0'],p['t1'])]
wq.sort(key=lambda p: -((p['r0'] if p['t0']==WQOM else p['r1'])*QOM_USD))
for p in wq[:15]:
    other = p['t1'] if p['t0']==WQOM else p['t0']
    wq_amt = p['r0'] if p['t0']==WQOM else p['r1']
    print(sym(other), f"WQOM liq ${wq_amt*QOM_USD:,.0f}", p['pair'])
json.dump(rows, open('/tmp/ql1_priced_v2.json','w'), indent=1, default=str)
