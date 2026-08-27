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


# --- the same card as a page, for the Ledger Market tab ----------------------
# Its own file (docs/intraday.html), like docs/sim.html, so card.yml's
# account-data gate on docs/index.html is untouched.
def page(r: dict, news: str = "", now: str = "") -> str:
    BG, FGC, DIMC = "#0F1712", "#F2F0E9", "#8fa3b6"
    GRNC, REDC, GLDC = "#4ADE80", "#FF6B6B", "#E8B84B"

    def sp(t, c, b=False):
        return '<span style="color:%s%s;">%s</span>' % (c, ";font-weight:600" if b else "", t)

    px = r["price"]
    prior = r.get("prior_close")
    chg = (px / prior - 1) * 100 if prior else None
    ccol = GRNC if (chg or 0) >= 0 else REDC

    head = (sp(r["symbol"], FGC, True) + "&nbsp;&nbsp;" + sp("%.2f" % px, ccol, True)
            + ("&nbsp;&nbsp;" + sp("%+.2f%%" % chg, ccol) if chg is not None else "")
            + "&nbsp;&nbsp;" + sp(now, DIMC))

    if r["side"] == "NO SETUP":
        body = sp("WAIT", GLDC, True) + sp(" &mdash; no setup", DIMC) + "<br><br>"
        if r.get("orb_high") and r.get("vwap"):
            body += (sp("trigger&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;", DIMC) + sp("%.2f" % r["orb_high"], GRNC, True)
                     + sp("&nbsp; break above &rarr; LONG", DIMC) + "<br>"
                     + sp("invalidation&nbsp;", DIMC) + sp("%.2f" % r["vwap"], REDC, True)
                     + sp("&nbsp; VWAP &mdash; long is off", DIMC) + "<br>"
                     + sp("target&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&mdash;&nbsp; set when it triggers", DIMC))
        else:
            body += sp(r.get("why", ""), DIMC)
    else:
        sc = GRNC if r["side"] == "LONG" else REDC
        body = (sp(r["side"], sc, True) + "<br><br>"
                + sp("entry&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;", DIMC) + sp("%.2f" % r["entry"], FGC, True) + "<br>"
                + sp("stop&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;", DIMC) + sp("%.2f" % r["stop"], REDC, True)
                + sp("&nbsp; %.2f/sh &middot; %s%%" % (r["risk_per_share"], r["risk_pct_of_price"]), DIMC) + "<br>"
                + sp("target&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;", DIMC) + sp("%.2f" % r["target"], GRNC, True)
                + sp("&nbsp; %sR" % r["r_multiple"], DIMC) + "<br>"
                + sp("size&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;", DIMC) + sp("%s sh" % format(r["qty"], ","), FGC)
                + sp("&nbsp; risk $%s &middot; notional $%s"
                     % (format(r["risk_dollars"], ",.0f"), format(r["notional"], ",.0f")), DIMC))

    tape = ("VWAP %.2f &middot; opening 30m %.2f&ndash;%.2f &middot; session %.2f&ndash;%.2f "
            "&middot; %.1fM shares &middot; ATR %.2f"
            % (r["vwap"], r["orb_low"], r["orb_high"], r["session_low"],
               r["session_high"], r["volume"] / 1e6, r["atr"]))

    extra = (sp("catalyst&nbsp;&nbsp;", DIMC) + sp(news, FGC) + "<br>") if news else ""

    return ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="refresh" content="60">'
            '<title>i004 &middot; intraday</title><link rel="icon" href="data:,"></head>'
            '<body style="margin:0;padding:16px;background:#080d0a;">'
            '<div style="background:%s;color:%s;padding:18px 20px;border-radius:10px;'
            'font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:14px;'
            'line-height:1.7;max-width:640px;">%s<br><br>%s<br><br>%s%s<br><br>%s</div>'
            '</body></html>'
            % (BG, FGC, head, body, extra,
               sp("tape&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;", DIMC) + sp(tape, DIMC),
               sp("Not an order. Trigger and invalidation only &mdash; you place it.", GLDC)))


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
    if "--html" in argv:
        dest = argv[argv.index("--html") + 1]
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w") as f:
            f.write(page(r, news, now))
        print(f"page -> {dest}")
    else:
        print(card(r, news, now))


if __name__ == "__main__":
    main()
