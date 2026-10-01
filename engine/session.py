#!/usr/bin/env python3
"""In-session card: the daily call plus TODAY's entry line, once the opening range has formed.

    python engine/session.py                     terminal, universe + paper book
    python engine/session.py --private           terminal, + YY's real holdings
    python engine/session.py --html docs/session.html     public page (advice only)

Why it exists (YY, 2026-10-01): the 09:00 SGT card is built from last night's close.
It says MU is a BUY with an exit below 1,000 -- true, and useless at 21:35 SGT when MU
opens, flushes to 1,036 and the question is WHERE to get in today. This run happens
after the first 30 minutes and adds that line.

It decides nothing new. The daily regime comes from indicators.analyse() and the
intraday trigger from intraday.read() -- both unchanged. This only states the two side
by side and says which one governs today. It logs no prediction and lodges no paper
order: the measured record stays the 09:00 SGT card alone.
"""
from __future__ import annotations

import datetime
import html
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import card                                    # noqa: E402
import feed                                    # noqa: E402
import intraday                                # noqa: E402
from render import BG, FG, DIM, UP, DOWN, FLAT, ACC, ET, SGT   # noqa: E402


def px(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:,.2f}" if abs(v) >= 10 else f"{v:.4f}".rstrip("0").rstrip(".")


def entry_line(d: dict, i: dict | None) -> tuple[str, str, str]:
    """(verdict, colour, sentence) for today. Never names a position: public-safe."""
    regime = d.get("regime")
    if d.get("action") == "NO_DATA":
        return "NO DATA", DIM, d.get("why", "")
    if i is None:
        return "WAIT", FLAT, "intraday bars unavailable — use the daily levels only"
    if i.get("refused"):
        lvl = (f"swing exit below {px(d['invalidation'])}" if regime == "IN" else
               f"trend turns above {px(d['reentry'])}" if regime == "OUT" else "no daily trend")
        return "DAILY ONLY", DIM, f"{i['why'].replace('REFUSED — ', '')} Daily: {lvl}"
    side = i.get("side")
    orh, orl, vw = i.get("orb_high"), i.get("orb_low"), i.get("vwap")
    if side == "NO SETUP" and i.get("orb_bars", 0) < intraday.ORB_MIN // 5:
        return "WAIT", FLAT, "opening range still forming — " + i.get("why", "")
    if regime == "IN":
        if side == "LONG":
            return "BUY NOW", UP, (f"trend up and today above VWAP {px(vw)} and the opening "
                                   f"high {px(orh)}: entry {px(i['entry'])} · stop {px(i['stop'])}"
                                   f" · target {px(i['target'])}")
        if side == "SHORT":
            return "WAIT", FLAT, (f"trend up but today is selling — below VWAP {px(vw)} and the "
                                  f"opening low {px(orl)}. No entry unless it reclaims {px(vw)}; "
                                  f"swing exit stays below {px(d['invalidation'])}")
        return "WAIT", FLAT, (f"trend up; buy only on a move above {px(max(orh, vw))} "
                              f"(opening high / VWAP). Swing exit below {px(d['invalidation'])}")
    if regime == "OUT":
        if side == "SHORT":
            return "STAY OUT", DOWN, (f"trend down and today below VWAP {px(vw)} and the opening "
                                      f"low {px(orl)}. Any long is an exit on the next bounce")
        if side == "LONG":
            return "SELL INTO STRENGTH", DOWN, (f"bounce above VWAP {px(vw)} inside a down trend — "
                                                f"exit strength near {px(i.get('target'))}; the trend "
                                                f"only turns above {px(d['reentry'])}")
        return "STAY OUT", DOWN, f"trend down; it only turns on a close above {px(d['reentry'])}"
    return "WAIT", FLAT, (f"no daily trend. Intraday: above {px(orh)} long, below {px(orl)} "
                          f"short, between them nothing")


