#!/usr/bin/env python3
"""The out-of-sample record: what the card actually said, and what happened next.

    python engine/predictions.py          # settle what is due, then print the table
    python engine/predictions.py --log    # (used by daily.py) log today, then settle

Why this exists
---------------
`score.py` measures the rule by replaying it over history. That is honest as far
as it goes, but BAND was calibrated by sweeping 0.5-1.3 over the same bars it is
then scored on, so the backtest figure is in-sample and optimistic by an unknown
amount. The only cure is a record of advice issued BEFORE the outcome was known.

`docs/index.html` is overwritten every run, so it is not that record. This file
is: one row per ticker per trading day, appended at issue time, settled later
from `data/bars.csv` alone -- no API call, no second source, nothing to drift.

Scoring is deliberately IDENTICAL to score.py so the two numbers are comparable:

    dir_hit   regime IN  -> correct if next_close > base_close
              regime OUT -> correct if next_close < base_close
              (WATCH is not scored, exactly as in the replay)
    band_hit  range_lo <= next_close <= range_hi

Both are anchored on the prior close, which is what indicators.py bands on too.
"""
from __future__ import annotations

import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PRED = os.path.join(REPO, "data", "predictions.csv")
BARS = os.path.join(REPO, "data", "bars.csv")

COLS = ["issued_date", "ticker", "regime", "action", "price", "base_close",
        "range_lo", "range_hi", "invalidation", "bar_date",
        "settle_date", "settle_close", "dir_hit", "band_hit"]


def _read() -> list[dict]:
    if not os.path.exists(PRED):
        return []
    with open(PRED, newline="") as f:
        return list(csv.DictReader(f))


def _write(rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(PRED), exist_ok=True)
    with open(PRED, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)


def _bars_by_ticker() -> dict[str, list[dict]]:
    """Every bar we have on disk, oldest first, keyed by ticker."""
    out: dict[str, list[dict]] = {}
    if not os.path.exists(BARS):
        return out
    with open(BARS, newline="") as f:
        for b in csv.DictReader(f):
            out.setdefault(b["ticker"], []).append(b)
    for t in out:
        out[t].sort(key=lambda b: b["date"])
    return out


def log(card_rows: list[dict], issued_date: str) -> int:
    """Append one row per ticker for `issued_date`. Idempotent: a second run on
    the same day updates nothing and adds nothing, so a manual re-run or a
    retried Action can never double-count."""
    rows = _read()
    seen = {(r["issued_date"], r["ticker"]) for r in rows}
    added = 0
    for r in card_rows:
        if r.get("action") == "NO_DATA":
            continue                      # nothing was claimed, so nothing to score
        key = (issued_date, r["symbol"])
        if key in seen:
            continue
        rows.append({
            "issued_date": issued_date,
            "ticker": r["symbol"],
            "regime": r.get("regime", ""),
            "action": r.get("action", ""),
            "price": f"{r['price']:.6f}",
            "base_close": "",             # filled at settle time from bars.csv
            "range_lo": f"{r['range_lo']:.6f}",
            "range_hi": f"{r['range_hi']:.6f}",
            "invalidation": f"{r['invalidation']:.6f}",
            "bar_date": r.get("last_bar", ""),
            "settle_date": "", "settle_close": "", "dir_hit": "", "band_hit": "",
        })
        added += 1
    if added:
        _write(rows)
    return added


def settle() -> int:
    """Fill in the outcome of every row whose next bar has since arrived.

    A row is settled from the first bar STRICTLY AFTER its own bar_date. If that
    bar is not on disk yet the row is left alone -- never padded, never assumed,
    the same discipline score.py applies to horizons that run off the end."""
    rows = _read()
    if not rows:
        return 0
    bars = _bars_by_ticker()
    settled = 0
    for r in rows:
        if r["settle_date"]:
            continue
        series = bars.get(r["ticker"], [])
        base = next((b for b in series if b["date"] == r["bar_date"]), None)
        nxt = next((b for b in series if b["date"] > r["bar_date"]), None)
        if not base or not nxt:
            continue
        base_close, settle_close = float(base["close"]), float(nxt["close"])
        r["base_close"] = f"{base_close:.6f}"
        r["settle_date"] = nxt["date"]
        r["settle_close"] = f"{settle_close:.6f}"
        # WATCH makes no directional claim, so it is not scored -- as in score.py.
        if r["regime"] in ("IN", "OUT"):
            moved_up = settle_close > base_close
            r["dir_hit"] = "1" if (r["regime"] == "IN") == moved_up else "0"
        r["band_hit"] = "1" if float(r["range_lo"]) <= settle_close <= float(r["range_hi"]) else "0"
        settled += 1
    if settled:
        _write(rows)
    return settled


def summary() -> dict:
    rows = [r for r in _read() if r["settle_date"]]
    d = [r for r in rows if r["dir_hit"]]
    b = [r for r in rows if r["band_hit"]]
    return {
        "settled": len(rows),
        "pending": len(_read()) - len(rows),
        "dir_n": len(d),
        "dir_pct": (sum(int(r["dir_hit"]) for r in d) / len(d) * 100) if d else None,
        "band_n": len(b),
        "band_pct": (sum(int(r["band_hit"]) for r in b) / len(b) * 100) if b else None,
    }


def main() -> None:
    n = settle()
    s = summary()
    print(f"settled {n} row(s) this run\n")
    print(f"{'live, out-of-sample':<24}{'n':>6}{'hit':>8}")
    dp = f"{s['dir_pct']:.1f}%" if s["dir_pct"] is not None else "--"
    bp = f"{s['band_pct']:.1f}%" if s["band_pct"] is not None else "--"
    print(f"{'1D direction':<24}{s['dir_n']:>6}{dp:>8}")
    print(f"{'1D band containment':<24}{s['band_n']:>6}{bp:>8}")
    print(f"\n{s['pending']} row(s) still waiting on the next bar.")
    if s["dir_n"] < 30:
        print("Too few settled rows to mean anything yet — do not re-fit on this.")


if __name__ == "__main__":
    main()
