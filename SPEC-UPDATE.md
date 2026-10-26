# NASDAQ spec — update, 26 Oct 2026

Merge into the NASDAQ spec in the Mac `jerrykid` folder, then delete this file.

## Two apps, eight tabs

| App | Who sees it | Tabs |
|---|---|---|
| **Desk** | YY only (private, pinned in Claude) | **Account · Card · Search · Ask · Track** |
| **Ledger** | Public web app | **Market · In-session · Intraday** |

## Desk tabs

- **Account** — money only: value 7 days ago → now, open P&L by stock, last 7 days by stock. Live from Webull.
- **Card** — advice only: my stocks (Sell/Trim/Hold, target, stop, trend, 1D/5D/1M confidence), watchlist calls, buy ideas.
- **Search** — any ticker: live price, trend, exit and re-entry prices, price ladder, 1D/5D/1M calls with confidence.
- **Ask** — question in, Claude answer out, using live positions and prices.
- **Track** — is the Card right: direction hit rate, range hit rate, paper account value since 27 Aug, per-stock accuracy, recent calls ✓/✗.

Confidence: **High** = call beats guessing by ≥5pp · **Medium** 2–5pp · **Low** = no edge, trust only the range.

## Daily timing (SGT, weekdays)

06:10 Ledger data rebuild → 08:00 yesterday's calls scored → 09:00 Ledger Market card → 09:25 Desk Card and Track refreshed. Account and prices are live whenever the Desk is open.

## Rules

- Desk never shows on the public Ledger; the Ledger never shows holdings or P&L.
- Desk Sell/Trim/Hold, target and stop come from Claude's last review (22–23 Oct) until a daily review is added.
- Replies to YY: 3 short lines, picture over text, only the tab names above.

## Open

1. Daily refresh of Sell/Trim/Hold, target, stop.
2. Desk has no In-session or Intraday equivalent yet; keep those Ledger tabs.
3. Search shows full analysis for 273 tickers; others get price only.
