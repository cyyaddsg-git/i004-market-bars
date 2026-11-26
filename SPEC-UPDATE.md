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

## Review fixes (24 Nov)

- The daily plan alone decides each action. Live prices no longer flip it: a dip under a stop shows a note ("the stop counts at the close"), and a price at the limit shows "check the order filled".
- Card is one list: Today, then Orders grouped Sell now · Sell part now · Limit orders (GTC) · Hold. Each row shows price, day move, P&L, the order to type and its stop rule. Tapping it shows the reason, target vs stop, past-year odds, day/week/month ranges and a link to Search.
- Each order row checks Webull's open orders: "✓ In Webull", "Not placed in Webull yet", or what differs (DAY instead of GTC, quantity, price).
- Search, for a held stock: the plan's stop and limit prices sit on the chart-levels ladder; the trend levels read "Trend turns up above" / "Uptrend breaks under"; the 5-minute entry line is hidden.

## Today panel (24 Nov)

The top of the Card is a compact status panel, not an article: a mode chip (Sell mode / Hold mode / Buy mode, Buy once the buy signal is met) with the plan date and a "Why" button on one row; a one-line headline; the buy-signal gauge (dots for closes above the line, a track from the recent low to the line with today's price and the last 10 closes marked); and Value · Open P&L · Cash in one divided row. "Why" opens the reasons inside the panel.

## Market header and Buy back (24 Nov)

- Market tab header: one row with a session chip (Pre-market / Open / After hours / Closed), the next bell in SGT with a countdown, and a small holiday tag ("Thu off") only when one is within 3 days. The QQQ chart shows today's pre-market and session bars, captioned "Today · 5-min" or "Last session · <date>", with the last close as the dashed line. Before the open, % changes are measured from the last session's close, not Webull's previous-day move.
- Card: a Buy back list after Orders. It waits for the buy signal (QQQ closes above its 200-day two days in a row). QQQ comes first with half the cash; then each name buys, max 10% of the account, when it closes above its trend-turns-up line, sorted by distance. Small caps that caused the losses are listed as not bought back.

## Search clean-up (24 Nov)

- One trend line per stock ("Downtrend · turns up above X"); the IN/OUT pill that said the same is gone.
- Chart levels show only levels within ±25% of the price, plus the plan's stop and limits.
- While the Card's buy signal is off, nothing says BUY: day/week/month calls read "BUY AFTER SIGNAL", the 5-minute line reads "WAIT", and Buy ideas become a Watchlist ("buy only after the market buy signal"). "Exit" there reads "Breaks under".
- "Ask a question about X" puts the ticker in the search box for a question instead of asking Claude for a second verdict.

## One structure (approved 24 Nov)

Each tab answers one question; each fact has one source; only the Card advises; shared parts look the same everywhere. The Desk always opens on the Card.

- Market (what is the market doing?): session + QQQ (Today 5-min or 2-week daily chart, SPY/SMH in the figures row) · sectors · key stocks and big movers in one card · dated news. No advice.
- Card (what do I do today?): Today panel · Orders · Buy back · Ask.
- Search (one stock): header with one trend line · your plan (held, read-only from the Card) or watchlist status (not held) · Price levels (stop–now–target scale with odds, ladder, day/week/month ranges) · news & Claude's read · street view. The watchlist shows only when no stock is open.
- Sim (is the advice working?): paper curve · holdings and order history · accuracy per stock with recent calls.
- Shared parts: session chip, trend line, order line + stop, level scale, progress track, ranges block.
- Sources: daily plan → Card, Search plan, Ask, Claude's read, Buy back; trend levels → trend line, ladder, Buy back, watchlist; Webull live → prices, account, open orders, odds, street view; morning news → Market and Search news; paper account → Sim.

## Record tab (25 Nov)

A fifth tab, Record (YY's real Webull trades; Sim stays the paper account), opens with the running total versus selling at the close, then "Sells vs close": for each trading day, each stock YY sold with shares, average sell price, that day's close, the difference and the dollars missed (or saved) against selling at the close, plus a total, other trades that day and one note. Earlier days stay as one line each. The daily order ticket appends the previous day from Webull's filled orders. The record lives only in the private Desk.

## Daily summaries (25 Nov)

- Pre-market: the order ticket at 21:40 SGT (push + Card Today panel).
- After close: a recap at 07:08 SGT, Tue–Sat, for the session that just ended: QQQ/SPY/SMH closes, QQQ's day range with open and close, how the day moved, the main reason, moves in YY's names, and the levels to watch (buy signal, 20-day, support). Shown on the Card inside "Why" as the "Post-close review" page, next to the "Pre-market plan" page, with one "Plan vs day" line comparing the morning plan with what happened; pushed as one line. It also adds that day's sells to Record.
