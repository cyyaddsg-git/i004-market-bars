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


def main() -> None:
    cfg = load("config.json")
    symbols = sys.argv[1:] or list(dict.fromkeys(cfg["watchlist"]))
    rows, acct, _ = build(symbols, cfg)
    print(render.as_text(rows, load("accuracy.json"), acct))


if __name__ == "__main__":
    main()
