import json, math
ql1=json.load(open('/tmp/ql1_pairs.json'))
bs=json.load(open('/tmp/ql1_tokens.json'))
qmeta={k.lower():v for k,v in ql1['tokens'].items()}
holders={t['address_hash'].lower(): int(t['holders_count'] or 0) for t in bs}
bsmeta={t['address_hash'].lower(): t for t in bs}
pair_addrs=set(p['pair'].lower() for p in ql1['pairs'])
WQOM="0xa26dfbf98dd1a32fae56a3d2b2d60a8a41b0bdf0"; QUSDT="0xc276b91c0e8d10260af7b67009d2683bb7776308"
QOM_USD=7.741590213761138e-10

def dec(addr):
    m=qmeta.get(addr) or bsmeta.get(addr) or {}
    d=m.get('decimals')
    return int(d) if d is not None else 18
def supply(addr):
    m=qmeta.get(addr) or {}
    ts=m.get('totalSupply')
    if ts: return int(ts)/10**dec(addr)
    t=bsmeta.get(addr)
    if t and t.get('total_supply'): return int(t['total_supply'])/10**dec(addr)
    return None
def sym(addr):
    m=qmeta.get(addr) or bsmeta.get(addr) or {}
    return m.get('symbol') or '?'

# Build pair list with human reserves
pairs=[]
for p in ql1['pairs']:
    t0=p['token0'].lower(); t1=p['token1'].lower()
    r0=int(p['reserve0'])/10**dec(t0); r1=int(p['reserve1'])/10**dec(t1)
    pairs.append(dict(pair=p['pair'].lower(),t0=t0,t1=t1,r0=r0,r1=r1))

prices={WQOM: dict(usd=QOM_USD, route='Infiniteアンカー (42経由)', liq=None),
        QUSDT: dict(usd=1.0, route='ステーブル $1固定', liq=None)}
# iterative BFS preferring deepest known-side liquidity
for iteration in range(12):
    candidates={}
    for pr in pairs:
        for known, unk, rk, ru in [(pr['t0'],pr['t1'],pr['r0'],pr['r1']),(pr['t1'],pr['t0'],pr['r1'],pr['r0'])]:
            if known in prices and ru>0 and rk>0:
                liq_usd = rk * prices[known]['usd']  # value of known side
                if liq_usd < 0.5: continue  # dust pool floor
                usd = prices[known]['usd'] * rk / ru
                cand = dict(usd=usd, route=f"{sym(unk)}→{sym(known)}", liq=liq_usd, pair=pr['pair'], known=known)
                if unk not in candidates or liq_usd > candidates[unk]['liq']:
                    candidates[unk]=cand
    added=0
    for unk,cand in candidates.items():
        if unk not in prices:
            prices[unk]=cand; added+=1
    if added==0: break
print("priced tokens:", len(prices))
rows=[]
for addr,info in prices.items():
    s=supply(addr); mcap = info['usd']*s if s else None
    rows.append(dict(addr=addr, sym=sym(addr), name=(qmeta.get(addr) or bsmeta.get(addr) or {}).get('name'), price=info['usd'], route=info['route'], liq=info.get('liq'), supply=s, mcap=mcap, holders=holders.get(addr), isLP=addr in pair_addrs))
rows.sort(key=lambda x: -(x['mcap'] or 0))
for r in rows[:60]:
    print(f"{r['sym']:14} ${r['price']:.6g} mcap=${r['mcap']:,.2f}" if r['mcap'] else f"{r['sym']:14} ${r['price']:.6g} mcap=?", f"liq=${r['liq']:,.0f}" if r['liq'] else "anchor", r['route'], "LP" if r['isLP'] else "", "holders", r['holders'], r['addr'])
print("--- priced but no supply / etc", len(rows))
# tokens in bs list with holders>=50 and no price
unpriced=[t for t in bs if t['address_hash'].lower() not in prices]
unpriced_sorted=sorted(unpriced, key=lambda t:-int(t['holders_count'] or 0))
print("unpriced top holders:")
for t in unpriced_sorted[:25]: print(t['symbol'], t['holders_count'], t['address_hash'], "LP" if t['address_hash'].lower() in pair_addrs else "")
# direct WQOM pairs count
wq_pairs=[p for p in pairs if WQOM in (p['t0'],p['t1'])]
print("direct WQOM pairs:", len(wq_pairs), "with liq>= $0.5 on WQOM side:", sum(1 for p in wq_pairs if (p['r0'] if p['t0']==WQOM else p['r1'])*QOM_USD>=0.5))
json.dump(rows, open('/tmp/ql1_priced.json','w'), indent=1, default=str)
