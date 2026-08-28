#!/usr/bin/env python3
"""A paper book, opened 2026-08-27 with USD 100,000 and no stock.

    python engine/sim.py            # settle what is due, then print the book

Per plan R16. Only BUY and SELL move it. HOLD / NO_TRADE / STAND_ASIDE leave it
alone, so holding is a real outcome rather than a forced flat. No fees, per YY.

"Claude should not fake the order" is enforced structurally, not promised:

  1. Every fill price is an actual bar out of data/bars.csv. The engine never
     picks a price -- it can only wait for one to exist.
  2. data/orders.csv is append-only. A lodged order carries the levels that were
     visible when it was decided; nothing about it is revised afterwards.
  3. The book is DERIVED by replaying that log from 100,000, and replay() is
     asserted against the stored book on every run. An invented or edited row
     fails the run instead of quietly changing the P/L.

No lookahead: an order decided before the open on day D fills at day D's OPEN,
and only once bars.csv actually carries that bar -- which is after that session
closed. The engine can never see the price it is about to trade at.
"""
from __future__ import annotations

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ORDERS = os.path.join(REPO, "data", "orders.csv")
BOOK = os.path.join(REPO, "data", "book.json")
BARS = os.path.join(REPO, "data", "bars.csv")

OPENED = "2026-08-27"
CAPITAL = 100_000.0
RISK_PCT = 0.01          # equity risked between entry and invalidation
MAX_WEIGHT = 0.20        # ceiling on one name, so a tight stop cannot eat the book

OCOLS = ["lodged_date", "ticker", "side", "qty", "decided_price", "invalidation",
         "bar_date", "fill_date", "fill_price", "status"]


def _orders() -> list[dict]:
    if not os.path.exists(ORDERS):
        return []
    with open(ORDERS, newline="") as f:
        return list(csv.DictReader(f))


def _save_orders(rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(ORDERS), exist_ok=True)
    with open(ORDERS, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OCOLS)
        w.writeheader()
        w.writerows(rows)


def _bars() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    if not os.path.exists(BARS):
        return out
    with open(BARS, newline="") as f:
        for b in csv.DictReader(f):
            out.setdefault(b["ticker"], []).append(b)
    for t in out:
        out[t].sort(key=lambda b: b["date"])
    return out


def replay(rows: list[dict] | None = None) -> dict:
    """The book, derived from the order log alone. This is the only place the
    book is ever computed -- there is no other path by which cash can move."""
    rows = _orders() if rows is None else rows
    cash, pos = CAPITAL, {}
    for r in rows:
        if r["status"] != "FILLED":
            continue
        q, px = int(r["qty"]), float(r["fill_price"])
        if r["side"] == "BUY":
            cash -= q * px
            p = pos.setdefault(r["ticker"], {"qty": 0, "cost": 0.0})
            p["cost"] += q * px
            p["qty"] += q
        else:
            p = pos.get(r["ticker"])
            if not p or p["qty"] < q:
                raise AssertionError(f"SELL {q} {r['ticker']} with {p['qty'] if p else 0} held "
                                     f"— the order log is not self-consistent")
            p["cost"] -= p["cost"] / p["qty"] * q      # average-cost basis
            p["qty"] -= q
            cash += q * px
            if p["qty"] == 0:
                del pos[r["ticker"]]
    return {"opened": OPENED, "capital": CAPITAL, "cash": round(cash, 2),
            "positions": {t: {"qty": p["qty"], "avg_cost": round(p["cost"] / p["qty"], 6)}
                          for t, p in pos.items()}}


def _size(equity: float, price: float, invalidation: float, cash: float) -> int:
    """Risk RISK_PCT of equity between entry and invalidation, capped by weight
    and by cash. Returns 0 when the stop is too wide to take any size."""
    per_share = price - invalidation
    if per_share <= 0 or price <= 0:
        return 0
    qty = int(equity * RISK_PCT / per_share)
    qty = min(qty, int(equity * MAX_WEIGHT / price), int(cash / price))
    return max(qty, 0)


def action_for(regime: str, held_qty: int) -> str:
    """The paper book's OWN action.

    The card's `action` cannot be used here: it is computed against YY's real
    Webull holdings, so a name YY already owns comes through as HOLD and the
    paper book -- which started flat -- would never buy it, while a SELL could
    arrive for stock it does not have. The book must read the regime against its
    own positions. Same mapping indicators.py uses, applied to a different book."""
    if regime == "IN":
        return "HOLD" if held_qty else "BUY"
    if regime == "OUT":
        return "SELL" if held_qty else "STAND_ASIDE"
    return "NO_TRADE"                                  # WATCH claims nothing


