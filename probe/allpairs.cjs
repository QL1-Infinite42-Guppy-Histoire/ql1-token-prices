const { JsonRpcProvider, Contract, formatUnits, ZeroAddress } = require('/home/hatch/workspace/infinite-ql1-wallet/node_modules/ethers');
const PAIR_ABI = ["function getReserves() view returns (uint112,uint112,uint32)", "function token0() view returns (address)", "function token1() view returns (address)"];
const FACTORY_ABI = ["function getPair(address,address) view returns (address)", "function allPairsLength() view returns (uint256)", "function allPairs(uint256) view returns (address)"];
const ERC20_ABI = ["function decimals() view returns (uint8)", "function symbol() view returns (string)"];

async function main(){
  const inf = new JsonRpcProvider("https://evm-rpc.infinitedrive.xyz", 421018);
  const factoryAddr="0x3157C6AcA800D507af95Ab1466adBA3A6F11eE1a";
  const f = new Contract(factoryAddr, FACTORY_ABI, inf);
  const n = Number(await f.allPairsLength());
  console.log("inf pairs", n);
  const symCache={};
  async function sym(addr){
    if(symCache[addr]) return symCache[addr];
    const c=new Contract(addr, ERC20_ABI, inf);
    let s='?'; try{s=await c.symbol();}catch{}
    let d=18; try{d=await c.decimals();}catch{}
    symCache[addr]={s,d}; return symCache[addr];
  }
  for(let i=0;i<n;i++){
    const pa = await f.allPairs(i);
    const p = new Contract(pa, PAIR_ABI, inf);
    try{
      const [t0,t1,res]=await Promise.all([p.token0(),p.token1(),p.getReserves()]);
      const a=await sym(t0), b=await sym(t1);
      const r0=Number(formatUnits(res[0], a.d)), r1=Number(formatUnits(res[1], b.d));
      // print only if involves QOM, USDT, or large reserves in 42/USDT terms rough
      if(a.s.includes('QOM')||b.s.includes('QOM')||a.s==='USDT'||b.s==='USDT'){
        console.log(i, pa, `${a.s}(${r0}) / ${b.s}(${r1})`);
      }
    }catch(e){ console.log(i, pa, "err", e.message.slice(0,80))}
  }
}
main();
