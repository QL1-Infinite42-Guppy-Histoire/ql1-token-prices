/* ql1-token-prices cache Worker — glue source.
   tools/build_worker.py splices the pricing logic extracted from
   docs/app.js above the marker below and writes dist/worker.bundle.js.
   Edit the glue here, and the pricing logic in docs/app.js (never in
   the generated bundle). */

/* === WORKER GLUE === */
/* Refreshes the full QL1 price dataset from both chains into KV every
   minute (cron). The site fetches this one JSON instead of making
   ~2,600 RPC reads from the visitor's phone. If the cache is missing,
   the first fetch computes it inline; if it is older than 2 minutes, a
   fetch serves the stale copy and refreshes in the background. */

const PRICES_KEY = "prices:v1";
const BSLIST_KEY = "bslist:v1";
const BSLIST_TTL_MS = 10 * 60 * 1000;

async function mapPool(items, limit, fn) {
  let idx = 0;
  async function run() {
    while (idx < items.length) {
      const i = idx++;
      await fn(items[i], i);
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, run));
}

async function getBsList(env) {
  try {
    const raw = await env.PRICES_KV.get(BSLIST_KEY);
    if (raw) {
      const j = JSON.parse(raw);
      if (Date.now() - j.at < BSLIST_TTL_MS && j.data && j.data.list) return j.data;
    }
  } catch (e) { /* fall through to a fresh fetch */ }
  const bs = await fetchBlockscout();
  const data = { holders: [...bs.holders], icons: [...bs.icons], list: bs.list };
  try { await env.PRICES_KV.put(BSLIST_KEY, JSON.stringify({ at: Date.now(), data })); } catch (e) {}
  return data;
}

async function refresh(env) {
  const anchors = await fetchAnchors();
  const ref = await fetchQl1Reference(anchors.qomUsd);
  Object.assign(anchors, ref);

  const lenRes = await rpcOne(QL1_RPC, QL1_FACTORY, SEL.allPairsLength);
  const nPairs = Number(decUint(lenRes));
  let pairAddrs = [];
  await mapPool(chunks([...Array(nPairs).keys()], 100), 4, async (c) => {
    const rs = await rpcBatch(QL1_RPC, c.map((i) => [QL1_FACTORY, SEL.allPairs + encUint(i)]));
    pairAddrs.push(...rs.map(decAddr));
  });
  pairAddrs = pairAddrs.filter(Boolean);

  const pairs = [];
  await mapPool(chunks(pairAddrs, 100), 4, async (c) => {
    const calls = [];
    for (const p of c) calls.push([p, SEL.token0], [p, SEL.token1], [p, SEL.getReserves], [p, SEL.totalSupply]);
    const rs = await rpcBatch(QL1_RPC, calls);
    c.forEach((p, i) => {
      const t0 = decAddr(rs[i * 4]), t1 = decAddr(rs[i * 4 + 1]);
      const rr = parseReservesRaw(rs[i * 4 + 2]);
      if (!p || !t0 || !t1 || !rr) return;
      pairs.push({ pair: p, token0: t0, token1: t1, reserve0: rr[0], reserve1: rr[1], lpSupplyRaw: decUint(rs[i * 4 + 3]) });
    });
  });

  /* Metadata: Blockscout first (cached 10 min), on-chain only for the
     tokens Blockscout does not know. */
  const bsData = await getBsList(env);
  const holders = new Map(bsData.holders), icons = new Map(bsData.icons);
  const bsByAddr = new Map(bsData.list.map((t) => [t.address_hash.toLowerCase(), t]));
  const uniq = [...new Set(pairs.flatMap((p) => [p.token0, p.token1]))];
  const meta = new Map();
  const missing = [];
  for (const t of uniq) {
    const b = bsByAddr.get(t);
    if (b) meta.set(t, {
      symbol: b.symbol || null, name: b.name || null,
      decimals: b.decimals != null ? Number(b.decimals) : null,
      totalSupply: b.total_supply ? BigInt(b.total_supply) : null,
    });
    else missing.push(t);
  }
  await mapPool(chunks(missing, 50), 4, async (c) => {
    const calls = [];
    for (const t of c) calls.push([t, SEL.symbol], [t, SEL.name], [t, SEL.decimals], [t, SEL.totalSupply]);
    const rs = await rpcBatch(QL1_RPC, calls);
    c.forEach((t, i) => meta.set(t, {
      symbol: decStr(rs[i * 4]), name: decStr(rs[i * 4 + 1]),
      decimals: rs[i * 4 + 2] ? Number(decUint(rs[i * 4 + 2])) : null,
      totalSupply: decUint(rs[i * 4 + 3]),
    }));
  });

  const tokens = computePrices(pairs, meta, holders, icons, anchors);
  const pricedAddrs = new Set(tokens.map((t) => t.address));
  const pairAddrSet = new Set(pairAddrs);
  const unpriced = [];
  for (const t of bsData.list) {
    const a = t.address_hash.toLowerCase();
    if (!pricedAddrs.has(a)) unpriced.push({
      address: a, symbol: t.symbol, name: t.name,
      holders: t.holders_count != null ? Number(t.holders_count) : null,
      totalSupply: t.total_supply ? bigToNum(BigInt(t.total_supply), t.decimals ? Number(t.decimals) : 18) : null,
      isLP: pairAddrSet.has(a),
    });
  }
  unpriced.sort((x, y) => (y.holders || 0) - (x.holders || 0));
  const [infBlock, ql1Block] = await Promise.all([rpcBlock(INF_RPC), rpcBlock(QL1_RPC)]);
  const data = {
    anchors, tokens, unpriced,
    stats: { ql1Pairs: nPairs, bsTokens: bsData.list.length, priced: tokens.length, unpriced: unpriced.length },
    generatedAt: new Date().toISOString(), source: "cache", infBlock, ql1Block,
  };
  await env.PRICES_KV.put(PRICES_KEY, JSON.stringify(data));
  return data;
}