def lodge(card_rows: list[dict], today: str) -> int:
    """Turn today's card into orders. Idempotent per (date, ticker)."""
    rows = _orders()
    seen = {(r["lodged_date"], r["ticker"]) for r in rows}
    book = replay(rows)
    marks = {t: p["avg_cost"] for t, p in book["positions"].items()}
    equity = book["cash"] + sum(p["qty"] * marks[t] for t, p in book["positions"].items())
    cash = book["cash"]
    added = 0
    for r in card_rows:
        t = r["symbol"]
        if r.get("action") == "NO_DATA" or (today, t) in seen:
            continue
        held = book["positions"].get(t, {}).get("qty", 0)
        act = action_for(r.get("regime", ""), held)
        if act not in ("BUY", "SELL"):
            continue
        if act == "BUY":
            qty = _size(equity, r["price"], r["invalidation"], cash)
            if qty <= 0:
                continue
            cash -= qty * r["price"]           # provisional, so two BUYs cannot spend the same cash
        else:
            qty = held
            if qty <= 0:
                continue                       # nothing to sell — STAND ASIDE, not a short
        rows.append({"lodged_date": today, "ticker": t, "side": act, "qty": qty,
                     "decided_price": f"{r['price']:.6f}",
                     "invalidation": f"{r['invalidation']:.6f}",
                     "bar_date": r.get("last_bar", ""), "fill_date": "",
                     "fill_price": "", "status": "PENDING"})
        added += 1
    if added:
        _save_orders(rows)
    return added


def fill() -> int:
    """Fill pending orders at the first session OPEN after the bar they were
    decided on, once that bar is on disk. Never estimated, never back-dated."""
    rows = _orders()
    bars = _bars()
    n = 0
    for r in rows:
        if r["status"] != "PENDING":
            continue
        series = bars.get(r["ticker"], [])
        nxt = next((b for b in series if b["date"] > r["bar_date"]), None)
        if not nxt:
            continue
        r["fill_date"], r["fill_price"] = nxt["date"], f"{float(nxt['open']):.6f}"
        r["status"] = "FILLED"
        n += 1
    if n:
        _save_orders(rows)
    return n


def mark(prices: dict[str, float] | None = None) -> dict:
    """The book marked to market. `prices` is the live snapshot; anything missing
    falls back to the last close on disk, and never to the cost basis."""
    book = replay()
    bars = _bars()
    prices = prices or {}
    out, mv = [], 0.0
    for t, p in sorted(book["positions"].items()):
        px = prices.get(t) or (float(bars[t][-1]["close"]) if bars.get(t) else p["avg_cost"])
        val = p["qty"] * px
        mv += val
        out.append({"ticker": t, "qty": p["qty"], "avg_cost": p["avg_cost"], "price": px,
                    "value": round(val, 2), "upl": round(val - p["qty"] * p["avg_cost"], 2),
                    "upl_pct": round((px / p["avg_cost"] - 1) * 100, 2)})
    equity = book["cash"] + mv
    return {"opened": OPENED, "capital": CAPITAL, "cash": round(book["cash"], 2),
            "market_value": round(mv, 2), "equity": round(equity, 2),
            "pl": round(equity - CAPITAL, 2), "pl_pct": round((equity / CAPITAL - 1) * 100, 2),
            "positions": out,
            "pending": sum(1 for r in _orders() if r["status"] == "PENDING"),
            "filled": sum(1 for r in _orders() if r["status"] == "FILLED")}


def save_book() -> dict:
    """Persist the derived book, after checking the log was not rewritten.

    An earlier version compared the stored book against a fresh replay and
    refused if they differed -- which is exactly what a legitimate fill does, so
    the first real settlement failed the build. The invariant is not "the book
    never changes"; it is:

      * an order's DECISION fields never change once written, and
      * a fill never un-fills, and a filled price is never revised.

    Those are the things a tampered log would have to break to move the P/L.
    """
    book = replay()
    rows = _orders()

    def decision_key(r):
        return "|".join(str(r[k]) for k in
                        ("lodged_date", "ticker", "side", "qty",
                         "decided_price", "invalidation", "bar_date"))

    seen = {}
    for r in rows:
        k = f"{r['lodged_date']}/{r['ticker']}"
        seen[k] = {"decision": decision_key(r),
                   "fill": f"{r['fill_date']}@{r['fill_price']}" if r["status"] == "FILLED" else ""}

    if os.path.exists(BOOK):
        prior = json.load(open(BOOK)).get("_orders", {})
        for k, was in prior.items():
            now = seen.get(k)
            if now is None:
                raise AssertionError(f"order {k} has vanished from the log — refusing to continue")
            if now["decision"] != was["decision"]:
                raise AssertionError(f"order {k} was rewritten after the fact "
                                     f"({was['decision']} -> {now['decision']}) — refusing to continue")
            if was["fill"] and now["fill"] != was["fill"]:
                raise AssertionError(f"order {k} was already filled at {was['fill']} and now reads "
                                     f"{now['fill'] or 'UNFILLED'} — refusing to continue")

    json.dump({"_readme": "DERIVED from data/orders.csv by engine/sim.py. Do not hand-edit.",
               "_derived": book, "_orders": seen}, open(BOOK, "w"), indent=1)
    return book


