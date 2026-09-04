#!/usr/bin/env python3
"""Multi-horizon read on one name: 1D / 5D / 1M.  ./horizons.sh META

Same lookahead-free rule as the daily card (MA20 + ATR14 + hysteresis, plan §5).
Only the horizon changes, so the three rows are comparable.

Every hit-rate is printed NEXT TO the baseline it has to beat — the share of
windows the stock simply rose. That is the proof.py lesson of 2026-08-31: on a
name that drifts up, an IN call scores without any edge at all, and a bare
hit-rate hides it. The edge column is hit minus baseline, and it is the only
number on this card that says whether the model is worth obeying.

Band is anchored driftless on the last close and scaled ATR*BAND*sqrt(h).
"""
from __future__ import annotations

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import feed                                                        # noqa: E402
import render                                                      # noqa: E402
from indicators import (ATR_N, BAND, HYST, MA_N, _sorted_oldest_first,  # noqa: E402
                        atr_series, sma_series, state_series)

HORIZONS = [("1D", 1), ("5D", 5), ("1M", 21)]
G, R, Y, D, B, X = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"


def live_price(sym: str) -> tuple[float | None, str]:
    """Webull snapshot first; Yahoo when it returns nothing.

    MEASURED 2026-09-04: get_snapshot returns [] for every symbol on this key while
    get_history_bar works, so the card was silently pricing off the last CLOSE and
    calling it live. A stale price presented as live is the worst of the two failures,
    so the source is printed.
    """
    s = feed.snapshot([sym]).get(sym)
    if s and s.get("price"):
        return s["price"], "webull"
    try:
        import urllib.request
        u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
             f"?interval=1d&range=1d")
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        m = json.load(urllib.request.urlopen(req, timeout=20))["chart"]["result"][0]["meta"]
        return float(m["regularMarketPrice"]), "yahoo"
    except Exception:
        return None, "close"


def evaluate(sym: str, count: int = 800, bars: list[dict] | None = None,
             account: bool = True) -> dict:
    """One symbol -> the 1D/5D/1M read.

    bars=None pulls from Webull. Pass bars to score a symbol Webull will not serve
    (that is how the public build works, off Yahoo).

    account=False keeps holdings and the live-position lookup out entirely. The
    public JSON is built with it OFF — plan R12: a file served from a public repo
    must not be able to carry account data even by accident.
    """
    bars = _sorted_oldest_first(bars if bars is not None else feed.bars(sym, count=count))
    if len(bars) < MA_N + ATR_N + 2:
        raise SystemExit(f"{sym}: EXTRACTION FAILED — {len(bars)} bars, "
                         f"need {MA_N + ATR_N + 2}")
    atr, sma = atr_series(bars), sma_series(bars)
    states = state_series(bars, atr, sma)
    closes = [b["close"] for b in bars]
    a, m, state, last = atr[-1], sma[-1], states[-1], bars[-1]

    px, src = live_price(sym) if account else (None, "close")
    price = px or last["close"]
    res = {"symbol": sym, "price": price, "src": src, "regime": state,
           "prev_close": last["close"], "last_bar": last["date"], "bars": len(bars),
           "first": bars[0]["date"], "atr": a, "atr_pct": a / price * 100, "sma20": m,
           "invalidation": m - HYST * a, "reentry": m + HYST * a,
           "change_pct": (price / last["close"] - 1) * 100 if px else
                         (last["close"] / closes[-2] - 1) * 100,
           "held": feed.positions().get(sym) if account else None, "rows": []}
    for n in (50, 200):
        if len(closes) >= n:
            res[f"sma{n}"] = sum(closes[-n:]) / n
    w = closes[-252:]
    res["r52"] = {"lo": min(w), "hi": max(w),
                  "pos": (price - min(w)) / (max(w) - min(w)) * 100}

    for label, h in HORIZONS:
        hit = n = up = 0                          # overlapping windows
        for i, st in enumerate(states):
            if st == "WATCH" or i + h >= len(closes):
                continue
            n += 1
            u = closes[i + h] > closes[i]
            up += u
            hit += (st == "IN") == u
        ihit = inn = iup = 0                      # independent (non-overlapping)
        for i in range(0, len(closes) - h, h):
            if states[i] == "WATCH":
                continue
            inn += 1
            u = closes[i + h] > closes[i]
            iup += u
            ihit += (states[i] == "IN") == u
        k = BAND * math.sqrt(h)
        inside = bn = 0
        for i in range(len(bars) - h):
            if atr[i] is None:
                continue
            bn += 1
            lo, hi = closes[i] - k * atr[i], closes[i] + k * atr[i]
            inside += lo <= closes[i + h] <= hi
        res["rows"].append({
            "label": label, "h": h,
            "lo": price - k * a, "hi": price + k * a,
            "half_pct": k * a / price * 100,
            "band_pct": inside / bn * 100 if bn else None,
            "hit": hit / n * 100 if n else None, "base": up / n * 100 if n else None,
            "edge": (hit - up) / n * 100 if n else None, "n": n,
            "iedge": (ihit - iup) / inn * 100 if inn else None, "in": inn,
            "moved": (closes[-1] / closes[-1 - h] - 1) * 100 if len(closes) > h else None,
        })

    # long-only replay of the rule vs simply holding, same bars, no costs.
    eq = 1.0
    for i in range(len(closes) - 1):
        if states[i] == "IN":
            eq *= closes[i + 1] / closes[i]
    res["rule_x"], res["hold_x"] = eq, closes[-1] / closes[0]
    return res