def build(symbols: list[str], cfg: dict) -> list[dict]:
    rows, _, held = card.build(symbols, cfg)
    out = []
    for d in rows:
        try:
            i = intraday.read(d["symbol"], "M5")
        except (SystemExit, Exception) as e:                 # one bad symbol, not the run
            print(f"  ! {d['symbol']} intraday failed: {e}", file=sys.stderr)
            i = None
        verdict, col, why = entry_line(d, i)
        out.append({"d": d, "i": i, "verdict": verdict, "col": col, "why": why,
                    "held": held.get(d["symbol"])})
    order = {"BUY NOW": 0, "SELL INTO STRENGTH": 1, "STAY OUT": 2, "WAIT": 3, "DAILY ONLY": 4}
    out.sort(key=lambda r: (order.get(r["verdict"], 5), r["d"]["symbol"]))
    return out


def stamp() -> str:
    now = datetime.datetime.now(SGT)
    return (f"NASDAQ · in-session · {now:%Y-%m-%d %H:%M} SGT · "
            f"{now.astimezone(ET):%H:%M} ET")


def as_text(rows: list[dict], private: bool) -> str:
    G, R, Y, D, B, X = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[1m", "\033[0m"
    tone = {UP: G, DOWN: R, FLAT: Y, DIM: D}
    L = [f"{D}{stamp()}{X}", ""]
    for r in rows:
        d = r["d"]
        chg = d.get("change_pct") or 0
        h = r["held"] if private else None
        pos = (f"   {D}holding {h['qty']:g} @ {px(h['cost'])}{X}" if h else "")
        L.append(f"{B}{d['symbol']:<6}{X}{G if chg >= 0 else R}{px(d.get('price')):>10} "
                 f"{chg:+.2f}%{X}   {D}daily {d.get('regime', '—')}{X}{pos}")
        L.append(f"      {tone.get(r['col'], '')}{B}{r['verdict']}{X} — {r['why']}")
        L.append("")
    return "\n".join(L)


def as_html(rows: list[dict]) -> str:
    """PUBLIC. No holdings, no account. The verdicts are position-free by construction."""
    e = html.escape
    sp = lambda t, c, b=False: (f'<span style="color:{c};{"font-weight:600;" if b else ""}">'
                                f'{t}</span>')
    blocks = []
    for r in rows:
        d = r["d"]
        chg = d.get("change_pct") or 0
        blocks.append(
            sp(e(d["symbol"]), FG, True) + "&nbsp;&nbsp;"
            + sp(f"{px(d.get('price'))}&nbsp; {chg:+.2f}%", UP if chg >= 0 else DOWN, True)
            + "&nbsp;&nbsp;" + sp(f"daily {e(str(d.get('regime', '—')))}", DIM)
            + "<br>&nbsp;&nbsp;" + sp(e(r["verdict"]), r["col"], True)
            + sp(" — " + e(r["why"]), FG))
    body = "<br><br>".join(blocks)
    foot = (sp("Daily trend from the 09:00 SGT card's rule; today's line from the 30-minute "
               "opening range and VWAP. Advice only — nothing here is a logged prediction.", DIM)
            + '<br><br><a href="index.html" style="color:%s;text-decoration:none;'
              'border-bottom:1px dotted %s;">&larr; daily card</a>' % (ACC, ACC))
    return ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>i004 · in-session</title><link rel="icon" href="data:,"></head>'
            '<body style="margin:0;padding:16px;background:#080d0a;">'
            f'<div style="background:{BG};color:{FG};padding:18px 20px;border-radius:10px;'
            'font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:14px;'
            f'line-height:1.65;max-width:640px;">{sp(stamp(), DIM)}<br><br>{body}<br><br>{foot}'
            '</div></body></html>')


def main() -> None:
    a = sys.argv[1:]
    private = "--private" in a
    out = a[a.index("--html") + 1] if "--html" in a else None
    if out and private:
        raise SystemExit("--private and --html together would publish holdings — refusing")
    cfg = card.load("config.json")
    syms = [s for s in a if not s.startswith("--") and s != out] or card.tradeable(cfg, real=private)
    rows = build(syms, cfg)
    if out:
        with open(out, "w") as f:
            f.write(as_html(rows))
        print(f"page -> {out}")
    print(as_text(rows, private))


if __name__ == "__main__":
    main()
