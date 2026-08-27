#!/usr/bin/env python3
"""The intraday card, for this terminal.

    python engine/intraday_card.py NVDA [M5] [--news "one line"]
    python engine/intraday_card.py --from-json read.json [--news "..."]

Format, decided with YY 2026-08-27. An intraday call is not "buy at X" -- it is
a TRIGGER and an INVALIDATION, and until price reaches one of them the answer is
WAIT. So the card leads with the state, then gives the three numbers that are
actually actionable, and nothing else.

--from-json renders a saved read without touching the API, which is how this was
built and tested outside market hours.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

R = "\033[0m"; B = "\033[1m"; D = "\033[2m"
GRN = "\033[38;5;77m"; RED = "\033[38;5;203m"; GLD = "\033[38;5;179m"
BLU = "\033[38;5;75m"; FG = "\033[38;5;253m"
W = 62


def rule(ch="─"):
    return D + ch * W + R


def wrap(text: str, indent: int, width: int = W) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width - indent:
            lines.append(cur); cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def card(r: dict, news: str = "", now: str = "") -> str:
    px = r["price"]
    prior = r.get("prior_close")
    chg = (px / prior - 1) * 100 if prior else None
    ccol = GRN if (chg or 0) >= 0 else RED

    head = f"{B}{FG}{r['symbol']}{R}   {B}{ccol}{px:,.2f}{R}"
    if chg is not None:
        head += f"  {ccol}{chg:+.2f}%{R}"
    pad = W - len(f"{r['symbol']}   {px:,.2f}  {chg:+.2f}%" if chg is not None
                  else f"{r['symbol']}   {px:,.2f}")
    head += " " * max(1, pad - len(now)) + D + now + R

    L = [rule(), " " + head, rule()]

    if r["side"] == "NO SETUP":
        L.append(f" {B}{GLD}WAIT{R} {D}— no setup{R}")
        L.append("")
        trig = r.get("orb_high")
        inval = r.get("vwap")
        if trig and inval:
            L.append(f"   {D}trigger     {R} {B}{GRN}{trig:,.2f}{R}  {D}break above → LONG{R}")
            L.append(f"   {D}invalidation{R} {B}{RED}{inval:,.2f}{R}  {D}VWAP — long is off{R}")
            L.append(f"   {D}target      {R} {D}     —  set when it triggers{R}")
        else:
            for ln in wrap(r.get("why", ""), 3):
                L.append("   " + D + ln + R)
    else:
        side_col = GRN if r["side"] == "LONG" else RED
        L.append(f" {B}{side_col}{r['side']}{R}")
        L.append("")
        L.append(f"   {D}entry       {R} {B}{FG}{r['entry']:,.2f}{R}")
        L.append(f"   {D}stop        {R} {B}{RED}{r['stop']:,.2f}{R}  "
                 f"{D}{r['risk_per_share']:,.2f}/sh · {r['risk_pct_of_price']}%{R}")
        L.append(f"   {D}target      {R} {B}{GRN}{r['target']:,.2f}{R}  {D}{r['r_multiple']}R{R}")
        L.append(f"   {D}size        {R} {FG}{r['qty']:,} sh{R}  "
                 f"{D}risk ${r['risk_dollars']:,.0f} · notional ${r['notional']:,.0f}{R}")

    L.append("")
    if news:
        for i, ln in enumerate(wrap(news, 12)):
            L.append(f" {D}{'catalyst' if i == 0 else '        '}{R}   {FG}{ln}{R}")
    tape = (f"VWAP {r['vwap']:,.2f} · opening 30m {r['orb_low']:,.2f}–{r['orb_high']:,.2f} · "
            f"session {r['session_low']:,.2f}–{r['session_high']:,.2f} · "
            f"{r['volume']/1e6:,.1f}M shares · ATR {r['atr']:,.2f}")
    for i, ln in enumerate(wrap(tape, 12)):
        L.append(f" {D}{'tape' if i == 0 else '    '}{R}       {D}{ln}{R}")

    L.append(rule())
    L.append(f" {D}Not an order. Trigger and invalidation only — you place it.{R}")
    L.append("")
    return "\n".join(L)


def main() -> None:
    news = ""
    argv = sys.argv[1:]
    if "--news" in argv:
        i = argv.index("--news")
        news = argv[i + 1] if i + 1 < len(argv) else ""
        argv = argv[:i] + argv[i + 2:]

    if "--from-json" in argv:
        i = argv.index("--from-json")
        r = json.load(open(argv[i + 1]))
    else:
        import intraday
        sym = (argv[0] if argv else "NVDA").upper()
        span = argv[1] if len(argv) > 1 else "M5"
        r = intraday.read(sym, span)

    import datetime, zoneinfo
    now = datetime.datetime.now(zoneinfo.ZoneInfo("Asia/Singapore")).strftime("%H:%M SGT")
    print(card(r, news, now))


if __name__ == "__main__":
    main()
