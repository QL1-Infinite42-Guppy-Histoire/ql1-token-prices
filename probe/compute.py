import json, math
ql1=json.load(open('/tmp/ql1_pairs.json'))
inf=json.load(open('/tmp/inf_pairs.json'))
bs=json.load(open('/tmp/ql1_tokens.json'))
holders={t['address_hash'].lower(): int(t['holders_count'] or 0) for t in bs}
bsmeta={t['address_hash'].lower(): t for t in bs}

def reserves(p, meta):
    d0=(meta.get(p['token0']) or {}).get('decimals') or 18
    d1=(meta.get(p['token1']) or {}).get('decimals') or 18
    return int(p['reserve0'])/10**d0, int(p['reserve1'])/10**d1

# Infinite anchor
imeta={k.lower():v for k,v in inf['tokens'].items()}
def find_pair(data, a, b):
    a=a.lower(); b=b.lower()
    for p in data['pairs']:
        if {p['token0'].lower(), p['token1'].lower()}=={a,b}: return p
    return None
USDT="0xc2684966e5c95b2bc636fb4a1f3da9ad23d94753"; PH="0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"; QOMI="0x53465cbbba5b14f5dc00794330f0f4afb30eaa1d"; FISH="0x2c32120a12b754272d9e85c57f64b50ca2c43513"
p=find_pair(inf, PH, USDT); r=reserves(p, imeta)
# token0 is USDT in that pair? check order
print("42/USDT pair tokens", p['token0'], p['token1'], r)
# price42 = USDT amount per 42
if p['token0'].lower()==USDT: price42=r[0]/r[1]
else: price42=r[1]/r[0]
print("price42 USD", price42)
p=find_pair(inf, QOMI, PH); r=reserves(p, imeta); print("QOM/42", p['token0'], r)
qom_per_42 = r[0]/r[1] if p['token0'].lower()==QOMI else r[1]/r[0]
priceQOM_direct = price42 / qom_per_42
print("QOM USD direct via 42", priceQOM_direct, "QOM per 42", qom_per_42)
p=find_pair(inf, FISH, USDT); r=reserves(p, imeta); fish_usd = r[1]/r[0] if p['token1'].lower()==USDT else r[0]/r[1]; print("FISH USD", fish_usd, r)
p=find_pair(inf, FISH, QOMI); r=reserves(p, imeta); qom_per_fish = r[1]/r[0] if p['token1'].lower()==QOMI else r[0]/r[1]; print("QOM per FISH", qom_per_fish, r)
priceQOM_fish = fish_usd / qom_per_fish
print("QOM USD via FISH", priceQOM_fish, "ratio direct/fish", priceQOM_direct/priceQOM_fish)

# QL1 reference
qmeta={k.lower():v for k,v in ql1['tokens'].items()}
WQOM="0xa26dfbf98dd1a32fae56a3d2b2d60a8a41b0bdf0"; QUSDT="0xc276b91c0e8d10260af7b67009d2683bb7776308"
p=find_pair(ql1, WQOM, QUSDT); r=reserves(p, qmeta); print("QL1 WQOM/qUSDT", p['token0'], r)
qom_in_qusdt = r[1]/r[0] if p['token1'].lower()==QUSDT else r[0]/r[1]
print("QL1 pool QOM USD if qUSDT=$1:", qom_in_qusdt, " divergence vs Inf anchor x", qom_in_qusdt/priceQOM_direct)
