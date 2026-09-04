#!/usr/bin/env python3
"""Prebuild the 1D/5D/1M card for every ticker YY might type.

    python engine/build_horizons.py [--limit N] [--only SYM ...]

Writes docs/h/<SYM>.json (one small file each) plus docs/h/index.json.

WHY PREBUILD, AND WHY ONE FILE PER SYMBOL (plan §10):
  A browser cannot reach any quote API — Yahoo and Stooq are both CORS-blocked
  from the Pages origin, MEASURED 2026-09-04 — and the page is public, so it can
  hold no token to call one through a proxy. Prebuilding removes the whole
  problem: one symbol serialises to ~1.4 KB, so the answer is already on disk
  before YY types. Per-symbol files mean the phone downloads 1.4 KB, not the
  whole set.

PUBLIC OUTPUT — account=False everywhere. These files are served from a public
repo; nothing here may carry a holding, a quantity or a P&L (plan R12).

Bars come from Yahoo, not Webull: this runs over hundreds of symbols in CI, and
Yahoo is the path bars.yml already proves at that volume.
"""
from __future__ import annotations

import datetime
import json
import os
import sys
import time
import urllib.request
import zoneinfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import horizons                                                # noqa: E402
from indicators import MA_N, ATR_N                             # noqa: E402

OUT = os.path.normpath(os.path.join(HERE, "..", "docs", "h"))
UA = {"User-Agent": "Mozilla/5.0"}
# Bar dates are ET, not UTC. fetch.py already learned this; a UTC date would
# shift a bar into the wrong day and silently misalign every horizon.
ET = zoneinfo.ZoneInfo("America/New_York")
MIN_BARS = MA_N + ATR_N + 2 + 21          # + the longest horizon, or 1M cannot score


def nasdaq_top(limit: int) -> list[str]:
    """Largest NASDAQ names by market cap, from Nasdaq's own screener.

    Fetched rather than hard-coded so the list does not rot. A hard-coded top-100
    is wrong within a quarter and nobody notices until YY types a name that is
    missing.
    """
    u = ("https://api.nasdaq.com/api/screener/stocks"
         "?tableonly=true&limit=5000&exchange=NASDAQ&download=true")
    req = urllib.request.Request(u, headers={**UA, "Accept": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=45))["data"]
    rows = d.get("rows") or d["table"]["rows"]
    out = []
    for r in rows:
        try:
            cap = float(r["marketCap"] or 0)
        except (TypeError, ValueError):
            continue
        sym = r["symbol"].strip().upper()
        if cap > 0 and sym.isalpha():      # skip warrants/units — ^ / . / digits
            out.append((cap, sym))
    out.sort(reverse=True)
    return [s for _, s in out[:limit]]


def yahoo_bars(sym: str, rng: str = "5y") -> list[dict]:
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
         f"?interval=1d&range={rng}")
    d = json.load(urllib.request.urlopen(
        urllib.request.Request(u, headers=UA), timeout=30))
    res = (d.get("chart") or {}).get("result")
    if not res:
        raise RuntimeError("empty chart result")
    r = res[0]
    q = (r.get("indicators") or {}).get("quote", [{}])[0]
    rows = []
    for i, t in enumerate(r.get("timestamp") or []):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue                       # a feed gap is dropped, never filled in
        rows.append({"date": str(datetime.datetime.fromtimestamp(t, ET).date()),
                     "open": o, "high": h, "low": l, "close": c,
                     "volume": q["volume"][i] or 0})
    # Drop today's bar while the session is still running. MEASURED 2026-09-04:
    # Yahoo returns an IN-PROGRESS bar for the current day, so its "close" is just
    # the live price. Feeding that to a daily-close rule anchors the band on half a
    # day and shifts every MA. Webull serves completed bars only; this keeps the
    # public card and the terminal card reading the same history.
    now = datetime.datetime.now(ET)
    closed = now.weekday() < 5 and now.time() >= datetime.time(16, 15)
    today = str(now.date())
    if rows and rows[-1]["date"] == today and not closed:
        rows.pop()
    return rows[-800:]


def suitability(r: dict, rules: dict, bars: list[dict]) -> dict:
    """Is this a name the model was built for? Printed on the card either way.

    Any-ticker means cards for names that fail the universe rule. Their accuracy
    and edge are still computed from their own bars, so the numbers are honest —
    but without this verdict the tab quietly advises on a $0.82 stock again
    (the ORBS lesson, 2026-08-31).
    """
    adv = sum(b["close"] * b["volume"] for b in bars[-20:]) / 20
    fails = []
    if r["price"] < rules["price_min"]:
        fails.append(f"price ${r['price']:,.2f} below ${rules['price_min']:.0f}")
    if adv < rules["adv_min"]:
        fails.append(f"20d volume ${adv/1e6:.0f}M below ${rules['adv_min']/1e6:.0f}M")
    atr = r["atr_pct"] / 100
    if atr < rules["atr_pct_min"]:
        fails.append(f"ATR {r['atr_pct']:.1f}% below {rules['atr_pct_min']*100:.1f}%")
    elif atr > rules["atr_pct_max"]:
        fails.append(f"ATR {r['atr_pct']:.1f}% above {rules['atr_pct_max']*100:.1f}%")
    return {"ok": not fails, "adv": adv, "fails": fails}


def symbols(limit: int) -> list[str]:
    cfg = json.load(open(os.path.join(HERE, "config.json")))
    syms = list(dict.fromkeys(cfg["watchlist"]))          # the measured universe first
    try:
        import sim
        syms += [t for t, p in sim.replay()["positions"].items()
                 if p["qty"] > 0 and t not in syms]
    except Exception:
        pass
    for s in nasdaq_top(limit):
        if s not in syms:
            syms.append(s)
    return syms


def main() -> None:
    a = sys.argv[1:]
    limit = int(a[a.index("--limit") + 1]) if "--limit" in a else 250
    only = a[a.index("--only") + 1:] if "--only" in a else None
    rules = json.load(open(os.path.join(HERE, "config.json")))["universe_rules"]

    syms = only or symbols(limit)
    os.makedirs(OUT, exist_ok=True)
    built, failed = [], []
    for i, sym in enumerate(syms, 1):
        try:
            bars = yahoo_bars(sym)
            if len(bars) < MIN_BARS:
                raise RuntimeError(f"{len(bars)} bars, need {MIN_BARS}")
            r = horizons.evaluate(sym, bars=bars, account=False)
            r.pop("held", None)                       # belt and braces: public file
            r["suitability"] = suitability(r, rules, bars)
            with open(os.path.join(OUT, f"{sym}.json"), "w") as f:
                json.dump(r, f, separators=(",", ":"), default=str)
            built.append(sym)
        except Exception as e:
            failed.append(sym)
            print(f"::warning::{sym} SKIPPED {type(e).__name__}: {e}")
        if i % 25 == 0:
            print(f"  {i}/{len(syms)} …", flush=True)
        time.sleep(0.4)

    if not built:
        raise SystemExit("EXTRACTION FAILED — 0 symbols built, refusing to write an "
                         "index that would make the tab look empty rather than broken")

    idx = {"generated": datetime.datetime.now(datetime.timezone.utc)
                                .strftime("%Y-%m-%d %H:%M UTC"),
           "count": len(built), "symbols": sorted(built)}
    with open(os.path.join(OUT, "index.json"), "w") as f:
        json.dump(idx, f, separators=(",", ":"))
    size = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
    print(f"built {len(built)}, skipped {len(failed)}, {size/1024:.0f} KB total")


if __name__ == "__main__":
    main()
