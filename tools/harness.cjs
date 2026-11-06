"use strict";
/* DOM-stub harness: runs docs/app.js under ja / en page stubs with a canned
   snapshot and checks i18n (string tables, rendering, language selector),
   tracked-data compatibility, and the index.html language gate logic. */
const fs = require("fs");
const vm = require("vm");
const path = require("path");
const DOCS = path.join(__dirname, "..", "docs");

let failures = 0;
function check(name, cond, extra) {
  console.log((cond ? "PASS" : "FAIL") + " | " + name + (extra ? " | " + extra : ""));
  if (!cond) failures++;
}

const SNAPSHOT = {
  anchors: { price42: 0.71, qomUsd: 7.74e-10, qomUsdViaFish: 7.73e-10, qomQl1Pool: 3.46e-9, divergence: 4.47 },
  tokens: [
    { address: "0xa26dfbf98dd1a32fae56a3d2b2d60a8a41b0bdf0", symbol: "WQOM", name: "Wrapped QOM", decimals: 18, totalSupply: 1e12, holders: 100, icon: null, priceUsd: 7.74e-10, priceQom: 1, mcap: 774, route: "Infiniteアンカー", via: "アンカー", pair: null, liqUsd: null, hop: 1, reserveKnown: null, reserveToken: null, diverge: null, isLP: false },
    { address: "0x1111111111111111111111111111111111111111", symbol: "BABY", name: "A Fund Baby", decimals: 18, totalSupply: 1e9, holders: 50, icon: null, priceUsd: 0.001, priceQom: 1291989, mcap: 1e6, route: "BABY→WQOM", via: "WQOM", pair: "0x2222222222222222222222222222222222222222", liqUsd: 5000, hop: 1, reserveKnown: 1e11, reserveToken: 1e5, diverge: [{ via: "WQOM", usd: 0.001, liq: 5000 }, { via: "qUSDT", usd: 0.004, liq: 600 }], isLP: false },
    { address: "0x3333333333333333333333333333333333333333", symbol: "QSWAP-V2", name: "QomSwap LP BABY/WQOM", decimals: 18, totalSupply: 1e6, holders: 10, icon: null, priceUsd: 2.5, priceQom: 3.2e9, mcap: 2.5e6, route: "LP裏付け (BABY/WQOM)", via: "LP", pair: "0x3333333333333333333333333333333333333333", liqUsd: 1.25e6, hop: 1, reserveKnown: null, reserveToken: null, diverge: null, isLP: false },
  ],
  unpriced: [
    { address: "0x4444444444444444444444444444444444444444", symbol: "NOPOOL", name: "No Pool Token", holders: 3, totalSupply: null, isLP: false },
  ],
  stats: { ql1Pairs: 645, bsTokens: 900, priced: 3, unpriced: 1 },
  generatedAt: "2026-11-06T00:00:00.000Z",
};

function makeEl(id) {
  return {
    id, value: "", textContent: "", innerHTML: "", checked: false, disabled: false,
    style: {}, dataset: {}, _handlers: {},
    classList: { _s: new Set(), add(c) { this._s.add(c); }, remove(c) { this._s.delete(c); }, contains(c) { return this._s.has(c); } },
    addEventListener(ev, fn) { (this._handlers[ev] = this._handlers[ev] || []).push(fn); },
    querySelectorAll() { return []; }, querySelector() { return null; },
    scrollIntoView() {},
  };
}

