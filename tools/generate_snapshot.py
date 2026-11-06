#!/usr/bin/env python3
"""Generate docs/snapshot.json for the QL1 token price site.

Method (all verified on-chain 2026-11-06):
- 42 USD price from the Infinite (42 Chain) 42/USDT Don't Panic pair.
- QOM USD anchor from the Infinite QOM/42 pair (QOM token on 42 Chain).
  Cross-checked via FISH: FISH/USDT x FISH/QOM pairs agree within ~0.1%.
- QL1 reference (Ave-style) QOM price from the QL1 WQOM/qUSDT QomSwap pair
  with qUSDT = $1. It diverges ~4.5x from the Infinite anchor; the site
  uses the Infinite anchor, per the owner's specification.
- Each QL1 token is priced from its deepest direct QomSwap pair against
  an anchor token (WQOM at the Infinite anchor, qUSDT/qUSDC/qDAI at $1),
  with a $0.5 minimum anchor-side liquidity. A second hop is allowed via
  intermediates whose own pool is >= $500 and non-divergent.
- Market cap = price x total supply (FDV basis).
"""
import requests, json, sys, datetime

INF_RPC = "https://evm-rpc.infinitedrive.xyz"
QL1_RPC = "https://evm-rpc-ql1.mschihuahua.org"
BS = "https://scan.qom.network/api/v2"
INF_FACTORY = "0x3157C6AcA800D507af95Ab1466adBA3A6F11eE1a"
QL1_FACTORY = "0x475f361993D6FAcBF32fB82B66be0fB40f3d974C"
SEL = {"allPairsLength":"0x574f2ba3","allPairs":"0x1e3dd18b","token0":"0x0dfe1681","token1":"0xd21220a7",
       "getReserves":"0x0902f1ac","symbol":"0x95d89b41","decimals":"0x313ce567","totalSupply":"0x18160ddd","name":"0x06fdde03"}

class Rpc:
    def __init__(self, url):
        self.url = url; self.s = requests.Session(); self._id = 0
    def batch(self, calls):
        start = self._id; payload = []
        for to, data in calls:
            self._id += 1
            payload.append({"jsonrpc":"2.0","id":self._id,"method":"eth_call","params":[{"to":to,"data":data},"latest"]})
        r = self.s.post(self.url, json=payload, timeout=90); r.raise_for_status()
        res = {x['id']: x.get('result') for x in r.json()}
        return [res[start+i+1] for i in range(len(calls))]
    def block(self):
        r = self.s.post(self.url, json={"jsonrpc":"2.0","id":1,"method":"eth_blockNumber","params":[]}, timeout=30)
        return int(r.json()['result'], 16)

def chunks(lst, n):
    for i in range(0, len(lst), n): yield lst[i:i+n]
def enc_uint(n): return hex(n)[2:].rjust(64, '0')
def dec_str(x):
    if not x or x == "0x": return None
    try:
        b = bytes.fromhex(x[2:])
        if len(b) >= 64:
            ln = int.from_bytes(b[32:64], 'big'); return b[64:64+ln].decode('utf-8', 'replace')
    except Exception: return None
    return None

def fetch_chain(rpc_url, factory):
    rpc = Rpc(rpc_url)
    n = int(rpc.batch([(factory, SEL["allPairsLength"])])[0], 16)
    pairs = []
    for chunk in chunks(list(range(n)), 100):
        rs = rpc.batch([(factory, SEL["allPairs"] + enc_uint(i)) for i in chunk])
        pairs.extend(["0x" + r[-40:] for r in rs])
    infos = []
    for chunk in chunks(pairs, 80):
        calls = []
        for p in chunk: calls += [(p, SEL["token0"]), (p, SEL["token1"]), (p, SEL["getReserves"]), (p, SEL["totalSupply"])]
        rs = rpc.batch(calls)
        for i, p in enumerate(chunk):
            raw = rs[i*4+2]
            r0 = int(raw[2:66], 16) if raw and len(raw) >= 130 else 0
            r1 = int(raw[66:130], 16) if raw and len(raw) >= 130 else 0
            lp_ts = int(rs[i*4+3], 16) if rs[i*4+3] and rs[i*4+3] != "0x" else None
            infos.append({"pair": p, "token0": "0x" + rs[i*4][-40:], "token1": "0x" + rs[i*4+1][-40:],
                          "reserve0": str(r0), "reserve1": str(r1), "lpSupplyRaw": str(lp_ts) if lp_ts is not None else None})
    tokens = sorted(set([x["token0"] for x in infos] + [x["token1"] for x in infos]))
    meta = {}
    for chunk in chunks(tokens, 80):
        calls = []
        for t in chunk: calls += [(t, SEL["symbol"]), (t, SEL["name"]), (t, SEL["decimals"]), (t, SEL["totalSupply"])]
        rs = rpc.batch(calls)
        for i, t in enumerate(chunk):
            meta[t] = {"symbol": dec_str(rs[i*4]), "name": dec_str(rs[i*4+1]),
                       "decimals": int(rs[i*4+2], 16) if rs[i*4+2] and rs[i*4+2] != "0x" else None,
                       "totalSupply": str(int(rs[i*4+3], 16)) if rs[i*4+3] and rs[i*4+3] != "0x" else None}
    return {"pairs": infos, "tokens": meta}, rpc.block()

