#!/usr/bin/env python3
"""Build the data files for the private i004 Desk artifact.

    python tools/build_desk.py OUT_DIR [--ref origin/main]

Reads the engine's PUBLIC outputs at a git ref (docs/h, data/predictions.csv,
data/orders.csv, data/bars.csv, engine/config.json) and writes:

    OUT_DIR/market.json   per-ticker regime, levels and 1D/5D/1M rows
    OUT_DIR/track.json    advice-card track record and the paper book's equity curve

Nothing here touches Webull or any account data: the Desk reads the account live
through the viewer's own Webull connector.
"""
from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import sys
import tarfile
from collections import defaultdict

CAPITAL = 100_000.0


def git(ref: str, path: str) -> str:
    return subprocess.run(["git", "show", f"{ref}:{path}"], check=True, capture_output=True, text=True).stdout


def horizons(ref: str) -> list[dict]:
    raw = subprocess.run(["git", "archive", ref, "docs/h"], check=True, capture_output=True).stdout
    out = []
    with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
        for m in tar.getmembers():
            if not m.name.endswith(".json"):
                continue
            j = json.load(tar.extractfile(m))
            if "symbol" not in j:
                continue
            R = lambda v: None if v is None else round(v, 4)
            r52 = j.get("r52") or {}
            rows = [[r["label"], R(r["lo"]), R(r["hi"]), r.get("action"), round(r.get("hit") or 0, 1),
                     round(r.get("base") or 0, 1), round(r.get("band_pct") or 0, 1), int(r.get("n") or 0)]
                    for r in j.get("rows", [])]
            out.append({"s": j["symbol"], "p": R(j["price"]), "ch": R(j.get("change_pct")), "rg": j.get("regime"),
                        "s20": R(j.get("sma20")), "s50": R(j.get("sma50")), "s200": R(j.get("sma200")),
                        "inv": R(j.get("invalidation")), "re": R(j.get("reentry")), "atr": R(j.get("atr_pct")),
                        "lo52": R(r52.get("lo")), "hi52": R(r52.get("hi")), "d": j.get("last_bar"),
                        "ok": (j.get("suitability") or {}).get("ok"), "rx": R(j.get("rule_x")), "hx": R(j.get("hold_x")),
                        "bars": j.get("bars"), "rows": rows})
    return sorted(out, key=lambda x: x["s"])


def track(ref: str) -> dict:
    preds = list(csv.DictReader(io.StringIO(git(ref, "data/predictions.csv"))))
    settled = [p for p in preds if p["dir_hit"] in ("0", "1")]
    latest = max((p["issued_date"] for p in preds), default="")
    open_ = [p for p in preds if not p["settle_date"] and p["issued_date"] == latest]   # today's card

    def rate(rows, k):
        return round(sum(int(r[k]) for r in rows) / len(rows) * 100, 1) if rows else None

    by = defaultdict(list)
    for p in settled:
        by[p["ticker"]].append(p)
    per = [{"s": t, "n": len(v), "dir": rate(v, "dir_hit"), "band": rate(v, "band_hit")} for t, v in by.items()]
    per.sort(key=lambda x: (-x["n"], x["s"]))
    last20 = sorted({p["issued_date"] for p in settled})[-20:]
    recent_window = [p for p in settled if p["issued_date"] in last20]
    recent = [{"d": p["issued_date"], "s": p["ticker"], "rg": p["regime"], "a": p["action"],
               "base": float(p["base_close"]), "lo": float(p["range_lo"]), "hi": float(p["range_hi"]),
               "close": float(p["settle_close"]), "dir": int(p["dir_hit"]), "band": int(p["band_hit"])}
              for p in sorted(settled, key=lambda p: (p["issued_date"], p["ticker"]), reverse=True)[:40]]

    # Paper book: replay the order log, mark to each day's close.
    orders = [o for o in csv.DictReader(io.StringIO(git(ref, "data/orders.csv"))) if o["status"] == "FILLED"]
    closes = defaultdict(dict)
    dates = set()
    for b in csv.DictReader(io.StringIO(git(ref, "data/bars.csv"))):
        closes[b["ticker"]][b["date"]] = float(b["close"])
        if b["date"] >= "2026-08-27":
            dates.add(b["date"])
    dates = sorted(dates)
    cash, pos, curve = CAPITAL, defaultdict(int), []
    last_px = {}
    fills = sorted(orders, key=lambda o: o["fill_date"])
    i = 0
    for d in dates:
        while i < len(fills) and fills[i]["fill_date"] <= d:
            o = fills[i]; q, px = int(o["qty"]), float(o["fill_price"])
            cash += -q * px if o["side"] == "BUY" else q * px
            pos[o["ticker"]] += q if o["side"] == "BUY" else -q
            i += 1
        mv = 0.0
        for t, q in pos.items():
            if q:
                last_px[t] = closes[t].get(d, last_px.get(t))
                mv += q * (last_px[t] or 0)
        curve.append([d, round(cash + mv, 2)])
    held = {t: q for t, q in pos.items() if q}
    trades = [{"d": o["fill_date"], "s": o["ticker"], "side": o["side"], "q": int(o["qty"]), "p": float(o["fill_price"])}
              for o in sorted(orders, key=lambda o: o["fill_date"], reverse=True)[:25]]
    peak, mdd = 0.0, 0.0
    for _, v in curve:
        peak = max(peak, v); mdd = min(mdd, v / peak - 1)
    cfg = json.loads(git(ref, "engine/config.json"))
    return {
        "generated": dates[-1] if dates else None,
        "watchlist": cfg.get("watchlist", []),
        "preds": {"n": len(settled), "dir": rate(settled, "dir_hit"), "band": rate(settled, "band_hit"),
                  "first": min((p["issued_date"] for p in settled), default=None),
                  "open": [{"d": p["issued_date"], "s": p["ticker"], "rg": p["regime"], "a": p["action"],
                            "lo": float(p["range_lo"]), "hi": float(p["range_hi"]), "base": float(p["price"])} for p in open_],
                  "per": per, "recent": recent},
        "sim": {"start": CAPITAL, "curve": curve, "held": held, "trades": trades,
                "equity": curve[-1][1] if curve else CAPITAL, "maxdd": round(mdd * 100, 2)},
    }


def main() -> None:
    out = sys.argv[1]
    ref = sys.argv[sys.argv.index("--ref") + 1] if "--ref" in sys.argv else "origin/main"
    os.makedirs(out, exist_ok=True)
    m = horizons(ref)
    json.dump(m, open(os.path.join(out, "market.json"), "w"), separators=(",", ":"))
    t = track(ref)
    json.dump(t, open(os.path.join(out, "track.json"), "w"), separators=(",", ":"))
    print(f"market.json {len(m)} tickers · track.json {t['preds']['n']} settled calls, sim {t['sim']['equity']:,.2f} on {t['generated']}")


if __name__ == "__main__":
    main()
