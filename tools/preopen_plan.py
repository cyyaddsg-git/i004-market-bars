#!/usr/bin/env python3
"""Pre-open plan for the private i004 Desk: one action, target and stop per holding.

    python tools/preopen_plan.py IN_DIR OUT_DIR
    python tools/preopen_plan.py --check      exit 3 when the US market is closed today

IN_DIR holds the raw Webull answers the caller fetched just before the US open:
    balance.json     get_account_balance
    positions.json   get_account_positions
    snapshots.json   list of get_stock_snapshot rows (stocks and ETFs, extended hours on), QQQ included
    bars/*.*         get_stock_bars answers (daily, ~260 bars), any number of files
    prev.json        the Desk's current account.json (optional: last plan's stops)

Writes OUT_DIR/account.json for the Desk and prints the alert text.
Nothing here holds account data: the numbers come in at run time and go to the private Desk only.

Rules (daily chart):
  trend   up = price above the 50-day and 200-day averages; down = below the 200-day
          (below the 50-day when there is no 200-day yet); otherwise sideways.
  stop    trails: the higher of the last plan's stop and (20-day low - 0.25 ATR), always below the price.
  target  the nearest resistance above the price (20/50/200-day average or 20-day high), else price + 2 ATR.
  action  price at or under the last stop -> SELL NOW.
          under $1 -> SELL at target (delisting risk).
          downtrend -> sell into the bounce at the target: half for large caps (> $100B), all for the rest.
          uptrend or sideways -> HOLD with the trailing stop.
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import sys
from zoneinfo import ZoneInfo

HOLIDAYS = {"2026-11-26", "2026-12-25", "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26",
            "2027-05-31", "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24"}
CORE_CAP = 100e9


def load(path, default=None):
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return default


def trading_day(d: dt.date) -> bool:
    return d.weekday() < 5 and d.isoformat() not in HOLIDAYS


def last_close(now_et: dt.datetime) -> str:
    """ET date of the last finished session."""
    d = now_et.date()
    if not trading_day(d) or now_et.hour < 16:
        d -= dt.timedelta(days=1)
        while not trading_day(d):
            d -= dt.timedelta(days=1)
    return d.isoformat()


def bars_from(obj, out):
    """Collect {symbol: [(date, high, low, close)]} from any nesting of get_stock_bars answers."""
    if isinstance(obj, dict):
        if "symbol" in obj and isinstance(obj.get("result"), list):
            rows = [(str(b["time"])[:10], float(b["high"]), float(b["low"]), float(b["close"])) for b in obj["result"]
                    if float(b.get("close") or 0) > 0]
            if rows:
                out[obj["symbol"]] = sorted(set(rows))
            return
        for v in obj.values():
            bars_from(v, out)
    elif isinstance(obj, list):
        for v in obj:
            bars_from(v, out)


def rsi(c, n=14):
    g = [max(0.0, c[i] - c[i - 1]) for i in range(1, len(c))]
    l = [max(0.0, c[i - 1] - c[i]) for i in range(1, len(c))]
    if len(g) < n:
        return None
    ag, al = sum(g[:n]) / n, sum(l[:n]) / n
    for i in range(n, len(g)):
        ag, al = (ag * (n - 1) + g[i]) / n, (al * (n - 1) + l[i]) / n
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def atr(b, n=14):
    tr = [max(b[i][1] - b[i][2], abs(b[i][1] - b[i - 1][3]), abs(b[i][2] - b[i - 1][3])) for i in range(1, len(b))]
    if len(tr) < n:
        return None
    a = sum(tr[:n]) / n
    for t in tr[n:]:
        a = (a * (n - 1) + t) / n
    return a


def px(v):
    return "—" if v is None else (f"{v:.4f}" if abs(v) < 1 else f"{v:,.2f}")


def live_price(q, fallback):
    if q:
        ext = float(q.get("extend_hour_last_price") or 0)
        if q.get("trade_status") not in ("RTH", None) and ext > 0:
            return ext
        if float(q.get("price") or 0) > 0:
            return float(q["price"])
    return fallback


def plan_one(s, qty, avg, price, b, cap, prev):
    c = [x[3] for x in b]
    sma = lambda n: sum(c[-n:]) / n if len(c) >= n else None
    s20, s50, s200 = sma(20), sma(50), sma(200)
    a = atr(b) or price * 0.03
    r = rsi(c)
    lo20 = min(x[2] for x in b[-20:])
    hi20 = max(x[1] for x in b[-20:])
    long_ma = s200 or s50
    if s50 and price > s50 and (s200 is None or price > s200):
        trend = "up"
    elif long_ma and price < long_ma:
        trend = "down"
    else:
        trend = "side"
    prev_stop = prev.get("stop") if prev else None
    if prev_stop is not None and price <= prev_stop:
        return dict(act="Sell", tgt=None, stop=prev_stop, now=True,
                    why=f"Below stop {px(prev_stop)}. Trend {trend}, RSI {r:.0f}" if r else f"Below stop {px(prev_stop)}")
    stop = lo20 - 0.25 * a
    if prev_stop is not None and prev_stop < price:
        stop = max(stop, prev_stop)
    if stop >= price:
        stop = price - a
    stop = round(stop, 4 if price < 1 else 2)
    res = sorted(v for v in (s20, s50, s200, hi20) if v and v > price * 1.01)
    tgt = res[0] if res else price + 2 * a
    tgt = round(tgt, 4 if price < 1 else 2)
    name = lambda v: ("20-day" if v == s20 else "50-day" if v == s50 else "200-day" if v == s200 else "20-day high")
    lvl = name(res[0]) if res else "2 ATR"
    rs = f", RSI {r:.0f}" if r is not None else ""
    if price < 1:
        return dict(act="Sell", tgt=tgt, stop=stop, why=f"Under $1, delisting risk. Sell at {lvl} {px(tgt)}{rs}")
    if trend == "down":
        core = cap and cap >= CORE_CAP
        line = f"Below {'200' if s200 else '50'}-day {px(long_ma)}{rs}. Sell {'half ' if core else ''}at {lvl} {px(tgt)}"
        return dict(act="Trim" if core else "Sell", tgt=tgt, stop=stop, why=line)
    return dict(act="Hold", tgt=tgt, stop=stop,
                why=f"{'Uptrend' if trend == 'up' else 'Sideways'}{rs}. Trailing stop {px(stop)} under 20-day low")


def main():
    if sys.argv[1:] == ["--check"]:
        today = dt.datetime.now(ZoneInfo("America/New_York")).date()
        print("open" if trading_day(today) else "closed")
        sys.exit(0 if trading_day(today) else 3)
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    now_et = dt.datetime.now(ZoneInfo("America/New_York"))
    bal = load(os.path.join(src, "balance.json"), {})
    pos = load(os.path.join(src, "positions.json"), [])
    snaps = load(os.path.join(src, "snapshots.json"), [])
    prev = load(os.path.join(src, "prev.json"), {}) or {}
    bars = {}
    for f in sorted(glob.glob(os.path.join(src, "bars", "*"))):
        try:
            bars_from(json.loads(open(f).read()), bars)
        except ValueError:
            pass
    q = {x["symbol"]: x for x in snaps if isinstance(x, dict) and x.get("symbol")}
    prev_by = {h["s"]: h for h in prev.get("holdings", [])}
    usd = next((a for a in bal.get("account_currency_assets", []) if a.get("currency") == "USD"), {})
    cash = float(usd.get("cash_balance") or 0)

    H = []
    for p in pos:
        s, qty, avg = p["symbol"], float(p["quantity"]), float(p["cost_price"])
        price = live_price(q.get(s), float(p["last_price"]))
        cap = float((q.get(s) or {}).get("market_value") or 0) or None
        b = bars.get(s)
        if b and len(b) >= 60:
            pl = plan_one(s, qty, avg, price, b, cap, prev_by.get(s))
        else:
            old = prev_by.get(s, {})
            pl = dict(act=old.get("act", "Hold"), tgt=old.get("tgt"), stop=old.get("stop"), why="No chart history; last plan kept")
        qty_i = int(qty) if qty == int(qty) else qty
        H.append(dict(s=s, group=(prev_by.get(s) or {}).get("group", ""), qty=qty_i, last=round(price, 4), avg=avg,
                      mv=round(qty * price, 2), pnl=round(qty * (price - avg), 2), pct=round((price / avg - 1) * 100, 2),
                      act=pl["act"], tgt=pl["tgt"], stop=pl["stop"], why=pl["why"], now=pl.get("now", False)))
    H.sort(key=lambda h: -h["mv"])
    mv = sum(h["mv"] for h in H)
    pnl = sum(h["pnl"] for h in H)
    day = last_close(now_et)
    qq = q.get("QQQ")
    qline = ""
    if qq and float(qq.get("pre_close") or 0):
        qp = live_price(qq, float(qq["price"]))
        qline = f"QQQ {qp:,.2f} ({(qp / float(qq['pre_close']) - 1) * 100:+.1f}% vs close)"
    acc = dict(asof=now_et.strftime("%-d %b %Y, %H:%M ET") + " (Webull, pre-open)", planDay=day,
               planName=now_et.strftime("%-d %b") + " · pre-open", net=round(mv + cash, 2), mv=round(mv, 2), cash=round(cash, 2),
               pnl=round(pnl, 2), pnlPct=round(pnl / (mv - pnl) * 100, 2) if mv - pnl else 0, missing="",
               market=qline, accuracy=prev.get("accuracy", {}), holdings=[{k: v for k, v in h.items() if k != "now"} for h in H],
               base=None)
    json.dump(acc, open(os.path.join(out, "account.json"), "w"))

    sell_now = [h for h in H if h["now"]]
    limit = [h for h in H if not h["now"] and h["act"] in ("Sell", "Trim")]
    hold = [h for h in H if not h["now"] and h["act"] not in ("Sell", "Trim")]
    lines = [f"i004 pre-open {now_et.strftime('%-d %b')} · open loss {'−' if pnl < 0 else '+'}${abs(pnl):,.0f}" + (f" · {qline}" if qline else "")]
    if sell_now:
        lines.append("SELL NOW (stop hit): " + ", ".join(f"{h['s']} {px(h['last'])}<{px(h['stop'])}" for h in sell_now))
    if limit:
        lines.append("LIMIT SELL: " + ", ".join(f"{h['s']}{' half' if h['act'] == 'Trim' else ''} @{px(h['tgt'])}" for h in limit))
    if hold:
        lines.append("HOLD: " + ", ".join(f"{h['s']} (stop {px(h['stop'])})" for h in hold))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
