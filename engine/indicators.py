#!/usr/bin/env python3
"""Indicators and the call, computed locally. See plan.html §5.

Every function here exists because it feeds a line of the card. Nothing is
computed "in case it is useful" — that is how the last build grew a scoring
layer nobody could interpret.

No lookahead (plan R8): the state series is walked forward, one bar at a time,
and the call for bar i uses bars 0..i only.
"""
from __future__ import annotations

ATR_N = 14
MA_N = 20
BAND = 0.8          # range half-width in ATRs. CALIBRATED 2026-08-27 by sweeping 0.5-1.3 over
                    # 800 bars x 7 tickers: 0.8 gives 82% next-close containment (per-ticker
                    # 77-89%). The inherited 1.3 gave 93% — a band that is almost never wrong
                    # is also almost never actionable. Re-run engine calibration before changing.
HYST = 0.25         # hysteresis around the MA, in ATRs, so state does not flip on noise


def _sorted_oldest_first(bars: list[dict]) -> list[dict]:
    return sorted(bars, key=lambda b: b["date"])


def true_range(cur: dict, prev: dict | None) -> float:
    if prev is None:
        return cur["high"] - cur["low"]
    return max(cur["high"] - cur["low"],
               abs(cur["high"] - prev["close"]),
               abs(cur["low"] - prev["close"]))


def atr_series(bars: list[dict], n: int = ATR_N) -> list[float | None]:
    """Wilder's ATR. None until there are n bars."""
    trs, out, prev_atr = [], [], None
    for i, b in enumerate(bars):
        trs.append(true_range(b, bars[i - 1] if i else None))
        if i + 1 < n:
            out.append(None)
        elif i + 1 == n:
            prev_atr = sum(trs) / n
            out.append(prev_atr)
        else:
            prev_atr = (prev_atr * (n - 1) + trs[-1]) / n
            out.append(prev_atr)
    return out


def sma_series(bars: list[dict], n: int = MA_N) -> list[float | None]:
    out, run = [], 0.0
    for i, b in enumerate(bars):
        run += b["close"]
        if i >= n:
            run -= bars[i - n]["close"]
        out.append(run / n if i + 1 >= n else None)
    return out


def state_series(bars: list[dict], atr: list, sma: list) -> list[str]:
    """IN / OUT / WATCH, walked forward with hysteresis.

    IN  once close rises above sma + HYST*atr
    OUT once close falls below sma - HYST*atr
    otherwise the previous state persists (this is the hysteresis)
    """
    out, state = [], "WATCH"
    for i, b in enumerate(bars):
        if atr[i] is None or sma[i] is None:
            out.append("WATCH")
            continue
        upper, lower = sma[i] + HYST * atr[i], sma[i] - HYST * atr[i]
        if b["close"] > upper:
            state = "IN"
        elif b["close"] < lower:
            state = "OUT"
        out.append(state)
    return out


def analyse(symbol: str, bars: list[dict], risk: dict, live_price: float | None = None,
            held: dict | None = None) -> dict:
    """One ticker -> everything the card needs, or a reason there is no call.

    The model produces a REGIME (in/out of trend). The ACTION comes from that
    regime crossed with what YY actually holds — the two are not the same thing
    and conflating them is what made the first version say HOLD to a flat book:

        held + regime IN   -> HOLD          held + regime OUT  -> SELL
        flat + regime IN   -> BUY           flat + regime OUT  -> STAND ASIDE

    Never returns a guess. Missing or insufficient data yields status NO_DATA
    (plan R9); an illiquid name yields NO_TRADE.
    """
    bars = _sorted_oldest_first(bars)
    if len(bars) < MA_N + ATR_N:
        return {"symbol": symbol, "action": "NO_DATA",
                "why": f"only {len(bars)} bars, need {MA_N + ATR_N}"}

    atr, sma = atr_series(bars), sma_series(bars)
    states = state_series(bars, atr, sma)
    last, a, m, state = bars[-1], atr[-1], sma[-1], states[-1]
    price = live_price if live_price else last["close"]

    # Liquidity gate. This blocks NEW entries only — it must never silence advice
    # on a position YY already holds. Holding 5,000 thin shares at a loss and being
    # told "NO TRADE" is worse than no card at all.
    adv = sum(b["close"] * b["volume"] for b in bars[-20:]) / 20
    thin = adv < risk["min_avg_dollar_volume"]
    thin_why = (f"thin — 20d avg ${adv/1e6:.1f}M below "
                f"${risk['min_avg_dollar_volume']/1e6:.0f}M floor")

    # today's expected band, anchored driftless on the prior close
    lo, hi = last["close"] - BAND * a, last["close"] + BAND * a
    invalidation = m - HYST * a           # the level at which state flips to OUT

    per_share = price - invalidation
    qty = held["qty"] if held else 0

    res = {"symbol": symbol, "regime": state, "price": price,
           "change_pct": (price / bars[-2]["close"] - 1) * 100,
           "atr": a, "sma": m, "range_lo": lo, "range_hi": hi,
           "invalidation": invalidation, "last_bar": last["date"],
           "held_qty": qty, "reentry": m + HYST * a}
    if held:
        res["cost"] = held["cost"]
        res["upl"] = held["upl"]

    if state == "WATCH":
        res["action"] = "HOLD" if qty else "NO_TRADE"
        if not qty:
            res["why"] = thin_why if thin else \
                "no regime established — price inside the hysteresis band"
        return res

    if thin:
        res["thin"] = thin_why

    if state == "IN":
        if qty:
            res["action"] = "HOLD"
        elif thin:
            res["action"] = "NO_TRADE"
            res["why"] = thin_why
        elif per_share > 0:
            res["action"] = "BUY"
            # Risk is a property of the stock, not of the account (plan R14):
            # how far price must fall to prove the call wrong, as a % of entry.
            res["risk_pct"] = per_share / price * 100
        else:
            res["action"] = "NO_TRADE"
            res["why"] = "price already below invalidation — no valid stop"
    else:                                   # regime OUT
        res["action"] = "SELL" if qty else "STAND_ASIDE"
    return res
