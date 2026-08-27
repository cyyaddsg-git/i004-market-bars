#!/usr/bin/env python3
"""Intraday structure for one symbol. DATA, not a call.

    python engine/intraday.py NVDA [M5]

Prints where price actually is against the levels an intraday trader reads:
session range, VWAP, opening range, M5 ATR and SMA20. It deliberately prints
NO action -- the daily engine's rule is a ~2-week swing filter (measured: median
hold 10 trading days) and has no intraday meaning. Plan R15 is not built.

feed.bars() truncates `time` to a date, which is fine for daily bars and useless
here, so this reads the SDK directly and keeps the full timestamp.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import feed                                                    # noqa: E402


def bars(symbol: str, timespan: str = "M5", count: int = 200) -> list[dict]:
    r = feed.client().data.market_data.get_history_bar(
        symbol=symbol, category="US_STOCK", timespan=timespan, count=count)
    data = r.json() if hasattr(r, "json") else r
    if not isinstance(data, list):
        raise SystemExit(f"{symbol}: unexpected payload {type(data).__name__} — not guessing at it")
    out = []
    for b in data:
        try:
            out.append({"t": b["time"], "o": float(b["open"]), "h": float(b["high"]),
                        "l": float(b["low"]), "c": float(b["close"]),
                        "v": float(b["volume"])})
        except (KeyError, TypeError, ValueError):
            continue
    out.sort(key=lambda b: b["t"])
    return out


def atr(bs: list[dict], n: int = 14) -> float | None:
    if len(bs) < n + 1:
        return None
    trs = []
    for i in range(1, len(bs)):
        p, c = bs[i - 1], bs[i]
        trs.append(max(c["h"] - c["l"], abs(c["h"] - p["c"]), abs(c["l"] - p["c"])))
    a = sum(trs[:n]) / n
    for tr in trs[n:]:
        a = (a * (n - 1) + tr) / n
    return a


def main() -> None:
    sym = (sys.argv[1] if len(sys.argv) > 1 else "NVDA").upper()
    span = sys.argv[2] if len(sys.argv) > 2 else "M5"
    bs = bars(sym, span)
    if not bs:
        raise SystemExit(f"{sym}: the API returned no {span} bars — this is a FAILED read, not 'no data'")

    day = bs[-1]["t"][:10]
    today = [b for b in bs if b["t"][:10] == day]
    last = bs[-1]
    hi, lo = max(b["h"] for b in today), min(b["l"] for b in today)
    vol = sum(b["v"] for b in today)
    vwap = (sum((b["h"] + b["l"] + b["c"]) / 3 * b["v"] for b in today) / vol) if vol else None
    orb = today[:6]                      # first 30 min on M5
    a = atr(bs)
    sma = sum(b["c"] for b in bs[-20:]) / 20 if len(bs) >= 20 else None

    def line(k, v):
        print(f"  {k:<22}{v}")

    print(f"\n{sym} · {span} · {len(bs)} bars · latest bar {last['t']}")
    print(f"  session {day} — {len(today)} bars\n")
    line("last", f"{last['c']:.2f}")
    if vwap:
        line("VWAP", f"{vwap:.2f}   ({(last['c']/vwap-1)*100:+.2f}% vs last)")
    line("session range", f"{lo:.2f} – {hi:.2f}   (last sits {(last['c']-lo)/(hi-lo)*100:.0f}% up the range)"
         if hi > lo else f"{lo:.2f} – {hi:.2f}")
    if len(orb) >= 2:
        olo, ohi = min(b["l"] for b in orb), max(b["h"] for b in orb)
        where = "above" if last["c"] > ohi else ("below" if last["c"] < olo else "inside")
        line("opening 30m range", f"{olo:.2f} – {ohi:.2f}   (price {where})")
    if a:
        line(f"ATR({span},14)", f"{a:.2f}   ({a/last['c']*100:.2f}% of price)")
    if sma:
        line(f"SMA20 ({span})", f"{sma:.2f}   (last {'above' if last['c']>sma else 'below'})")
    line("session volume", f"{vol:,.0f}")
    print("\n  Structure only. No entry, no stop, no call — the intraday rule (plan R15)")
    print("  is not built, and the daily engine's rule has no intraday meaning.\n")


if __name__ == "__main__":
    main()