function jsonResponse(o, status) {
  return new Response(JSON.stringify(o), {
    status: status || 200,
    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" },
  });
}

async function recordDebug(env, key, ok, err) {
  try {
    await env.PRICES_KV.put("debug:" + key, JSON.stringify({
      at: new Date().toISOString(), ok, err: err ? String((err && err.message) || err) : null,
    }));
  } catch (e) { /* debug only */ }
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil((async () => {
      try { await refresh(env); await recordDebug(env, "cron", true, null); }
      catch (e) { await recordDebug(env, "cron", false, e); }
    })());
  },
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    if (url.pathname === "/debug") {
      const cron = await env.PRICES_KV.get("debug:cron");
      return jsonResponse({ cron: cron ? JSON.parse(cron) : null });
    }
    if (url.pathname === "/status") {
      const raw = await env.PRICES_KV.get(PRICES_KEY);
      if (!raw) return jsonResponse({ ok: false, error: "cache empty" }, 503);
      const j = JSON.parse(raw);
      return jsonResponse({
        ok: true, generatedAt: j.generatedAt, infBlock: j.infBlock, ql1Block: j.ql1Block,
        priced: j.stats.priced, unpriced: j.stats.unpriced, qomUsd: j.anchors.qomUsd, price42: j.anchors.price42,
      });
    }
    if (url.pathname === "/" || url.pathname === "/prices") {
      let raw = await env.PRICES_KV.get(PRICES_KEY);
      if (!raw) {
        try {
          await refresh(env);
          raw = await env.PRICES_KV.get(PRICES_KEY);
        } catch (e) {
          return jsonResponse({ ok: false, error: String((e && e.message) || e) }, 502);
        }
      } else {
        try {
          const j = JSON.parse(raw);
          if (Date.now() - new Date(j.generatedAt).getTime() > 120000) {
            ctx.waitUntil(refresh(env).catch(() => {}));
          }
        } catch (e) { /* serve what we have */ }
      }
      return new Response(raw, {
        headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*", "Cache-Control": "no-store" },
      });
    }
    return new Response("not found", { status: 404 });
  },
};
