const { JsonRpcProvider, Contract, formatUnits, ZeroAddress } = require('/home/hatch/workspace/infinite-ql1-wallet/node_modules/ethers');

const INF_RPC = "https://evm-rpc.infinitedrive.xyz";
const QL1_RPC = "https://evm-rpc-ql1.mschihuahua.org";

const PAIR_ABI = ["function getReserves() view returns (uint112,uint112,uint32)", "function token0() view returns (address)", "function token1() view returns (address)"];
const FACTORY_ABI = ["function getPair(address,address) view returns (address)", "function allPairsLength() view returns (uint256)"];
const ERC20_ABI = ["function decimals() view returns (uint8)", "function symbol() view returns (string)", "function name() view returns (string)", "function totalSupply() view returns (uint256)"];

async function pairInfo(provider, pairAddr, label){
  if(!pairAddr || pairAddr===ZeroAddress){ console.log(label, "NO PAIR"); return null; }
  const p = new Contract(pairAddr, PAIR_ABI, provider);
  try{
    const [t0,t1,res] = await Promise.all([p.token0(), p.token1(), p.getReserves()]);
    // get decimals for each
    const c0 = new Contract(t0, ERC20_ABI, provider); const c1 = new Contract(t1, ERC20_ABI, provider);
    const [d0,d1,s0,s1] = await Promise.all([c0.decimals().catch(()=>18), c1.decimals().catch(()=>18), c0.symbol().catch(()=>'?'), c1.symbol().catch(()=>'?')]);
    const r0 = Number(formatUnits(res[0], d0)); const r1 = Number(formatUnits(res[1], d1));
    console.log(`\n${label} pair=${pairAddr}`);
    console.log(`  token0 ${s0} ${t0} dec${d0} reserve=${r0}`);
    console.log(`  token1 ${s1} ${t1} dec${d1} reserve=${r1}`);
    if(r0>0 && r1>0) console.log(`  price token0 in token1 = ${r1/r0} ; token1 in token0 = ${r0/r1}`);
    return {t0,t1,s0,s1,d0,d1,r0,r1};
  }catch(e){ console.log(label, "ERR", e.message.slice(0,200)); return null; }
}

(async()=>{
  const inf = new JsonRpcProvider(INF_RPC, 421018);
  const ql1 = new JsonRpcProvider(QL1_RPC, 766);
  console.log("inf block", await inf.getBlockNumber());
  console.log("ql1 block", await ql1.getBlockNumber());

  const INF_FACTORY="0x3157C6AcA800D507af95Ab1466adBA3A6F11eE1a";
  const QL1_FACTORY="0x475f361993D6FAcBF32fB82B66be0fB40f3d974C";
  const USDT_INF="0xC2684966e5c95B2bc636FB4a1f3Da9Ad23d94753";
  const QOM_INF="0x53465CbBBA5b14f5Dc00794330f0f4aFb30EAA1d";
  const NATIVE_PH="0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE";
  const WQOM="0xa26dfBF98Dd1A32FAe56A3D2B2D60A8a41b0bDF0";
  const QUSDT="0xC276b91c0e8D10260af7b67009d2683bB7776308";

  const infF = new Contract(INF_FACTORY, FACTORY_ABI, inf);
  const ql1F = new Contract(QL1_FACTORY, FACTORY_ABI, ql1);
  console.log("inf factory pairs", (await infF.allPairsLength()).toString());
  console.log("ql1 factory pairs", (await ql1F.allPairsLength()).toString());

  // Infinite anchor 42/USDT known pair
  await pairInfo(inf, "0xfac6a97837fd3ef5876e18457eea52415296c613", "INF 42/USDT known");
  const pair42usdt = await infF.getPair(NATIVE_PH, USDT_INF); console.log("getPair 42/USDT =", pair42usdt);
  const pairQomUsdt = await infF.getPair(QOM_INF, USDT_INF); await pairInfo(inf, pairQomUsdt, "INF QOM/USDT");
  const pairQom42 = await infF.getPair(QOM_INF, NATIVE_PH); await pairInfo(inf, pairQom42, "INF QOM/42");

  // QL1 WQOM/qUSDT
  const pairWQomQusdt = await ql1F.getPair(WQOM, QUSDT); await pairInfo(ql1, pairWQomQusdt, "QL1 WQOM/qUSDT (ave anchor?)");
  // also QSWAP/WQOM
  const QSWAP="0x4AF41F453Ead00d1cc6Aa0b5B454bdeB102AFc8d";
  const pairQswap = await ql1F.getPair(QSWAP, WQOM); await pairInfo(ql1, pairQswap, "QL1 QSWAP/WQOM");
})();
