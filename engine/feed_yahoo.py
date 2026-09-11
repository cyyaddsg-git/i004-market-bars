#!/usr/bin/env python3
"""Yahoo bars — daily and intraday — with no API key of any kind.

This exists so the hosted API (api/app.py, Render) can run the SAME analysis
modules as the terminal without carrying Webull credentials off YY's machine.
A public host holding a broker key is a risk that buys nothing here: the engine
only ever reads prices.

Webull remains the terminal's source. The two disagree in one known way, handled
below: Yahoo returns an IN-PROGRESS bar for the current session, Webull does not.
"""
from __future__ import annotations

import datetime
import json
import urllib.request
import zoneinfo

ET = zoneinfo.ZoneInfo("America/New_York")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

# Yahoo's interval strings, keyed by the engine's own timespan vocabulary so
# callers never learn a second set of names.
INTERVAL = {"M1": "1m", "M5": "5m", "M15": "15m", "M30": "30m", "M60": "60m"}
# How far back each interval is worth asking for. Yahoo caps 1m at 7 days.
RANGE = {"M1": "5d", "M5": "1mo", "M15": "1mo", "M30": "3mo", "M60": "3mo"}


# Yahoo 429s an anonymous request hard -- measured 2026-09-11 from BOTH YY's home
# address and Render's Singapore egress, so it is not one bad IP. What it actually
# wants is a session: consent cookies from fc.yahoo.com, then a crumb. Build that
# once per process and reuse it, with a short backoff for the genuine bursts.
_OPENER = None


def _opener():
    global _OPENER
    if _OPENER is None:
        import http.cookiejar
        cj = http.cookiejar.CookieJar()
        _OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        _OPENER.addheaders = list(UA.items())
        for u in ("https://fc.yahoo.com/", "https://finance.yahoo.com/"):
            try:
                _OPENER.open(u, timeout=10).read(1)
            except Exception:                                      # noqa: BLE001
                pass                    # a refused warm-up is not fatal; the cookie
                                        # may already have come from the other URL
    return _OPENER


def _get(u: str, timeout: int, tries: int = 4):
    """One GET with backoff. 429 is the expected failure here, not an anomaly."""
    import time
    last = None
    for i in range(tries):
        try:
            return _opener().open(u, timeout=timeout).read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in (429, 503):
                raise
            global _OPENER
            _OPENER = None              # rebuild the session; the cookie may be stale
            time.sleep(1.5 * (i + 1))
    raise last


def _chart(sym: str, interval: str, rng: str, timeout: int = 30) -> dict:
    u = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
         f"?interval={interval}&range={rng}&includePrePost=false")
    d = json.loads(_get(u, timeout))
    res = (d.get("chart") or {}).get("result")
    if not res:
        err = ((d.get("chart") or {}).get("error") or {}).get("description")
        raise RuntimeError(err or f"{sym}: empty chart result")
    return res[0]


def _rows(r: dict):
    q = (r.get("indicators") or {}).get("quote", [{}])[0]
    for i, t in enumerate(r.get("timestamp") or []):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue                      # a feed gap is dropped, never filled in
        yield t, o, h, l, c, (q["volume"][i] or 0)


def daily_bars(sym: str, count: int = 800) -> list[dict]:
    """Oldest-first daily bars shaped for horizons.evaluate(bars=...)."""
    r = _chart(sym, "1d", "5y")
    rows = [{"date": str(datetime.datetime.fromtimestamp(t, ET).date()),
             "open": o, "high": h, "low": l, "close": c, "volume": v}
            for t, o, h, l, c, v in _rows(r)]
    # Drop today's bar while the session is still running. Yahoo's current-day
    # "close" is just the live price; fed to a daily-close rule it anchors the
    # band on half a day and shifts every moving average.
    now = datetime.datetime.now(ET)
    if rows and rows[-1]["date"] == str(now.date()) and not (
            now.weekday() < 5 and now.time() >= datetime.time(16, 15)):
        rows.pop()
    if not rows:
        raise RuntimeError(f"{sym}: EXTRACTION FAILED — 0 daily bars")
    return rows[-count:]


def intraday_bars(sym: str, timespan: str = "M5") -> list[dict]:
    """Oldest-first intraday bars shaped for intraday.read(bars=...).

    `t` is a full ISO timestamp in UTC, because intraday.read() slices it for the
    session date and the opening range. The CURRENT bar is kept -- unlike the daily
    case, a partly-formed bar IS the live price and that is the whole point here.
    """
    if timespan not in INTERVAL:
        raise RuntimeError(f"{timespan}: not one of {', '.join(INTERVAL)}")
    r = _chart(sym, INTERVAL[timespan], RANGE[timespan])
    out = [{"t": datetime.datetime.fromtimestamp(t, datetime.timezone.utc)
                     .strftime("%Y-%m-%dT%H:%M:%S.000+0000"),
            "o": o, "h": h, "l": l, "c": c, "v": v}
           for t, o, h, l, c, v in _rows(r)]
    if not out:
        raise RuntimeError(f"{sym}: EXTRACTION FAILED — 0 {timespan} bars")
    return out