function loadPage(lang, seedStore) {
  const ids = ["status", "refreshBtn", "qomPrice", "qomRoute", "price42", "qomViaFish", "fishNote", "qomQl1Pool", "divNote",
    "caInput", "caAddBtn", "caMsg", "trackedWrap", "portfolioTotal", "portfolioDetail", "trackedCards",
    "shareWatchBtn", "sharePfBtn", "shareXBtn", "shareImgBtn", "shareMsg",
    "searchBox", "minLiq", "showLp", "showDivergeOnly", "countLine", "tokenBody",
    "unpricedSummary", "unpricedBody", "convOverlay", "convTitle", "convClose", "convPriceLine",
    "convSymLabel", "convToken", "convUsd", "convQom", "convRate", "convDetail", "convTrackBtn", "langSel"];
  const els = {};
  for (const id of ids) els[id] = makeEl(id);
  els.minLiq.value = "50";
  const store = Object.assign({}, seedStore || {});
  const location = { origin: "https://example.github.io", pathname: lang === "en" ? "/en.html" : "/ja.html", search: "", hash: "", href: "" };
  const sandbox = {
    console, setTimeout, clearTimeout, BigInt, JSON, Math, Number, String, Array, Object, Map, Set, Promise, RegExp, Error, TextDecoder, URLSearchParams,
    fetch: (url) => {
      if (String(url).indexOf("snapshot.json") >= 0) return Promise.resolve({ ok: true, json: async () => JSON.parse(JSON.stringify(SNAPSHOT)) });
      return new Promise(() => {}); // RPC etc.: hang so loadLive stays in its first status
    },
    localStorage: { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); }, removeItem: (k) => { delete store[k]; } },
    document: {
      documentElement: { lang },
      getElementById: (id) => els[id] || null,
      querySelectorAll: () => [],
      addEventListener: () => {},
      createElement: () => makeEl("dyn"),
    },
    location,
    navigator: {},
    window: {},
  };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  const src = fs.readFileSync(path.join(DOCS, "app.js"), "utf8") +
    "\n;globalThis.__X = { STR, LANG, L, locRoute, langTargetFor };";
  vm.runInContext(src, sandbox, { filename: "app.js" });
  return { X: sandbox.__X, els, store, location };
}

async function settle(els) {
  for (let i = 0; i < 60; i++) {
    if (els.tokenBody.innerHTML) return true;
    await new Promise((r) => setTimeout(r, 25));
  }
  return false;
}