def action(r: dict, row: dict) -> tuple[str, str]:
    """Regime x holding x measured edge -> what to do at this horizon.

    An edge at or below zero cannot justify OPENING or ADDING to a position: that
    is the model claiming to know a direction it has been measured not to know.
    It can still justify HOLDING what is already held, because the exit level is
    a risk statement, not a direction call.
    """
    held = bool(r["held"] and r["held"]["qty"])
    if r["regime"] == "OUT":
        return ("SELL", R) if held else ("STAND ASIDE", D)
    if r["regime"] == "WATCH":
        return ("HOLD", Y) if held else ("NO TRADE", D)
    if row["edge"] is not None and row["edge"] <= 0:
        return ("HOLD, NO ADD", Y) if held else ("NO TRADE", D)
    return ("HOLD", G) if held else ("BUY", G)


def main() -> None:
    for sym in (sys.argv[1:] or ["META"]):
        r = evaluate(sym)
        c = G if r["change_pct"] >= 0 else R
        print(f"\n{D}{render.stamp()}{X}")
        head = (f"\n{B}{r['symbol']:<6}{X}{c}{r['price']:>8,.2f}  "
                f"{r['change_pct']:+.2f}%{X}")
        if r["held"] and r["held"]["qty"]:
            h = r["held"]
            uc = G if h["upl"] >= 0 else R
            head += (f"   {D}holding {h['qty']:.0f} @ {h['cost']:,.2f} "
                     f"{uc}{h['upl']:+,.0f}{X}")
        print(head + f"   {D}({r['src']}){X}")

        print(f"\n{D}{'':<5}{'action':<14}{'expected range':>22}{'band held':>11}"
              f"{'edge vs hold':>14}{X}")
        for row in r["rows"]:
            act, col = action(r, row)
            e = row["edge"]
            ec = G if e > 2 else (Y if e > -2 else R)
            print(f"{B}{row['label']:<5}{X}{col}{act:<14}{X}"
                  f"{row['lo']:>10,.0f} –{row['hi']:>8,.0f}{D} ±{row['half_pct']:.1f}%{X}"
                  f"{row['band_pct']:>9.0f}%{ec}{e:>13.0f}pp{X}")

        print(f"\n{D}regime {r['regime']} · exit below {r['invalidation']:,.2f} "
              f"({(r['price']-r['invalidation'])/r['price']*100:.1f}% away) · "
              f"ATR {r['atr_pct']:.1f}% · MA20 {r['sma20']:,.0f}"
              + (f" · MA200 {r['sma200']:,.0f}" if "sma200" in r else "")
              + f" · 52w {r['r52']['pos']:.0f}% of range{X}")
        print(f"{D}trailing closed bars: 1D {r['rows'][0]['moved']:+.1f}% · 5D {r['rows'][1]['moved']:+.1f}%"
              f" · 1M {r['rows'][2]['moved']:+.1f}%{X}")
        print(f"{D}{r['bars']} bars {r['first']}→{r['last_bar']} · rule long-only "
              f"x{r['rule_x']:.2f} vs buy-and-hold x{r['hold_x']:.2f} over the same bars{X}")
        print(f"{D}edge = model hit-rate minus the share of windows the stock rose anyway. "
              f"0 or below means the direction call adds nothing.{X}")


if __name__ == "__main__":
    main()