def fetch_blockscout_tokens():
    items = []; url = BS + "/tokens?type=ERC-20"
    while url:
        r = requests.get(url, timeout=30); r.raise_for_status(); j = r.json()
        items.extend(j['items'])
        nxt = j.get('next_page_params')
        if not nxt: break
        from urllib.parse import urlencode
        url = BS + "/tokens?type=ERC-20&" + urlencode(nxt)
        if len(items) > 800: break
    return items

def main(out_path):
    inf, inf_block = fetch_chain(INF_RPC, INF_FACTORY)
    ql1, ql1_block = fetch_chain(QL1_RPC, QL1_FACTORY)
    bs = fetch_blockscout_tokens()
    bsmeta = {t['address_hash'].lower(): t for t in bs}
    holders = {a: int(t['holders_count'] or 0) for a, t in bsmeta.items()}
    imeta = {k.lower(): v for k, v in inf['tokens'].items()}
    qmeta = {k.lower(): v for k, v in ql1['tokens'].items()}
    pair_addrs = set(p['pair'].lower() for p in ql1['pairs'])

    def reserves(data, p):
        meta = imeta if data is inf else qmeta
        d0 = (meta.get(p['token0'].lower()) or {}).get('decimals') or 18
        d1 = (meta.get(p['token1'].lower()) or {}).get('decimals') or 18
        return int(p['reserve0'])/10**d0, int(p['reserve1'])/10**d1
    def find_pair(data, a, b):
        a, b = a.lower(), b.lower()
        for p in data['pairs']:
            if {p['token0'].lower(), p['token1'].lower()} == {a, b}: return p
        return None
    USDT = "0xc2684966e5c95b2bc636fb4a1f3da9ad23d94753"; PH = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
    QOMI = "0x53465cbbba5b14f5dc00794330f0f4afb30eaa1d"; FISH = "0x2c32120a12b754272d9e85c57f64b50ca2c43513"
    p = find_pair(inf, PH, USDT); r = reserves(inf, p)
    price42 = r[0]/r[1] if p['token0'].lower() == USDT else r[1]/r[0]
    p = find_pair(inf, QOMI, PH); r = reserves(inf, p)
    qom_per_42 = r[0]/r[1] if p['token0'].lower() == QOMI else r[1]/r[0]
    qom_usd = price42 / qom_per_42
    p = find_pair(inf, FISH, USDT); r = reserves(inf, p)
    fish_usd = r[1]/r[0] if p['token1'].lower() == USDT else r[0]/r[1]
    p = find_pair(inf, FISH, QOMI); r = reserves(inf, p)
    qom_per_fish = r[1]/r[0] if p['token1'].lower() == QOMI else r[0]/r[1]
    qom_usd_fish = fish_usd / qom_per_fish

    WQOM = "0xa26dfbf98dd1a32fae56a3d2b2d60a8a41b0bdf0"; QUSDT = "0xc276b91c0e8d10260af7b67009d2683bb7776308"
    QUSDC = "0xb0a125e9673dc8e12bbcd0769c1257cf4a836d54"; QDAI = "0x8cb00ee173ae1c35d66118b7e08a69a0d4da06f2"
    p = find_pair(ql1, WQOM, QUSDT); r = reserves(ql1, p)
    qom_ql1_pool = r[1]/r[0] if p['token1'].lower() == QUSDT else r[0]/r[1]  # qUSDT = $1 assumption

    def dec(a):
        m = qmeta.get(a) or bsmeta.get(a) or {}; d = m.get('decimals')
        return int(d) if d is not None else 18
    def sym(a):
        m = qmeta.get(a) or bsmeta.get(a) or {}; return m.get('symbol') or '?'
    def nm(a):
        m = qmeta.get(a) or bsmeta.get(a) or {}; return m.get('name') or ''
    def supply(a):
        m = qmeta.get(a)
        if m and m.get('totalSupply'): return int(m['totalSupply'])/10**dec(a)
        t = bsmeta.get(a)
        if t and t.get('total_supply'): return int(t['total_supply'])/10**dec(a)
        return None
    pairs = []
    pair_by_addr = {}
    for p in ql1['pairs']:
        t0, t1 = p['token0'].lower(), p['token1'].lower()
        pr = dict(pair=p['pair'].lower(), t0=t0, t1=t1,
                  r0=int(p['reserve0'])/10**dec(t0), r1=int(p['reserve1'])/10**dec(t1),
                  lpSupply=int(p['lpSupplyRaw'])/10**18 if p.get('lpSupplyRaw') else None)
        pairs.append(pr); pair_by_addr[pr['pair']] = pr
    ANCHORS = {WQOM: (qom_usd, 'Infiniteアンカー'), QUSDT: (1.0, '$1固定'), QUSDC: (1.0, '$1固定'), QDAI: (1.0, '$1固定')}
    def direct(anchor_map):
        best, allc = {}, {}
        for pr in pairs:
            for known, unk, rk, ru in [(pr['t0'], pr['t1'], pr['r0'], pr['r1']), (pr['t1'], pr['t0'], pr['r1'], pr['r0'])]:
                if known in anchor_map and rk > 0 and ru > 0:
                    kusd = anchor_map[known][0]; liq = rk * kusd
                    if liq < 0.5: continue
                    cand = dict(usd=kusd * rk / ru, route=f"{sym(unk)}→{sym(known)}", via=sym(known), viaAddr=known,
                                liq=liq, pair=pr['pair'], reserveKnown=rk, reserveToken=ru)
                    allc.setdefault(unk, []).append(cand)
                    if unk not in best or liq > best[unk]['liq']: best[unk] = cand
        return best, allc
    best, allc = direct(ANCHORS)
    for a in list(best):
        cs = allc[a]
        if len(cs) >= 2:
            ps = [c['usd'] for c in cs]
            if max(ps)/min(ps) > 3:
                best[a] = dict(best[a]); best[a]['diverge'] = cs
    inter = {a: (best[a]['usd'], '2段') for a in best if best[a]['liq'] >= 500 and a not in ANCHORS and not best[a].get('diverge')}
    anchor2 = dict(ANCHORS); anchor2.update(inter)
    best2, _ = direct(anchor2)
    for a, c in best2.items():
        if a not in best and a not in ANCHORS:
            c = dict(c); c['hop'] = 2; c['route'] = c['route'] + "→…→アンカー"; best[a] = c
    for a in ANCHORS: best[a] = dict(usd=ANCHORS[a][0], route=ANCHORS[a][1], via='アンカー', liq=None, pair=None)
    tokens = []
    for addr, info in best.items():
        s = supply(addr)
        tokens.append(dict(address=addr, symbol=sym(addr), name=nm(addr), decimals=dec(addr), totalSupply=s,
                           holders=holders.get(addr), icon=(bsmeta.get(addr) or {}).get('icon_url'),
                           priceUsd=info['usd'], priceQom=info['usd']/qom_usd if addr != WQOM else 1,
                           mcap=info['usd']*s if s else None, route=info.get('route'), via=info.get('via'),
                           pair=info.get('pair'), liqUsd=info.get('liq'), hop=info.get('hop', 1),
                           reserveKnown=info.get('reserveKnown'), reserveToken=info.get('reserveToken'),
                           diverge=[dict(via=c['via'], usd=c['usd'], liq=c['liq']) for c in info['diverge']] if info.get('diverge') else None,
                           isLP=addr in pair_addrs))
    # LP token values (pair contracts themselves)
    price_map = {t['address']: t['priceUsd'] for t in tokens}
    for pr in pairs:
        pa = pr['pair']
        if pa in price_map: continue
        if pr['t0'] in price_map and pr['t1'] in price_map and pr['lpSupply']:
            val = pr['r0']*price_map[pr['t0']] + pr['r1']*price_map[pr['t1']]
            if val >= 0.5:
                tokens.append(dict(address=pa, symbol=sym(pa) if sym(pa) != '?' else 'QSWAP-V2', name=f"QomSwap LP {sym(pr['t0'])}/{sym(pr['t1'])}",
                                   decimals=18, totalSupply=pr['lpSupply'], holders=holders.get(pa),
                                   icon=(bsmeta.get(pa) or {}).get('icon_url'), priceUsd=val/pr['lpSupply'],
                                   priceQom=(val/pr['lpSupply'])/qom_usd, mcap=val, route=f"LP裏付け ({sym(pr['t0'])}/{sym(pr['t1'])})",
                                   via='LP', pair=pa, liqUsd=val/2, hop=1, reserveKnown=None, reserveToken=None, diverge=None, isLP=True))
    tokens.sort(key=lambda x: -(x['mcap'] or 0))
    priced_addrs = set(t['address'] for t in tokens)
    unpriced = []
    for t in bs:
        a = t['address_hash'].lower()
        if a not in priced_addrs:
            unpriced.append(dict(address=a, symbol=t.get('symbol'), name=t.get('name'), holders=int(t['holders_count'] or 0),
                                 totalSupply=int(t['total_supply'])/10**(int(t['decimals']) if t.get('decimals') else 18) if t.get('total_supply') else None,
                                 isLP=a in pair_addrs))
    unpriced.sort(key=lambda x: -(x['holders'] or 0))
    snap = dict(generatedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                infBlock=inf_block, ql1Block=ql1_block,
                anchors=dict(price42=price42, qomUsd=qom_usd, qomUsdViaFish=qom_usd_fish, fishUsd=fish_usd,
                             qomQl1Pool=qom_ql1_pool, divergence=qom_ql1_pool/qom_usd),
                stats=dict(ql1Pairs=len(pairs), bsTokens=len(bs), priced=len(tokens), unpriced=len(unpriced)),
                tokens=tokens, unpriced=unpriced)
    json.dump(snap, open(out_path, 'w'), indent=1, ensure_ascii=False)
    print("wrote", out_path, snap['stats'], "QOM anchor", qom_usd, "viaFish", qom_usd_fish, "QL1pool", qom_ql1_pool)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "docs/snapshot.json")