(async () => {
  /* ---- STR parity + LANG detection ---- */
  const en = loadPage("en");
  const ja = loadPage("ja");
  check("LANG detected en", en.X.LANG === "en");
  check("LANG detected ja", ja.X.LANG === "ja");
  const kj = Object.keys(en.X.STR.ja).sort(), ke = Object.keys(en.X.STR.en).sort();
  check("STR key parity ja/en", JSON.stringify(kj) === JSON.stringify(ke), kj.length + " keys");
  check("locRoute translates snapshot strings (en)", en.X.locRoute("LP裏付け (BABY/WQOM)") === "LP-backed (BABY/WQOM)" && en.X.locRoute("Infiniteアンカー") === "Infinite anchor" && en.X.locRoute("BABY→WQOM（CA検索）") === "BABY→WQOM (CA lookup)");
  check("locRoute is identity on ja page", ja.X.locRoute("LP裏付け (BABY/WQOM)") === "LP裏付け (BABY/WQOM)");
  check("langTargetFor", en.X.langTargetFor("ja", "en") === "ja.html" && en.X.langTargetFor("en", "ja") === "en.html" && en.X.langTargetFor("en", "en") === null);

  /* ---- rendering: EN ---- */
  check("en snapshot rendered", await settle(en.els));
  check("en status is English", en.els.status.textContent.includes("Fetching the QOM price anchor from 42 Chain"), en.els.status.textContent.slice(0, 60));
  check("en countLine is English", en.els.countLine.textContent.indexOf("Showing 3 of 3 priced tokens") === 0, en.els.countLine.textContent.slice(0, 60));
  check("en row labels English", en.els.tokenBody.innerHTML.includes('data-label="Price (USD)"') && en.els.tokenBody.innerHTML.includes('data-label="Market cap"') && en.els.tokenBody.innerHTML.includes('data-label="Route"'));
  check("en snapshot route translated in table", en.els.tokenBody.innerHTML.includes("LP-backed (BABY/WQOM)") && en.els.tokenBody.innerHTML.includes("Infinite anchor"));
  check("en badges English", en.els.tokenBody.innerHTML.includes("⚠ Route divergence") && !en.els.tokenBody.innerHTML.includes("⚠ルート乖離"));
  check("en unpriced summary English", en.els.unpricedSummary.textContent === "Tokens without a price (1)", en.els.unpricedSummary.textContent);
  check("en anchor notes English", /cross-check/i.test(en.els.fishNote.textContent) && /Ave\.ai prices every token/.test(en.els.divNote.textContent));

  /* ---- rendering: JA ---- */
  check("ja snapshot rendered", await settle(ja.els));
  check("ja status is Japanese", ja.els.status.textContent.includes("42 Chain からQOM価格アンカーを取得中"), ja.els.status.textContent.slice(0, 40));
  check("ja countLine is Japanese", ja.els.countLine.textContent.indexOf("価格あり 3 件中 3 件を表示") === 0, ja.els.countLine.textContent.slice(0, 40));
  check("ja row labels Japanese", ja.els.tokenBody.innerHTML.includes('data-label="価格 (USD)"') && ja.els.tokenBody.innerHTML.includes("LP裏付け (BABY/WQOM)"));
  check("ja unpriced summary Japanese", ja.els.unpricedSummary.textContent === "価格なしのトークン（1件）", ja.els.unpricedSummary.textContent);

  /* ---- tracked data compatibility (existing localStorage keys) ---- */
  const seed = { ql1pf_tracked_v1: JSON.stringify([{ address: "0x1111111111111111111111111111111111111111", amount: "100" }]) };
  const enT = loadPage("en", seed);
  await settle(enT.els);
  check("en tracked card from legacy storage key", enT.els.trackedWrap.style.display !== "none" && enT.els.trackedCards.innerHTML.includes("BABY"));
  check("en tracked card strings English", enT.els.trackedCards.innerHTML.includes("Remove from tracking") && enT.els.trackedCards.innerHTML.includes('placeholder="Enter amount held"'));
  const jaT = loadPage("ja", seed);
  await settle(jaT.els);
  check("ja tracked card strings Japanese", jaT.els.trackedCards.innerHTML.includes("追跡を外す") && jaT.els.trackedCards.innerHTML.includes('placeholder="保有量を入力"'));
  check("legacy keys untouched in shape", enT.store.ql1pf_tracked_v1.includes("0x1111111111111111111111111111111111111111") && enT.store.ql1pf_tracked_v1.includes('"amount":"100"'));

  /* ---- language selector behaviour ---- */
  const enS = loadPage("en");
  await settle(enS.els);
  enS.els.langSel.value = "ja";
  for (const fn of enS.els.langSel._handlers.change || []) fn();
  check("selector saves ql1prices_lang=ja", enS.store.ql1prices_lang === "ja");
  check("selector navigates to ja.html", enS.location.href.indexOf("ja.html") === 0, enS.location.href);
  const jaS = loadPage("ja");
  await settle(jaS.els);
  jaS.els.langSel.value = "en";
  for (const fn of jaS.els.langSel._handlers.change || []) fn();
  check("selector (ja page) saves en + navigates en.html", jaS.store.ql1prices_lang === "en" && jaS.location.href.indexOf("en.html") === 0);

  /* ---- index.html gate ---- */
  const gate = fs.readFileSync(path.join(DOCS, "index.html"), "utf8");
  const m = gate.match(/<script>([\s\S]*?)<\/script>/);
  check("gate script present + uses ql1prices_lang", !!m && m[1].includes("ql1prices_lang"));
  function runGate(saved, search) {
    let target = null;
    const sb = {
      localStorage: { getItem: () => saved },
      location: { search: search || "", hash: "", replace: (u) => { target = u; } },
    };
    vm.createContext(sb);
    vm.runInContext(m[1], sb);
    return target;
  }
  check("gate: no saved choice -> en.html", runGate(null) === "en.html");
  check("gate: saved ja -> ja.html", runGate("ja") === "ja.html");
  check("gate: saved en -> en.html", runGate("en") === "en.html");
  check("gate: watchlist query survives redirect", runGate(null, "?w=0xabc") === "en.html?w=0xabc", runGate(null, "?w=0xabc"));
  check("gate: plain links to both pages", gate.includes('href="en.html"') && gate.includes('href="ja.html"'));

  /* ---- static html language evidence ---- */
  const jaHtml = fs.readFileSync(path.join(DOCS, "ja.html"), "utf8");
  const enHtml = fs.readFileSync(path.join(DOCS, "en.html"), "utf8");
  check("ja.html lang=ja + selector", jaHtml.includes('<html lang="ja">') && jaHtml.includes('id="langSel"') && jaHtml.includes('class="lang-switch"'));
  check("en.html lang=en + selector", enHtml.includes('<html lang="en">') && enHtml.includes('id="langSel"') && enHtml.includes('class="lang-switch"'));
  check("en.html static copy English", enHtml.includes("Track by CA (contract address)") && enHtml.includes("Fetch latest data (on-chain)") && !enHtml.includes("追跡に追加"));

  console.log(failures ? ("\n" + failures + " FAILURES") : "\nALL CHECKS PASSED");
  process.exit(failures ? 1 : 0);
})().catch((e) => { console.error("HARNESS ERROR:", e); process.exit(1); });
