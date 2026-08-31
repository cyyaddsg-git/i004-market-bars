#!/usr/bin/env python3
"""
Which stocks this engine should be trading at all, decided by rule from measured bars.

    python3 engine/universe.py            # print the selection and every rejection
    python3 engine/universe.py --write    # also rewrite config.json's watchlist

WHY (YY, 2026-08-31): "deep think the buy sell strategy should target what stock, eg top
active, technology stock? then play according to it."

THE ARGUMENT, from what this engine actually claims to be good at.

Its own acceptance test (plan.html §1) scores RANGE CONTAINMENT, invalidation discipline
and no-trade discipline -- and deliberately does NOT score direction, because the previous
build called direction 0/6 and daily direction is close to a coin flip. So the engine is,
honestly, a volatility-and-discipline model: it says how far a name is likely to travel,
where the idea is wrong, and how much to size. Everything follows from that.

A name suits this engine when its RANGE IS MEASURABLE AND TRADEABLE:

  1. Price high enough that the tick is noise, not the signal. At $0.82 a one-cent spread
     is 1.2% of price -- comparable to the whole edge being modelled. ORBS was in the
     watchlist at $0.82 and the book bought 10,022 shares of it.
  2. Deep enough that the position is a rounding error in the day's volume. The old
     $5M ADV floor let names in where a 20%-of-book position is a meaningful share of
     daily turnover, so the fill price the backtest assumes is not the fill price reality
     would give.
  3. Volatility in a usable band. Below ~1.5% ATR there is no range worth trading after
     costs; above ~6% the ATR-based stop is so wide that risk sizing returns a token
     position, and the gap risk the model does not price starts to dominate.
  4. NOT A LEVERAGED OR INVERSE PRODUCT. This is the sharpest exclusion. PLTU is 2x PLTR:
     its ATR is roughly twice the underlying's and its return is path-dependent through
     daily rebalancing, so a band fitted on ordinary equity behaviour does not transfer,
     and holding it overnight is a different bet from the one the card describes. The old
     watchlist held three such products (PLTU, BULL, SPCX) out of seven names.

Point 4 also answers YY's question directly: TOP-ACTIVE LARGE-CAP TECHNOLOGY, which is
what NASDAQ is mostly made of, is the right target -- not because technology is special,
but because that is where price, depth and volatility all sit in the usable band at once.
Rank by dollar volume x ATR%: activity that actually moves, rather than activity alone.

REVIEWED MONTHLY, NOT DAILY. A universe that re-picks every day is fitting to yesterday,
and the scoring log could never separate the model's skill from the churn.

HONEST LIMIT: `CANDIDATES` is a hand-kept pool of large NASDAQ names, not a live index
membership feed. It is a POOL, not the answer -- the rules below do the choosing from
measured bars, so a name that does not belong is filtered on its own numbers, and a
ticker that does not exist simply has no bars and is reported as such.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(HERE, "config.json")
BARS = os.path.join(os.path.dirname(HERE), "data", "bars.csv")

# Large, liquid NASDAQ names. A POOL to filter, never the selection itself.
CANDIDATES = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "AMD", "NFLX",
    "ADBE", "INTC", "QCOM", "TXN", "AMAT", "MU", "LRCX", "KLAC", "PANW", "CRWD",
    "SNPS", "CDNS", "MRVL", "ADI", "INTU", "ORCL", "PLTR", "SMCI", "ASML", "ARM",
]

# Anything matching these is a leveraged, inverse or single-stock derivative product.
LEVERAGE_MARKERS = ("2X", "3X", "ULTRA", "BULL", "BEAR", "INVERSE", "LEVERAGED")

RULES = {
    "price_min": 20.0,          # a cent of spread must be small against the move
    "adv_min": 100_000_000.0,   # 20-day average dollar volume
    "atr_pct_min": 0.015,
    "atr_pct_max": 0.060,
    "take": 8,
}


def load_bars():
    import csv
    out = {}
    if not os.path.exists(BARS):
        return out
    with open(BARS, newline="") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["ticker"], []).append(r)
    for t in out:
        out[t].sort(key=lambda b: b["date"])
    return out


def atr_pct(series, n=14):
    """ATR(n) as a fraction of the last close. True range, not high-low."""
    if len(series) < n + 1:
        return None
    trs = []
    for prev, cur in zip(series[-n - 1:-1], series[-n:]):
        h, l, pc = float(cur["high"]), float(cur["low"]), float(prev["close"])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    close = float(series[-1]["close"])
    return (sum(trs) / len(trs)) / close if close else None


def adv(series, n=20):
    tail = series[-n:]
    if not tail:
        return None
    return sum(float(b["close"]) * float(b["volume"]) for b in tail) / len(tail)


def select(bars, rules=RULES, candidates=None):
    """-> (picked, rejected). Every rejection carries the number that caused it, so the
    universe can be argued with rather than taken on trust."""
    picked, rejected = [], []
    for t in (candidates or CANDIDATES):
        if any(m in t.upper() for m in LEVERAGE_MARKERS):
            rejected.append((t, "leveraged/inverse product — a band fitted on ordinary "
                                "equity behaviour does not transfer"))
            continue
        s = bars.get(t) or []
        if len(s) < 21:
            rejected.append((t, f"only {len(s)} bar(s) — cannot measure ATR or ADV"))
            continue
        px, a, v = float(s[-1]["close"]), atr_pct(s), adv(s)
        if px < rules["price_min"]:
            rejected.append((t, f"price ${px:,.2f} < ${rules['price_min']:,.0f}"))
            continue
        if v is None or v < rules["adv_min"]:
            rejected.append((t, f"ADV ${(v or 0)/1e6:,.0f}M < ${rules['adv_min']/1e6:,.0f}M"))
            continue
        if a is None or not (rules["atr_pct_min"] <= a <= rules["atr_pct_max"]):
            rejected.append((t, f"ATR {a*100:.2f}% outside "
                                f"{rules['atr_pct_min']*100:.1f}–{rules['atr_pct_max']*100:.1f}%"))
            continue
        picked.append({"ticker": t, "price": px, "adv": v, "atr_pct": a,
                       "score": v * a})
    picked.sort(key=lambda x: -x["score"])
    return picked[:rules["take"]], rejected


def main():
    bars = load_bars()
    if not bars:
        sys.exit(f"no bars at {BARS} — run fetch.py first. Selecting a universe without "
                 f"measured bars would be picking names by opinion, which is the thing "
                 f"this file exists to stop.")
    picked, rejected = select(bars)
    print(f"pool {len(CANDIDATES)} · bars on {sum(1 for t in CANDIDATES if bars.get(t))} "
          f"· picked {len(picked)}")
    print(f"\n{'ticker':<8}{'price':>10}{'ADV $M':>10}{'ATR%':>8}{'score':>12}")
    for p in picked:
        print(f"{p['ticker']:<8}{p['price']:>10,.2f}{p['adv']/1e6:>10,.0f}"
              f"{p['atr_pct']*100:>7.2f}%{p['score']/1e6:>12,.0f}")
    print("\nrejected:")
    for t, why in rejected:
        print(f"  {t:<8}{why}")
    if "--write" in sys.argv:
        cfg = json.load(open(CFG))
        cfg["watchlist"] = [p["ticker"] for p in picked]
        cfg["universe_rules"] = RULES
        json.dump(cfg, open(CFG, "w"), indent=1)
        print(f"\nwatchlist written: {cfg['watchlist']}")


if __name__ == "__main__":
    main()
