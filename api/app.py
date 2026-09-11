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

# The host runs WITHOUT the Webull SDK and without any key -- see render.yaml. The
# per-source loops below already treat a raising source as "cannot serve", but a
# source that can never work should not be tried at all: it would put a misleading
# "webull: ModuleNotFoundError" at the head of every error detail.
HAS_WEBULL = bool(os.environ.get("WEBULL_APP_KEY"))

# The SDK reads the 2FA token from a FILE, and a host has no checkout to read it
# from. Materialise it from the env var into a private temp dir at startup, the
# same shape CI uses (it writes $RUNNER_TEMP/wb/token.txt). Optional: if market
# data works on key+secret alone, WEBULL_TOKEN simply stays unset.
TOKEN_LINES = 0

# A Render Secret File is the sturdier path: token.txt is three positional lines and
# a dashboard textarea mangles or silently drops a multi-line paste (measured
# 2026-09-12 -- the variable did not save at all). A file arrives byte-exact.
if HAS_WEBULL and not os.environ.get("WEBULL_TOKEN"):
    for _p in ("/etc/secrets/token.txt", os.path.join(os.getcwd(), "token.txt")):
        try:
            with open(_p) as _f:
                _v = _f.read().strip()
            if _v:
                os.environ["WEBULL_TOKEN"] = _v
                break
        except OSError:
            continue

if HAS_WEBULL and os.environ.get("WEBULL_TOKEN") and not os.environ.get("WEBULL_TOKEN_DIR"):
    import tempfile
    # token.txt is THREE lines -- token, expiry, status -- and the SDK parses it
    # positionally. A dashboard textarea can hand back \r\n, a single flattened
    # line, or stray blanks; any of those make the SDK read the token as PENDING
    # and demand 2FA, which is indistinguishable from a bad credential. So
    # normalise on whatever separator survived rather than trust the paste.
    _raw = os.environ["WEBULL_TOKEN"].replace("\r\n", "\n").replace("\r", "\n")
    _parts = [x for x in _raw.replace(",", "\n").split() if x]
    TOKEN_LINES = len(_parts)
    _td = os.path.join(tempfile.gettempdir(), "wb")
    os.makedirs(_td, mode=0o700, exist_ok=True)
    with open(os.path.join(_td, "token.txt"), "w") as _f:
        _f.write("\n".join(_parts) + "\n")
    os.environ["WEBULL_TOKEN_DIR"] = _td

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
    return jsonify(ok=True, sources=["webull", "yahoo"] if HAS_WEBULL else ["yahoo"],
                   token_fields=TOKEN_LINES)   # count only, never the value


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
    sources = ([("webull", lambda: intraday.bars(sym, tf, 200))] if HAS_WEBULL else []) \
        + [("yahoo", lambda: feed_yahoo.intraday_bars(sym, tf))]
    for name, get in sources:
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
    sources = ([("webull", lambda: intraday.bars(sym, "M5", 2))] if HAS_WEBULL else []) \
        + [("yahoo", lambda: feed_yahoo.intraday_bars(sym, "M5"))]
    for name, get in sources:
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
    sources = ([("webull", lambda: None)] if HAS_WEBULL else []) \
        + [("yahoo", lambda: feed_yahoo.daily_bars(sym))]
    for name, get in sources:
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


@app.get("/card")
def r_card():
    """The whole watchlist, advice only -- what the Card tab needs to recompute on
    Reload instead of showing this morning's snapshot until tomorrow.

    NOT card.build(): that calls feed.positions() and feed.equity_usd(). This runs
    the same analyse() with held=None and no account lookup at all, so the response
    cannot carry a holding, a balance or a P&L even by accident.
    """
    import json as _json
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "engine"))
    from indicators import analyse                                 # noqa: PLC0415
    import feed                                                    # noqa: PLC0415
    cfg = _json.load(open(os.path.join(os.path.dirname(HERE), "engine", "config.json")))
    syms = cfg["watchlist"]
    rows, errs = [], []
    for sym in syms:
        try:
            bars = feed.bars(sym, count=90)
            if not bars:
                errs.append(f"{sym}: no bars")
                continue
            px, _ = _live_price(sym)
            r = analyse(sym, bars, cfg, live_price=px, held=None)
            # analyse() still emits held_qty (0 here). Strip every position-shaped
            # key by name rather than trust that it stays 0 -- R12 says a public
            # response must not be ABLE to carry account data, not merely not today.
            for _k in ("held", "held_qty", "upl", "qty", "cost", "equity", "deposited"):
                r.pop(_k, None)
            rows.append(r)
        except (Exception, SystemExit) as e:                       # noqa: BLE001
            errs.append(f"{sym}: {type(e).__name__}"[:80])
    if not rows:
        return jsonify(error="no symbol could be evaluated", detail=errs), 502
    return jsonify(rows=rows, errors=errs, source="webull" if HAS_WEBULL else "yahoo")


@app.errorhandler(500)
def boom(e):
    return jsonify(error="internal", detail=traceback.format_exc()[-400:]), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8021)), debug=False)
