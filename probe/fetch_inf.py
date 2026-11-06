import requests, json
RPC="https://evm-rpc.infinitedrive.xyz"
S=requests.Session(); _id=0
def batch_aligned(calls):
    global _id; start=_id; payload=[]
    for to,data in calls:
        _id+=1; payload.append({"jsonrpc":"2.0","id":_id,"method":"eth_call","params":[{"to":to,"data":data},"latest"]})
    r=S.post(RPC, json=payload, timeout=60); r.raise_for_status()
    res={x['id']: x.get('result') for x in r.json()}
    return [res[start+i+1] for i in range(len(calls))]
def chunks(lst,n):
    for i in range(0,len(lst),n): yield lst[i:i+n]
def enc_uint(n): return hex(n)[2:].rjust(64,'0')
FACTORY="0x3157C6AcA800D507af95Ab1466adBA3A6F11eE1a"
SEL={"allPairsLength":"0x574f2ba3","allPairs":"0x1e3dd18b","token0":"0x0dfe1681","token1":"0xd21220a7","getReserves":"0x0902f1ac","symbol":"0x95d89b41","decimals":"0x313ce567","totalSupply":"0x18160ddd","name":"0x06fdde03"}
n=int(batch_aligned([(FACTORY, SEL["allPairsLength"])])[0],16); print("pairs",n)
pairs=[]
for chunk in chunks(list(range(n)),100):
    rs=batch_aligned([(FACTORY, SEL["allPairs"]+enc_uint(i)) for i in chunk]); pairs.extend(["0x"+r[-40:] for r in rs])
infos=[]
for chunk in chunks(pairs,80):
    calls=[]
    for p in chunk: calls+=[(p,SEL["token0"]),(p,SEL["token1"]),(p,SEL["getReserves"])]
    rs=batch_aligned(calls)
    for i,p in enumerate(chunk):
        t0="0x"+rs[i*3][-40:]; t1="0x"+rs[i*3+1][-40:]; raw=rs[i*3+2]
        r0=int(raw[2:66],16) if raw and len(raw)>=130 else 0; r1=int(raw[66:130],16) if raw and len(raw)>=130 else 0
        infos.append({"pair":p,"token0":t0,"token1":t1,"reserve0":str(r0),"reserve1":str(r1)})
tokens=sorted(set([x["token0"] for x in infos]+[x["token1"] for x in infos]))
meta={}
def dec_str(x):
    if not x or x=="0x": return None
    try:
        b=bytes.fromhex(x[2:])
        if len(b)>=64:
            ln=int.from_bytes(b[32:64],'big'); return b[64:64+ln].decode('utf-8','replace')
    except: return None
for chunk in chunks(tokens,80):
    calls=[]
    for t in chunk: calls+=[(t,SEL["symbol"]),(t,SEL["name"]),(t,SEL["decimals"]),(t,SEL["totalSupply"])]
    rs=batch_aligned(calls)
    for i,t in enumerate(chunk):
        meta[t]={"symbol":dec_str(rs[i*4]),"name":dec_str(rs[i*4+1]),"decimals":int(rs[i*4+2],16) if rs[i*4+2] and rs[i*4+2]!="0x" else None,"totalSupply":str(int(rs[i*4+3],16)) if rs[i*4+3] and rs[i*4+3]!="0x" else None}
json.dump({"pairs":infos,"tokens":meta}, open('/tmp/inf_pairs.json','w'), indent=1)
for a,m in meta.items(): print(a,m)
print("--- pairs with QOM/USDT/42 placeholder ---")
PH="0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
for p in infos:
    s0=meta.get(p["token0"],{}).get("symbol"); s1=meta.get(p["token1"],{}).get("symbol")
    if s0 in ("QOM","USDT") or s1 in ("QOM","USDT") or PH in (p["token0"],p["token1"]):
        d0=meta[p["token0"]]["decimals"] or 18; d1=meta[p["token1"]]["decimals"] or 18
        print(p["pair"], s0, int(p["reserve0"])/10**d0, "/", s1, int(p["reserve1"])/10**d1)
