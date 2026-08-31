#!/usr/bin/env python3
"""Terminal card.  ./run.sh  [SYMBOLS...]

Rendering lives in render.py so terminal, email and page cannot drift apart.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import feed                                    # noqa: E402
import render                                  # noqa: E402
from indicators import analyse                 # noqa: E402


def load(name: str, default=None):
    try:
        return json.load(open(os.path.join(HERE, name)))
    except Exception:
        return default if default is not None else {}


def build(symbols: list[str], cfg: dict) -> tuple[list[dict], dict, dict]:
    """rows, account, held — the shared path for terminal, email and page."""
    snaps = feed.snapshot(symbols)
    held = feed.positions()
    rows = [analyse(s, feed.bars(s, count=90), cfg,
                    live_price=snaps.get(s, {}).get("price"), held=held.get(s))
            for s in symbols]
    acct = feed.equity_usd()
    if acct:
        dep = os.environ.get("ACCOUNT_DEPOSITED")
        if dep:
            acct["deposited"] = float(dep)
        acct["kill_pct"] = cfg.get("drawdown_kill_switch_pct", 20)
    return rows, acct, held


def tradeable(cfg) -> list[str]:
    """The universe, PLUS anything the paper book still holds.

    A name that leaves the universe must keep getting a card until the book is out of it.
    Dropping it the day the watchlist changes would strand the position: no card, so no
    regime, so no SELL, so no exit -- ever. Learned when the universe rule was introduced
    on 2026-08-31 and four held names (PLTU, BULL, ORBS, SPCX) were about to fall off it.
    """
    syms = list(dict.fromkeys(cfg["watchlist"]))
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import sim
        held = [t for t, p in sim.replay()["positions"].items() if p["qty"] > 0]
    except Exception:
        held = []
    return syms + [t for t in held if t not in syms]


def main() -> None:
    cfg = load("config.json")
    symbols = sys.argv[1:] or tradeable(cfg)
    rows, acct, _ = build(symbols, cfg)
    print(render.as_text(rows, load("accuracy.json"), acct))


if __name__ == "__main__":
    main()
