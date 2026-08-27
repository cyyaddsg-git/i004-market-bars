#!/usr/bin/env python3
"""Accuracy of the advice, at 1D / 1M / 1Y — read like an indicator.

    ./score.sh              whole watchlist
    ./score.sh PLTU ORCL    just those

The rule is deterministic and lookahead-free (plan R8), so its advice for any
past day can be regenerated exactly as it would have been issued. That means the
hit rates below are measured over real history, not waited for.

What "correct" means, per plan R14 — judged on price alone, never on P&L or
position size:

    regime IN  on day T  ->  correct if close[T+h] > close[T]
    regime OUT on day T  ->  correct if close[T+h] < close[T]

h = 1 (1D), 21 (1M), 252 (1Y) trading bars. A day whose horizon runs past the
end of the data is not scored — never padded, never assumed.

Range containment is scored separately and only at 1D, because that is the claim
the card actually makes about tomorrow.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import feed                                                    # noqa: E402
from indicators import (ATR_N, BAND, MA_N, atr_series,          # noqa: E402
                        sma_series, state_series, _sorted_oldest_first)

HORIZONS = [("1D", 1), ("1M", 21), ("1Y", 252)]
G, R, Y, D, B, X = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"


def score(bars: list[dict]) -> dict | None:
    bars = _sorted_oldest_first(bars)
    if len(bars) < MA_N + ATR_N + 2:
        return None
    atr, sma = atr_series(bars), sma_series(bars)
    states = state_series(bars, atr, sma)
    closes = [b["close"] for b in bars]

    res = {"bars": len(bars), "first": bars[0]["date"], "last": bars[-1]["date"]}

    for label, h in HORIZONS:
        hit = n = 0
        for i, st in enumerate(states):
            if st == "WATCH" or i + h >= len(closes):
                continue
            n += 1
            moved_up = closes[i + h] > closes[i]
            if (st == "IN") == moved_up:
                hit += 1
        res[label] = (hit / n * 100, n) if n else (None, 0)

    # range containment at 1D: did tomorrow's close land inside today's band?
    inside = n = 0
    for i in range(len(bars) - 1):
        if atr[i] is None:
            continue
        lo, hi = closes[i] - BAND * atr[i], closes[i] + BAND * atr[i]
        n += 1
        if lo <= closes[i + 1] <= hi:
            inside += 1
    res["band"] = (inside / n * 100, n) if n else (None, 0)
    return res


def colour(pct: float | None, good: float, ok: float) -> str:
    if pct is None:
        return D
    return G if pct >= good else (Y if pct >= ok else R)


ACC_FILE = os.path.join(HERE, "accuracy.json")


def main() -> None:
    risk = json.load(open(os.path.join(HERE, "config.json")))
    args = [a for a in sys.argv[1:] if a != "--save"]
    save = "--save" in sys.argv
    symbols = args or list(dict.fromkeys(risk["watchlist"]))
    saved = {}

    print(f"{D}Advice accuracy — regime call scored on price alone, "
          f"lookahead-free replay{X}\n")
    print(f"{B}{'':<7}{'1D':>12}{'1M':>12}{'1Y':>12}{'band 1D':>12}   {'history':<24}{X}")

    agg = {k: [0, 0] for k, _ in HORIZONS}
    agg["band"] = [0, 0]

    for sym in symbols:
        s = score(feed.bars(sym, count=800))
        if not s:
            print(f"{B}{sym:<7}{X}{D}{'not enough history — no score':>48}{X}")
            continue
        cells = ""
        for label, _ in HORIZONS:
            pct, n = s[label]
            cells += f"{colour(pct, 55, 50)}{pct:>10.0f}%{X}" if pct is not None else f"{D}{'—':>11}{X}"
            if pct is not None:
                agg[label][0] += pct * n
                agg[label][1] += n
        bpct, bn = s["band"]
        cells += f"{colour(bpct, 70, 60)}{bpct:>11.0f}%{X}"
        agg["band"][0] += bpct * bn
        agg["band"][1] += bn
        print(f"{B}{sym:<7}{X}{cells}   {D}{s['bars']} bars {s['first']}→{s['last']}{X}")
        saved[sym] = {"d1": s["1D"][0], "m1": s["1M"][0], "y1": s["1Y"][0],
                      "band": s["band"][0], "bars": s["bars"], "last": s["last"]}

    print()
    line = f"{B}{'ALL':<7}{X}"
    for label, _ in HORIZONS:
        tot, n = agg[label]
        line += f"{colour(tot/n if n else None, 55, 50)}{tot/n:>10.0f}%{X}" if n else f"{D}{'—':>11}{X}"
    tot, n = agg["band"]
    line += f"{colour(tot/n if n else None, 70, 60)}{tot/n:>11.0f}%{X}" if n else ""
    print(line)
    if save:
        import datetime
        json.dump({"generated": datetime.date.today().isoformat(), "tickers": saved},
                  open(ACC_FILE, "w"), indent=1)
        print(f"\n{D}saved -> {os.path.basename(ACC_FILE)}{X}")
    print(f"\n{D}1D/1M/1Y = share of days the regime call matched the price move over that "
          f"horizon.\nband 1D = share of days the next close landed inside the stated range.\n"
          f"50% on direction is a coin flip. The band is where the edge should show.{X}")


if __name__ == "__main__":
    main()
