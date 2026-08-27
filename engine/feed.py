#!/usr/bin/env python3
"""Webull data access for i004. JSON in, plain dicts out — no formatting.

Uses the SDK client that ships inside webull-openapi-mcp, so the 2FA token in
webull/conf/token.txt is honoured and there is only ever one auth path.

Env comes from webull/.env (WEBULL_APP_KEY / _SECRET / _REGION_ID / _ENVIRONMENT).
Run anything in this package through run.sh, which loads it.
"""
from __future__ import annotations

import logging
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Token location. WEBULL_TOKEN_DIR wins (that is how CI supplies it — the token is
# a portable opaque string, proven 2026-08-27). Otherwise fall back to the local
# checkout's webull/conf, searching upward so this works from any working dir.
def _token_dir() -> str | None:
    if os.environ.get("WEBULL_TOKEN_DIR"):
        return os.environ["WEBULL_TOKEN_DIR"]
    d = HERE
    for _ in range(4):
        d = os.path.dirname(d)
        cand = os.path.join(d, "webull", "conf")
        if os.path.isdir(cand):
            return cand
    return None

# The SDK logs a scary-looking token-file warning on every client build. It is
# not an error and it is not actionable; keep it out of the card's output.
logging.getLogger("webull.core.http.initializer.token.token_storage").setLevel(logging.ERROR)

_client = None


def client():
    """Authenticated SDK client. Built once per process."""
    global _client
    if _client is None:
        td = _token_dir()
        if td:
            os.environ["WEBULL_TOKEN_DIR"] = td
        from webull_openapi_mcp.config import load_config
        from webull_openapi_mcp.sdk_client import WebullSDKClient
        c = WebullSDKClient(load_config())
        c.initialize()
        _client = c
    return _client


def bars(symbol: str, count: int = 60, timespan: str = "D") -> list[dict]:
    """Daily OHLCV, newest first. [] when the symbol returns nothing."""
    try:
        r = client().data.market_data.get_history_bar(
            symbol=symbol, category="US_STOCK", timespan=timespan, count=count)
        data = r.json() if hasattr(r, "json") else r
    except Exception as e:
        print(f"  ! {symbol} bars failed: {type(e).__name__}: {e}", file=sys.stderr)
        return []
    if not isinstance(data, list):
        return []
    out = []
    for b in data:
        try:
            out.append({
                "date": b["time"][:10],
                "open": float(b["open"]),
                "high": float(b["high"]),
                "low": float(b["low"]),
                "close": float(b["close"]),
                "volume": float(b["volume"]),
            })
        except (KeyError, TypeError, ValueError):
            continue          # a malformed bar is dropped, never guessed at
    return out


def snapshot(symbols: list[str]) -> dict[str, dict]:
    """Latest price per symbol. Missing symbols are simply absent from the dict."""
    try:
        r = client().data.market_data.get_snapshot(
            symbols=",".join(symbols), category="US_STOCK")
        data = r.json() if hasattr(r, "json") else r
    except Exception as e:
        print(f"  ! snapshot failed: {type(e).__name__}: {e}", file=sys.stderr)
        return {}
    out = {}
    for s in data if isinstance(data, list) else []:
        try:
            out[s["symbol"]] = {
                "price": float(s["price"]),
                "pre_close": float(s["preClose"]),
                "change_pct": float(s.get("changeRatio", 0)) * 100,
                "volume": float(s.get("volume", 0)),
            }
        except (KeyError, TypeError, ValueError):
            continue
    return out


# --- account (read-only; never leaves this machine — plan R12) -----------------

_account_id = None


def account_id() -> str | None:
    global _account_id
    if _account_id is None:
        try:
            r = client().trade.account_v2.get_account_list()
            data = r.json() if hasattr(r, "json") else r
            _account_id = data[0]["account_id"] if data else None
        except Exception as e:
            print(f"  ! account list failed: {type(e).__name__}: {e}", file=sys.stderr)
    return _account_id


def equity_usd() -> dict:
    """USD market value, cash and buying power. {} if unavailable."""
    aid = account_id()
    if not aid:
        return {}
    try:
        r = client().trade.account_v2.get_account_balance(aid)
        data = r.json() if hasattr(r, "json") else r
        for a in data.get("account_currency_assets", []):
            if a.get("currency") == "USD":
                mv, cash = float(a["market_value"]), float(a["cash_balance"])
                return {"market_value": mv, "cash": cash, "equity": mv + cash,
                        "buying_power": float(a["buying_power"])}
    except Exception as e:
        print(f"  ! balance failed: {type(e).__name__}: {e}", file=sys.stderr)
    return {}


def positions() -> dict[str, dict]:
    """Held quantity and average cost per symbol. {} if unavailable."""
    aid = account_id()
    if not aid:
        return {}
    try:
        r = client().trade.account_v2.get_account_position(aid)
        data = r.json() if hasattr(r, "json") else r
    except Exception as e:
        print(f"  ! positions failed: {type(e).__name__}: {e}", file=sys.stderr)
        return {}
    out = {}
    for x in data if isinstance(data, list) else []:
        try:
            out[x["symbol"]] = {
                "qty": float(x["quantity"]),
                "cost": float(x["cost_price"]),
                "last": float(x["last_price"]),
                "upl": float(x["unrealized_profit_loss"]),
            }
        except (KeyError, TypeError, ValueError):
            continue
    return out
