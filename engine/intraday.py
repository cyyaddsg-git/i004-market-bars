#!/usr/bin/env python3
"""Intraday read for one symbol -> a concrete order setting.

    python engine/intraday.py NVDA [M5] [--json]

Plan R15. The daily engine is a ~2-week swing filter (measured: median hold 10
trading days) and has no intraday meaning, so NOTHING here is imported from it.
This is its own rule, on its own bars, with its own levels.

The rule -- deliberately the plainest thing that is actually traded intraday,
so that when it is scored we learn something about the FRAMEWORK rather than
about a pile of tuned parameters:

    LONG   price > VWAP and price > opening-range high
           stop  = max(opening-range high, VWAP) - STOP_PAD * ATR
    SHORT  price < VWAP and price < opening-range low
           stop  = min(opening-range low, VWAP) + STOP_PAD * ATR
    else   NO SETUP -- say so, never manufacture one

Target is R_MULT x the risk. Size puts RISK_PCT of CAPITAL between entry and
stop. No fees, matching the paper book.

Everything is computed from bars. Nothing here is a judgement call, so the same
inputs always give the same order setting and it can be replayed and scored.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import feed                                                    # noqa: E402

ORB_MIN = 30          # opening range = first 30 minutes
STOP_PAD = 0.25       # ATRs of air beyond the level, so noise does not stop you
R_MULT = 2.0          # target distance, in units of risk
CAPITAL = 100_000.0   # same book as engine/sim.py
RISK_PCT = 0.01
MAX_WEIGHT = 0.20

SPAN_MIN = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "M60": 60}


def bars(symbol: str, timespan: str = "M5", count: int = 200) -> list[dict]:
    """Full-timestamp intraday bars. feed.bars() truncates `time` to a date,
    which is fine for daily and useless here."""
    r = feed.client().data.market_data.get_history_bar(
        symbol=symbol, category="US_STOCK", timespan=timespan, count=count)
    data = r.json() if hasattr(r, "json") else r
    if not isinstance(data, list):
        raise SystemExit(f"{symbol}: unexpected payload {type(data).__name__} — not guessing at it")
    out = []
    for b in data:
        try:
            out.append({"t": b["time"], "o": float(b["open"]), "h": float(b["high"]),
                        "l": float(b["low"]), "c": float(b["close"]), "v": float(b["volume"])})
        except (KeyError, TypeError, ValueError):
            continue
    out.sort(key=lambda b: b["t"])
    return out


def atr(bs: list[dict], n: int = 14) -> float | None:
    if len(bs) < n + 1:
        return None
    trs = [max(c["h"] - c["l"], abs(c["h"] - p["c"]), abs(c["l"] - p["c"]))
           for p, c in zip(bs, bs[1:])]
    a = sum(trs[:n]) / n
    for tr in trs[n:]:
        a = (a * (n - 1) + tr) / n
    return a


def read(symbol: str, timespan: str = "M5") -> dict:
    bs = bars(symbol, timespan)
    if not bs:
        raise SystemExit(f"{symbol}: the API returned no {timespan} bars — "
                         f"a FAILED read, not 'no data'")

    days = sorted({b["t"][:10] for b in bs})
    day = days[-1]
    today = [b for b in bs if b["t"][:10] == day]
    prior = [b for b in bs if b["t"][:10] == days[-2]] if len(days) > 1 else []
    last = bs[-1]
    px = last["c"]

    vol = sum(b["v"] for b in today)
    vwap = (sum((b["h"] + b["l"] + b["c"]) / 3 * b["v"] for b in today) / vol) if vol else None
    a = atr(bs)

    n_orb = max(1, ORB_MIN // SPAN_MIN.get(timespan, 5))
    orb = today[:n_orb]
    orh = max(b["h"] for b in orb) if orb else None
    orl = min(b["l"] for b in orb) if orb else None

    out = {
        "symbol": symbol, "timespan": timespan, "session": day,
        "last_bar": last["t"], "price": round(px, 4), "bars_today": len(today),
        "vwap": round(vwap, 4) if vwap else None,
        "atr": round(a, 4) if a else None,
        "session_high": round(max(b["h"] for b in today), 4),
        "session_low": round(min(b["l"] for b in today), 4),
        "orb_high": round(orh, 4) if orh else None,
        "orb_low": round(orl, 4) if orl else None,
        "orb_bars": len(orb),
        "prior_close": round(prior[-1]["c"], 4) if prior else None,
        "prior_high": round(max(b["h"] for b in prior), 4) if prior else None,
        "prior_low": round(min(b["l"] for b in prior), 4) if prior else None,
        "volume": vol,
    }

    # --- the setup -----------------------------------------------------------
    # The opening range must have actually FORMED. With one bar traded, orh/orl
    # exist but describe a single candle, and the rule would fire on nothing.
    if not (vwap and a and orh and orl) or len(orb) < n_orb:
        need = n_orb - len(orb)
        out.update(side="NO SETUP",
                   why=(f"the opening {ORB_MIN} minutes are not complete — "
                        f"{len(orb)}/{n_orb} bars in, {need} to go"
                        if len(orb) < n_orb else
                        "not enough of the session has traded to have a VWAP and an ATR"))
        return out

    if px > vwap and px > orh:
        side, stop = "LONG", max(orh, vwap) - STOP_PAD * a
    elif px < vwap and px < orl:
        side, stop = "SHORT", min(orl, vwap) + STOP_PAD * a
    else:
        where = ("between VWAP and the opening range" if orl <= px <= orh
                 else "on the wrong side of VWAP for its position in the range")
        out.update(side="NO SETUP",
                   why=f"price {px:.2f} is {where} — VWAP {vwap:.2f}, "
                       f"opening range {orl:.2f}–{orh:.2f}. No edge either way.")
        return out

    # Round entry and stop FIRST, then derive everything from the rounded pair.
    # These numbers get typed into a broker, so they must be exactly consistent
    # with each other -- deriving the target from unrounded values gave 2.002R.
    entry, stop = round(px, 2), round(stop, 2)
    risk_ps = round(abs(entry - stop), 2)
    if risk_ps <= 0:
        out.update(side="NO SETUP", why="stop computed at or through the entry")
        return out

    target = round(entry + R_MULT * risk_ps if side == "LONG"
                   else entry - R_MULT * risk_ps, 2)
    qty = min(int(CAPITAL * RISK_PCT / risk_ps), int(CAPITAL * MAX_WEIGHT / entry))

    out.update(
        side=side,
        entry=entry, stop=stop, target=target,
        risk_per_share=risk_ps, risk_pct_of_price=round(risk_ps / entry * 100, 2),
        qty=qty, risk_dollars=round(qty * risk_ps, 2),
        notional=round(qty * entry, 2), r_multiple=R_MULT,
        why=(f"price {px:.2f} {'above' if side == 'LONG' else 'below'} both VWAP "
             f"{vwap:.2f} and the opening range "
             f"({orl:.2f}–{orh:.2f}); stop is {STOP_PAD} ATR beyond the nearer level"))
    return out


def render(r: dict) -> str:
    L = [f"\n{r['symbol']} · {r['timespan']} · session {r['session']} · "
         f"latest bar {r['last_bar']}  ({r['bars_today']} bars in)"]
    L.append("")
    if r["side"] == "NO SETUP":
        L += [f"  NO SETUP", f"  {r['why']}", ""]
    else:
        L += [f"  {r['side']}  entry {r['entry']}   stop {r['stop']}   target {r['target']}",
              f"        qty {r['qty']}   risk ${r['risk_dollars']:,.0f} "
              f"({r['risk_per_share']} /sh, {r['risk_pct_of_price']}% of price)   "
              f"notional ${r['notional']:,.0f}   {r['r_multiple']}R",
              f"        {r['why']}", ""]
    L += [f"  price {r['price']}   VWAP {r['vwap']}   ATR {r['atr']}",
          f"  session {r['session_low']} – {r['session_high']}   "
          f"opening {ORB_MIN}m {r['orb_low']} – {r['orb_high']}",
          f"  prior day  close {r['prior_close']}  high {r['prior_high']}  low {r['prior_low']}",
          f"  volume {r['volume']:,.0f}", ""]
    return "\n".join(L)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sym = (args[0] if args else "NVDA").upper()
    span = args[1] if len(args) > 1 else "M5"
    r = read(sym, span)
    if "--json" in sys.argv:
        print("JSON_BEGIN")
        print(json.dumps(r, indent=1))
        print("JSON_END")
    else:
        print(render(r))


if __name__ == "__main__":
    main()
