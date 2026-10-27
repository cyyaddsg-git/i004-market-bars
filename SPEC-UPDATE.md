# NASDAQ spec — update, 26 Oct 2026

Merge into the NASDAQ spec in the Mac `jerrykid` folder, then delete this file.

## Desk — 4 tabs (27 Oct 2026)

- **Market** — how is the market today: QQQ live with today's 5-minute line, SPY, SMH, 12 key stocks as a heat grid, sectors, big movers (> $2B), top 5 headlines (refreshed each morning).
- **Card** — what to do with each of my stocks: header counts SELL/TRIM/HOLD, value, 7-day change, cash; every holding with live price, action, target, stop and a stop←price→target bar; tonight's 5-minute line in US hours. (i) explains the basis: daily chart + 1-month range for the plan, 5-minute chart for tonight.
- **Search** — one box: a ticker opens its view (live price, trend, ladder, 1D/5D/1M with confidence, tonight's line); a question goes to Claude, which must fetch live data (quotes, chart analysis, portfolio, market, price history) before answering. Buy ideas below.
- **Sim** — paper account that follows the daily market call: P&L, curve, direction/range hit rates, worst drop, current paper holdings, full order history, per-stock accuracy, recent calls.

Ledger (public site) retired 27 Oct 2026.

## Daily timing (SGT, weekdays)

06:10 Ledger data rebuild → 08:00 yesterday's calls scored → 09:00 Ledger Market card → 09:25 Desk Card and Track refreshed. Account and prices are live whenever the Desk is open.

## Rules

- Desk never shows on the public Ledger; the Ledger never shows holdings or P&L.
- Desk Sell/Trim/Hold, target and stop come from Claude's last review (22–23 Oct) until a daily review is added.
- Replies to YY: 3 short lines, picture over text, only the tab names above.

## Open

1. Daily refresh of Sell/Trim/Hold, target, stop.
2. Done 27 Oct: Desk Card has In-session; Desk Search has Today (Intraday). Ledger retired.
3. Search shows full analysis for 273 tickers; others get price only.
