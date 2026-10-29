# NASDAQ spec — update, 26 Oct 2026

Merge into the NASDAQ spec in the Mac `jerrykid` folder, then delete this file.

## Desk — 4 tabs (27 Oct 2026)

- **Market** — how is the market today: QQQ live with today's 5-minute line, SPY, SMH, 12 key stocks as a heat grid, sectors, big movers (> $2B), top 5 headlines (refreshed each morning).
- **Card** — what to do with each of my stocks: header counts SELL/TRIM/HOLD, value, 7-day change, cash; every holding with live price, action, target, stop and a stop←price→target bar; tonight's 5-minute line in US hours. (i) explains the basis: daily chart + 1-month range for the plan, 5-minute chart for tonight. Each stock also has an odds bar (29 Oct): on its own last ~14 months, how often price reached the target before the stop within 20 trading days.
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

1. Daily refresh of Sell/Trim/Hold, target, stop.
2. Done 27 Oct: Desk Card has In-session; Desk Search has Today (Intraday). Ledger retired.
3. Search shows full analysis for 273 tickers; others get price only.
