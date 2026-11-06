import requests, json, sys
RPC="https://evm-rpc-ql1.mschihuahua.org"
S=requests.Session()
_id=0
def batch(calls):
    # calls: list of (to, data)
    global _id
    payload=[]
    for to,data in calls:
        _id+=1
        payload.append({"jsonrpc":"2.0","id":_id,"method":"eth_call","params":[{"to":to,"data":data},"latest"]})
    r=S.post(RPC, json=payload, timeout=60); r.raise_for_status()
    out=r.json()
    out_sorted=sorted(out, key=lambda x: x['id'])
    # ids are sequential in order sent; we incremented globally, need map
    return out_sorted

def batch_aligned(calls):
    # returns results aligned to calls order
    global _id
    start=_id
    payload=[]
    for to,data in calls:
        _id+=1
        payload.append({"jsonrpc":"2.0","id":_id,"method":"eth_call","params":[{"to":to,"data":data},"latest"]})
    r=S.post(RPC, json=payload, timeout=60); r.raise_for_status()
    res={x['id']: x.get('result') for x in r.json()}
    return [res[start+i+1] for i in range(len(calls))]

def chunks(lst,n):
    for i in range(0,len(lst),n): yield lst[i:i+n]

def enc_uint(n): return hex(n)[2:].rjust(64,'0')
def enc_addr(a): return a.lower().replace('0x','').rjust(64,'0')

FACTORY="0x475f361993D6FAcBF32fB82B66be0fB40f3d974C"
SEL={"allPairsLength":"0x574f2ba3","allPairs":"0x1e3dd18b","getPair":"0xe6a43905","token0":"0x0dfe1681","token1":"0xd21220a7","getReserves":"0x0902f1ac","symbol":"0x95d89b41","decimals":"0x313ce567","totalSupply":"0x18160ddd","name":"0x06fdde03"}

# length
res=batch_aligned([(FACTORY, SEL["allPairsLength"])])[0]
n=int(res,16); print("pairs",n, flush=True)
pairs=[]
for chunk in chunks(list(range(n)),100):
    rs=batch_aligned([(FACTORY, SEL["allPairs"]+enc_uint(i)) for i in chunk])
    pairs.extend(["0x"+r[-40:] for r in rs])
print("got pair addrs", len(pairs), flush=True)
# token0/token1/reserves
infos=[]
for chunk in chunks(pairs,80):
    calls=[]
    for p in chunk: calls += [(p,SEL["token0"]),(p,SEL["token1"]),(p,SEL["getReserves"])]
    rs=batch_aligned(calls)
    for i,p in enumerate(chunk):
        t0="0x"+rs[i*3][-40:]; t1="0x"+rs[i*3+1][-40:]
        raw=rs[i*3+2]
        if raw and len(raw)>=130:
            r0=int(raw[2:66],16); r1=int(raw[66:130],16)
        else: r0=r1=0
        infos.append({"pair":p,"token0":t0,"token1":t1,"reserve0":str(r0),"reserve1":str(r1)})
print("pair infos", len(infos), flush=True)
tokens=sorted(set([x["token0"] for x in infos]+[x["token1"] for x in infos]))
print("unique tokens in pairs", len(tokens), flush=True)
meta={}
for chunk in chunks(tokens,80):
    calls=[]
    for t in chunk: calls += [(t,SEL["symbol"]),(t,SEL["name"]),(t,SEL["decimals"]),(t,SEL["totalSupply"])]
    rs=batch_aligned(calls)
    for i,t in enumerate(chunk):
        def dec_str(x):
            if not x or x=="0x": return None
            try:
                b=bytes.fromhex(x[2:])
                # dynamic string: offset,length,data
                if len(b)>=64:
                    ln=int.from_bytes(b[32:64],'big'); return b[64:64+ln].decode('utf-8','replace')
                return None
            except: return None
        sym=dec_str(rs[i*4]); nm=dec_str(rs[i*4+1])
        dec=int(rs[i*4+2],16) if rs[i*4+2] and rs[i*4+2]!="0x" else None
        ts=int(rs[i*4+3],16) if rs[i*4+3] and rs[i*4+3]!="0x" else None
        meta[t]={"symbol":sym,"name":nm,"decimals":dec,"totalSupply":str(ts) if ts is not None else None}
json.dump({"pairs":infos,"tokens":meta}, open('/tmp/ql1_pairs.json','w'), indent=1)
print("saved")
