#!/usr/bin/env python3
"""Fetch daily OHLCV for the i004 watchlist and merge into data/bars.csv.

Runs on GitHub Actions, which has unrestricted internet. The Claude cloud sandbox
does NOT — every finance host is CONNECT-403 blocked there, but
raw.githubusercontent.com returns 200. So GitHub fetches; Claude reads.

Idempotent: re-running for a day already stored changes nothing.
"""
import csv, io, json, os, sys, time, urllib.request, datetime, zoneinfo

ET = zoneinfo.ZoneInfo("America/New_York")
SYMBOLS = ["PLTU", "BULL", "ORBS", "SPCX", "LIDR", "ORCL", "PLTR"]
OUT = "data/bars.csv"
COLS = ["date", "ticker", "open", "high", "low", "close", "volume"]
VALID_RANGES = {"5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"}


def fetch(sym, rng="5d"):
    # MEASURED: Yahoo does NOT error on a bad range string, it silently returns ONE bar.
    if rng not in VALID_RANGES:
        raise SystemExit(f"invalid range {rng!r}")
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
         f"?interval=1d&range={rng}")
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    res = (d.get("chart") or {}).get("result")
    if not res:
        raise RuntimeError(f"{sym}: empty chart result")
    r = res[0]
    q = (r.get("indicators") or {}).get("quote", [{}])[0]
    rows = []
    for i, t in enumerate(r.get("timestamp") or []):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue                       # real feed gap - recorded as absent, never faked
        rows.append({"date": str(datetime.datetime.fromtimestamp(t, ET).date()),
                     "ticker": sym, "open": o, "high": h, "low": l, "close": c,
                     "volume": q["volume"][i] or 0})
    if not rows:
        raise RuntimeError(f"{sym}: 0 usable bars from range={rng}")
    return rows


def load():
    if not os.path.exists(OUT):
        return {}
    with open(OUT) as f:
        return {(r["date"], r["ticker"]): r for r in csv.DictReader(f)}


def main():
    rng = sys.argv[1] if len(sys.argv) > 1 else "5d"
    have = load()
    added = 0
    for s in SYMBOLS:
        try:
            for row in fetch(s, rng):
                k = (row["date"], row["ticker"])
                if k not in have:
                    have[k] = row
                    added += 1
        except Exception as e:
            print(f"::warning::{s} FETCH_FAILED {e}")
        time.sleep(0.7)
    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for k in sorted(have):
            w.writerow({c: have[k][c] for c in COLS})
    print(f"rows total {len(have)}, added {added}")


if __name__ == "__main__":
    main()
