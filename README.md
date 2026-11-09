# QL1トークン価格・時価総額（Infiniteアンカー）

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

QL1 の全トークンの価格と時価総額を、**42 Chain（Infinite）側で追跡した QOM 価格**を基準に表示する静的サイト。

**公開サイト:** https://ql1-infinite42-guppy-histoire.github.io/ql1-token-prices/

トップ（index.html）は言語の振り分けページです。保存済みの言語設定
（localStorage の `ql1prices_lang`）が「ja」のときだけ日本語ページへ、
それ以外は**英語がデフォルト**で英語ページへ進みます。各ページ右上の
セレクタでいつでも切り替えできます（選択は保存されます）。

- 英語: https://ql1-infinite42-guppy-histoire.github.io/ql1-token-prices/en.html
- 日本語: https://ql1-infinite42-guppy-histoire.github.io/ql1-token-prices/ja.html

## なぜ Ave.ai の表示と違うのか

Ave.ai は QL1 内の **QOM/qUSDT ペア**の価格で QOM を換算して全トークンを計算している。そのプール基準だと QOM は約 $3.46×10⁻⁹ になるが、42 Chain 側の市場では約 $7.74×10⁻¹⁰ で、**約4.47倍の乖離**がある（2026-11-06 実測）。このサイトは 42 Chain 側を基準にする。

## 計算方法（全てオンチェーン実測）

- **42 価格**: 42 Chain の Don't Panic 42/USDT ペアのリザーブ比率（USDT = $1）
- **QOM アンカー**: 42 Chain の QOM/42 ペア × 42価格。
  裏付けとして FISH/USDT × FISH/QOM からも逆算し、両経路が約0.04%差で一致することを確認済み（2026-11-06）。
- **各QL1トークン**: QomSwap ファクトリーの全645ペアを取得し、基準トークン
  （WQOM = QOMアンカー、qUSDT/qUSDC/qDAI = $1固定）との直接ペアのうち、
  基準側流動性が最大のプールから算出。基準側流動性 $0.5 未満は価格なし。
  複数経路で3倍以上ズレたトークンには「⚠ルート乖離」を表示。
  2段ルートは中継トークンの流動性 $500 以上の場合のみ。
- **時価総額**: 価格 × 総供給量（FDV）。ブリッジトークンの総供給量は
  発行上限を含む場合があり、その場合は大きく出る（サイト内にも注意書きあり）。
- **LPトークン**: プールの裏付け資産合計 ÷ LP総供給量。

## 機能

- トークン一覧（価格 USD/QOM、時価総額、総供給量、保有者数、プール流動性、算出行ルート）
- 検索・並び替え・流動性フィルター・乖離フィルター
- **CA（コントラクトアドレス）入力で即時追跡**: 一覧に無いトークンでも、その場で
  チェーンから読み取って価格と時価総額を表示し、追跡リストに追加。外すことも可能。
  追跡リストはブラウザ（localStorage）に保存される。
- **ポートフォリオ**: 追跡トークンに保有量を入れると評価額と合計を表示。
- **シェア**: ウォッチリストのリンク（開くと相手の画面に取り込まれる）、
  保有量つきポートフォリオリンク、Xシェア、SNS用PNG画像の生成・共有。

## データ取得

通常はキャッシュ用 Cloudflare Worker（`ql1-token-prices.nepicobsv.workers.dev`）が
1分ごとに両チェーンを読み直して KV に置いた JSON を取得する（表示まで約1秒）。
Worker はサイトと同じ計算コードを `tools/build_worker.py` で `docs/app.js` から
生成して使っており、価格・アンカーはブラウザ直接取得と同一になることを検証済み。
Worker に届かない・古い場合はブラウザが RPC から直接ライブ取得し（42 Chain:
evm-rpc.infinitedrive.xyz、QL1: evm-rpc-ql1.mschihuahua.org、保有者数:
scan.qom.network Blockscout API）、それも失敗した場合は同梱のスナップショット
（`docs/snapshot.json`）を表示する。
スナップショットの再生成: `python3 tools/generate_snapshot.py docs/snapshot.json`
Worker の再デプロイ: `python3 tools/build_worker.py` でバンドルを生成し、
Cloudflare API ヘルパーで `worker/dist/worker.bundle.js` を
`worker/bindings.json` と一緒にデプロイ（cron は毎分）。

価格はプール比率からの推定値で、約定価格の保証ではない。

## English summary

A static site that lists prices and market caps for every QL1 token, anchored
to the QOM price tracked on the 42 Chain (Infinite) side instead of the QL1
QOM/qUSDT pool that Ave.ai uses (the two differed by about 4.47× when measured
on 2026-11-06). Token prices come from each token's deepest direct QomSwap
pair against an anchor token (WQOM at the Infinite-tracked QOM price;
qUSDT/qUSDC/qDAI at $1); market cap is price × total supply (FDV). Features:
live on-chain loading in the browser with a bundled snapshot fallback,
search/sort/filters, instant CA (contract address) lookup and tracking,
holdings-based portfolio totals, and sharing via watchlist links, portfolio
links, X, and generated PNG images. The root page is a language gate —
English by default, Japanese at `ja.html` — with a language selector at the
top right of each page. Prices are estimates from pool ratios, not guaranteed
execution prices. MIT licensed.

## 変更履歴

- 2026-11-09: 高速化。キャッシュ用 Worker（1分ごとに両チェーンを読み直し）を追加し、通常表示を約1秒に短縮（従来はスマホで数分かかることがあった）。直接取得のフォールバックも並列化。計算方法とアンカーは不変。
- 2026-11-09: リアルタイム版に更新（「要アップデート」告知で予告していた新バージョン）。価格の入力は全て訪問時点でチェーンからライブ取得し、開いたままでは45秒ごとに自動更新、最終更新時刻とブロック番号を表示。告知バナーは撤去。
- 2026-11-08: 「要アップデート／新バージョンをお待ちください」の告知バナーを掲載（サイトは公開維持）。
- 2026-11-06: 初版公開。

## ライセンス

MIT License（[LICENSE](LICENSE)）。オープンソースとして公開しています。自由に使って、直して、配って大丈夫です。