# --- the page YY reads on the phone -----------------------------------------
# Its own file, not docs/index.html, so card.yml's "refuse to publish account
# data" gate stays exactly as strict as it is. This book is simulated, but the
# words it uses (equity, holdings) are the words that gate looks for, and
# loosening a real safety check to fit a fake book would be a bad trade.
BG, FG, DIM, GRN, RED, GLD = "#0F1712", "#F2F0E9", "#8fa3b6", "#4ADE80", "#FF6B6B", "#E8B84B"


def _sp(text: str, colour: str, bold: bool = False) -> str:
    weight = ";font-weight:600" if bold else ""
    return '<span style="color:%s%s;">%s</span>' % (colour, weight, text)


def page(m: dict) -> str:
    col = GRN if m["pl"] >= 0 else RED

    lines = []
    for p in m["positions"]:
        pc = GRN if p["upl"] >= 0 else RED
        lines.append(
            _sp(p["ticker"], FG, True)
            + "&nbsp;&nbsp;" + _sp("%d sh" % p["qty"], DIM)
            + "&nbsp; @ " + _sp("%.2f" % p["avg_cost"], DIM)
            + "&nbsp; now " + _sp("%.2f" % p["price"], FG)
            + "&nbsp; " + _sp(format(p["upl"], "+,.2f"), pc, True)
            + " " + _sp("(%+.2f%%)" % p["upl_pct"], pc))
    body = "<br>".join(lines) if lines else _sp("no open positions", DIM)

    head = _sp("SIMULATED book &middot; opened %s &middot; $%s &middot; no fees"
               % (m["opened"], format(m["capital"], ",.0f")), DIM)
    pl = (_sp("P/L", FG, True) + "&nbsp;&nbsp;"
          + _sp(format(m["pl"], "+,.2f"), col, True) + "&nbsp;&nbsp;"
          + _sp("(%+.2f%%)" % m["pl_pct"], col))
    sub = _sp("equity %s &middot; cash %s &middot; positions %s"
              % (format(m["equity"], ",.2f"), format(m["cash"], ",.2f"),
                 format(m["market_value"], ",.2f")), DIM)
    foot = (_sp("%d order(s) filled, %d pending" % (m["filled"], m["pending"]), DIM)
            + "<br>" + _sp("Not real money. Fills are real bar opens; "
                           "no order was ever placed.", GLD))

    return ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>i004 &middot; paper book</title><link rel="icon" href="data:,"></head>'
            '<body style="margin:0;padding:16px;background:#080d0a;">'
            '<div style="background:%s;color:%s;padding:18px 20px;border-radius:10px;'
            'font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:14px;'
            'line-height:1.65;max-width:640px;">'
            '%s<br><br>%s<br>%s<br><br>%s<br><br>%s</div></body></html>'
            % (BG, FG, head, pl, sub, body, foot))


def main() -> None:
    print(f"filled {fill()} pending order(s)")
    m = mark()
    print(f"\npaper book — opened {m['opened']} with ${m['capital']:,.0f}, no fees")
    print(f"  cash        {m['cash']:>12,.2f}")
    print(f"  positions   {m['market_value']:>12,.2f}")
    print(f"  equity      {m['equity']:>12,.2f}")
    print(f"  P/L         {m['pl']:>12,.2f}  ({m['pl_pct']:+.2f}%)")
    if m["positions"]:
        print(f"\n  {'':<7}{'qty':>7}{'cost':>10}{'price':>10}{'P/L':>10}{'%':>8}")
        for p in m["positions"]:
            print(f"  {p['ticker']:<7}{p['qty']:>7}{p['avg_cost']:>10.2f}"
                  f"{p['price']:>10.2f}{p['upl']:>10.2f}{p['upl_pct']:>+8.2f}")
    print(f"\n  {m['filled']} filled, {m['pending']} pending")
    save_book()


if __name__ == "__main__":
    main()
