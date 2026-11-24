# NASDAQ spec — update, 26 Oct 2026

Merge into the NASDAQ spec in the Mac `jerrykid` folder, then delete this file.

## Desk — 4 tabs (27 Oct 2026)

- **Market** — how is the market today: QQQ live with today's 5-minute line, SPY, SMH, 12 key stocks as a heat grid, sectors, big movers (> $2B), top 5 headlines (refreshed each morning).
- **Card** (3 Nov) — top: today's action for the account (sell now · limit sell at target · hold, with the stocks and dollar amounts; all targets vs all stops). Then each stock: live price, one action (SELL NOW / SELL AT target / SELL HALF AT target / HOLD / HOLD · ODDS WEAK), target vs stop in % and $, and the reason: how the same target/stop plan did on the stock's last ~14 months (target first %, stop first %, average 20-day result → wait for the target or sell now), plus Claude's one-line why. Bottom: Ask Claude box (× to clear, clears after sending, no example questions; replies as ANSWER · bullets · RISK).
- **Search** — one box. A ticker shows (29 Oct): live price; odds of hitting target vs stop in 20 trading days; news and Claude's read (verdict + 3 bullets from headlines and live data); Street view (analyst ratings and target, big-order money flow, earnings); chart levels and 1D/1W/1M confidence folded. A question goes to Claude, which must fetch live quotes, odds, analysts and news before answering. Buy ideas folded below.
- **Sim** — paper account that follows the daily market call: P&L, curve, direction/range hit rates, worst drop, current paper holdings, full order history, per-stock accuracy, recent calls.

Ledger (public site) retired 27 Oct 2026.

## Daily timing (SGT, weekdays)

06:10 Ledger data rebuild → 08:00 yesterday's calls scored → 09:00 Ledger Market card → 09:25 Desk Card and Track refreshed, plus market and per-stock headlines. Account and prices are live whenever the Desk is open.

## Rules

- Desk never shows on the public Ledger; the Ledger never shows holdings or P&L.
- Desk Sell/Trim/Hold, target and stop come from Claude's last review (22–23 Oct) until a daily review is added.
- Replies to YY: 3 short lines, picture over text, only the tab names above.

## Open

1. Done 23 Nov: daily order ticket at 20:40 BKK refreshes Sell/Trim/Hold, target and stop from live Webull data.
2. Done 27 Oct: Desk Card has In-session; Desk Search has Today (Intraday). Ledger retired.
3. Search shows full analysis for 273 tickers; others get price only.

## Strategy headline and Why (23 Nov)

- Card: the action card's title is today's strategy headline (max 10 words, e.g. "One-day relief rally, trend still down → sell into the bounce"), then the counts (sell all now · sell part now · sell at target · hold), the condition that flips the plan to buying, and a closed "Why ▸" with the reasons, so the orders stay on the first screen.
- The reasons live in one place only: the Card's Why. The Market tab stays data (QQQ, key stocks, sectors, news).
- Scale-out: a holding can be sold part now and the rest on a limit; the Card shows "SELL n NOW · rest @limit".
- Both read the "strategy" block and "nowQty" in the Desk's private account file, written by the daily order ticket.

## Card layout (24 Nov)

1. Today: the strategy headline, the condition that turns the plan to buying with a tracker under it (the last 10 QQQ closes as dots against the goal line, the closes still needed, and a recent-low → goal track with today's price, live when Webull is connected), "Why this plan" (closed), and Value · Open loss · Cash.
2. Orders: exactly what to type into Webull, grouped Sell now · Sell part now · Limit orders (GTC) · Hold, with the rough dollar total per group. Tapping a row opens that stock.
3. My stocks: each stock shows the same order line, its stop rule ("Close under X → sell at next open") and one short reason. The target-vs-stop bar, past-year odds and chart levels open on tap.

## One plan everywhere (24 Nov)

For a stock YY holds, the Card's plan (action, order, stop rule) is the only advice. Search shows it under "You hold", with a link to the Card. Claude's read in Search and Ask must restate that plan and may only disagree in the RISK line. The trend label says where the trend breaks or turns (no action words). The day/week/month ranges show no SELL/HOLD pill for held stocks, and the past-year odds are shown as facts, not as a verdict.
