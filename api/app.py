#!/usr/bin/env python3
"""i004 market API — the one live endpoint behind the Ledger's Intraday tab.

WHY THIS EXISTS. The published pages are static GitHub Pages. Quote providers
send no `Access-Control-Allow-Origin`, so a page cannot fetch live bars in the
browser (measured 2026-09-08: Yahoo answers 200 to curl and is unreachable from
a Pages origin). And the analysis is Python. So one hop, running the ENGINE
MODULES UNCHANGED -- no second implementation of the rule to drift out of sync.

    GET /intraday?sym=NVDA&tf=M5   -> engine/intraday.py   (ORB setup, live)
    GET /horizons?sym=NVDA         -> engine/horizons.py   (1D/5D/1M card)
    GET /healthz                   -> liveness, and which source answered

ACCOUNT DATA CANNOT LEAVE THIS PROCESS. horizons is called with account=False,
nothing here ever calls feed.positions(), and the deploy sets
WEBULL_TOOLSETS=market-data,instrument -- the `account` scope is deliberately
not granted to the host.
"""
from __future__ import annotations

import os
import sys
import traceback

from flask import Flask, jsonify, request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "engine"))

import feed_yahoo                                                  # noqa: E402
import horizons                                                    # noqa: E402
import intraday                                                    # noqa: E402

app = Flask(__name__)

# The Pages origin is the only caller. Listed explicitly rather than "*", so a
# copy of this URL pasted into someone else's page does not silently work.
ALLOWED = {"https://cyyaddsg-git.github.io", "http://localhost:8020",
           "http://127.0.0.1:8020", "null"}


@app.after_request
def cors(resp):
    origin = request.headers.get("Origin", "")
    if origin in ALLOWED:
        resp.headers["Access-Control-Allow-Origin"] = origin
    resp.headers["Cache-Control"] = "no-store"
    return resp


def _sym() -> str:
    s = (request.args.get("sym") or "").strip().upper()
    if not (1 <= len(s) <= 6 and s.isalpha()):
        raise ValueError("sym must be 1-6 letters")
    return s


@app.get("/healthz")
def healthz():
    return jsonify(ok=True, webull=bool(os.environ.get("WEBULL_APP_KEY")))


@app.get("/intraday")
def r_intraday():
    """Webull first (completed bars, deepest history), Yahoo when it cannot serve.
    `source` is returned on every response -- a card that will not say where its
    price came from is how the daily card spent a week pricing off a stale close.
    """
    try:
        sym, tf = _sym(), (request.args.get("tf") or "M5").upper()
    except ValueError as e:
        return jsonify(error=str(e)), 400
    errs = []
    for name, get in (("webull", lambda: intraday.bars(sym, tf, 200)),
                      ("yahoo", lambda: feed_yahoo.intraday_bars(sym, tf))):
        try:
            bs = get()
            if not bs:
                errs.append(f"{name}: 0 bars")
                continue
            out = intraday.read(sym, tf, bs=bs)
            out["source"] = name
            return jsonify(out)
        except (Exception, SystemExit) as e:                       # noqa: BLE001
            errs.append(f"{name}: {type(e).__name__}: {e}"[:200])
    return jsonify(error=f"{sym}: no source could serve {tf} bars",
                   detail=errs), 502


def _live_price(sym: str) -> tuple[float | None, str]:
    """The live price, from the intraday BAR feed.

    horizons.live_price() asks Webull for a snapshot, and that endpoint returns []
    for every symbol on this key (measured 2026-09-04); its Yahoo fallback is
    rate-limited from most hosts. get_history_bar works on the same key, and the
    latest intraday bar's close IS the live price -- so take it from there rather
    than let the card quote a stale close and call it live.
    """
    for name, get in (("webull", lambda: intraday.bars(sym, "M5", 2)),
                      ("yahoo", lambda: feed_yahoo.intraday_bars(sym, "M5"))):
        try:
            bs = get()
            if bs:
                return bs[-1]["c"], name
        except (Exception, SystemExit):                            # noqa: BLE001
            continue
    return None, "close"


@app.get("/horizons")
def r_horizons():
    try:
        sym = _sym()
    except ValueError as e:
        return jsonify(error=str(e)), 400
    errs = []
    for name, get in (("webull", lambda: None),                    # feed default
                      ("yahoo", lambda: feed_yahoo.daily_bars(sym))):
        try:
            out = horizons.evaluate(sym, bars=get(), account=False, live=False)
            out["source"] = name
            px, psrc = _live_price(sym)
            if px:
                out["price"], out["src"] = px, psrc
                base = out.get("prev_close")
                if base:
                    out["change_pct"] = (px / base - 1) * 100
            return jsonify(out)
        except (Exception, SystemExit) as e:                       # noqa: BLE001
            errs.append(f"{name}: {type(e).__name__}: {e}"[:200])
    return jsonify(error=f"{sym}: no source could serve daily bars",
                   detail=errs), 502


@app.errorhandler(500)
def boom(e):
    return jsonify(error="internal", detail=traceback.format_exc()[-400:]), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8021)), debug=False)
