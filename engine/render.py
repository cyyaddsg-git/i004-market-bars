#!/usr/bin/env python3
"""One card, three surfaces: terminal, email, public page.

Rendered from a single list of rows so the three can never drift apart.

PRIVACY — the reason `private` exists (plan R12/R14):
    private=True   terminal + email     holdings, equity, P&L, kill-switch distance
    private=False  the public page      advice only — price, action, level, risk %,
                                        band, accuracy. Nothing about the account.
The public page is served from a public repo. Anything account-shaped that reaches
it is the `ledger` incident repeating.
"""
from __future__ import annotations

import datetime
import zoneinfo

ET = zoneinfo.ZoneInfo("America/New_York")
SGT = zoneinfo.ZoneInfo("Asia/Singapore")

ORDER = {"SELL": 0, "BUY": 1, "HOLD": 2, "STAND_ASIDE": 3, "NO_TRADE": 4, "NO_DATA": 5}
LABEL = {"BUY": "BUY", "HOLD": "HOLD", "SELL": "SELL",
         "STAND_ASIDE": "STAND ASIDE", "NO_TRADE": "NO TRADE", "NO_DATA": "NO DATA"}

# palette shared by page and email (inline styles only — mail clients strip <style>)
BG, FG, DIM, UP, DOWN, FLAT, ACC = ("#0F1712", "#F2F0E9", "#8fa3b6",
                                    "#4ADE80", "#FF6B6B", "#E8B84B", "#7dd3fc")


def money(v: float) -> str:
    return f"{v:,.2f}" if abs(v) >= 1 else f"{v:.4f}"


def session_label(now_et: datetime.datetime) -> str:
    t = now_et.time()
    if now_et.weekday() >= 5:
        return "weekend"
    if t < datetime.time(9, 30):
        return "pre-open"
    if t <= datetime.time(16, 0):
        return "open"
    return "post-close"


def sort_rows(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (ORDER.get(r["action"], 9), r["symbol"]))


def stamp() -> str:
    now_et = datetime.datetime.now(ET)
    return (f"NASDAQ · {datetime.datetime.now(SGT):%Y-%m-%d %H:%M} SGT · "
            f"{now_et:%H:%M} ET · {session_label(now_et)}")


def risk_pct(r: dict) -> float | None:
    if "risk_pct" in r:
        return r["risk_pct"]
    if "invalidation" in r and r.get("price"):
        return (r["price"] - r["invalidation"]) / r["price"] * 100
    return None


def acc_of(sym: str, acc: dict) -> dict | None:
    return (acc or {}).get("tickers", {}).get(sym)


# --------------------------------------------------------------------- terminal

def as_text(rows: list[dict], acc: dict, account: dict | None = None) -> str:
    G, R, Y, C, D, B, X = ("\033[32m", "\033[31m", "\033[33m",
                           "\033[36m", "\033[2m", "\033[1m", "\033[0m")
    out = [f"{D}{stamp()}{X}"]
    if account:
        out += [f"{D}{ln}{X}" for ln in account_lines(account)]
    out.append("")

    for r in sort_rows(rows):
        sym, act = f"{B}{r['symbol']:<6}{X}", r["action"]
        if act == "NO_DATA":
            out += [f"{sym}{D}—   NO DATA{X}", f"      {D}{r['why']} · no call made{X}", ""]
            continue
        col = G if r["change_pct"] >= 0 else R
        head = f"{sym}{col}{money(r['price'])}   {r['change_pct']:+.2f}%{X}"
        if r.get("held_qty"):
            u = r.get("upl", 0)
            head += (f"   {D}holding {r['held_qty']:,.0f} @ {money(r['cost'])} "
                     f"{G if u >= 0 else R}{u:+,.0f}{X}")
        out.append(head)

        rp = risk_pct(r)
        rtxt = f"{D} · risk {rp:.1f}%{X}" if rp is not None else ""
        if act == "BUY":
            out.append(f"      {C}{B}BUY{X} @ {money(r['price'])} · "
                       f"{R}out below {money(r['invalidation'])}{X}{rtxt}")
        elif act == "HOLD":
            out.append(f"      {B}HOLD{X} — {R}out below {money(r['invalidation'])}{X}{rtxt}")
        elif act == "SELL":
            thin = f"{Y} · thin book, work the exit{X}" if r.get("thin") else ""
            out.append(f"      {R}{B}SELL{X} — regime broke · "
                       f"{D}re-entry above {money(r['reentry'])}{X}{thin}")
        elif act == "STAND_ASIDE":
            out.append(f"      {B}STAND ASIDE{X} — {D}below the line · "
                       f"re-entry above {money(r['reentry'])}{X}")
        else:
            out.append(f"      {B}NO TRADE{X} — {D}{r.get('why', 'no level in reach')}{X}")

        if "range_lo" in r:
            out.append(f"      {D}today {money(r['range_lo'])} – {money(r['range_hi'])}{X}")
        a = acc_of(r["symbol"], acc)
        if a:
            def c(v):
                if v is None:
                    return f"{D}—{X}"
                return f"{G if v >= 55 else (Y if v >= 50 else R)}{v:.0f}%{X}"
            out.append(f"      {D}accuracy  1D {c(a['d1'])}{D}  1M {c(a['m1'])}{D}  "
                       f"1Y {c(a['y1'])}{D}  ·  band {c(a['band'])}{D}  ({a['bars']} bars){X}")
        out.append("")
    return "\n".join(out)


def account_lines(a: dict) -> list[str]:
    """Private only. Never called for the public page."""
    lines = [f"equity ${a['equity']:,.0f} · cash ${a['cash']:,.0f} · "
             f"buying power ${a['buying_power']:,.0f}"]
    dep = a.get("deposited")
    if dep:
        pnl = a["equity"] - dep
        kill = dep * (1 - a.get("kill_pct", 20) / 100)
        lines.append(f"vs ${dep:,.0f} deposited: {pnl:+,.0f} ({pnl/dep*100:+.1f}%) · "
                     f"kill switch ${kill:,.0f}, {(a['equity']-kill)/dep*100:.1f}% away")
    return lines


# ------------------------------------------------------------------ html / mail

def as_html(rows: list[dict], acc: dict, account: dict | None = None,
            private: bool = False) -> str:
    def sp(txt, col=None, bold=False):
        st = "".join([f"color:{col};" if col else "", "font-weight:600;" if bold else ""])
        return f'<span style="{st}">{txt}</span>' if st else str(txt)

    blocks = []
    for r in sort_rows(rows):
        sym = sp(r["symbol"], FG, True)
        if r["action"] == "NO_DATA":
            blocks.append(f"{sym}&nbsp;&nbsp;{sp('—  NO DATA', DIM)}<br>"
                          f"&nbsp;&nbsp;{sp(r['why'] + ' · no call made', DIM)}")
            continue

        col = UP if r["change_pct"] >= 0 else DOWN
        pct = f"{r['change_pct']:+.2f}%"
        head = f"{sym}&nbsp;&nbsp;{sp(money(r['price']) + '  ' + pct, col, True)}"
        if private and r.get("held_qty"):
            u = r.get("upl", 0)
            head += ("&nbsp;&nbsp;" + sp(f"holding {r['held_qty']:,.0f} @ {money(r['cost'])} ", DIM)
                     + sp(f"{u:+,.0f}", UP if u >= 0 else DOWN))

        rp = risk_pct(r)
        rtxt = sp(f" · risk {rp:.1f}%", DIM) if rp is not None else ""
        act = r["action"]
        if act == "BUY":
            line = sp("BUY", ACC, True) + f" @ {money(r['price'])} · " + \
                sp(f"out below {money(r['invalidation'])}", DOWN) + rtxt
        elif act == "HOLD":
            line = sp("HOLD", FG, True) + " — " + \
                sp(f"out below {money(r['invalidation'])}", DOWN) + rtxt
        elif act == "SELL":
            line = sp("SELL", DOWN, True) + " — regime broke · " + \
                sp(f"re-entry above {money(r['reentry'])}", DIM)
            if r.get("thin"):
                line += sp(" · thin book, work the exit", FLAT)
        elif act == "STAND_ASIDE":
            line = sp("STAND ASIDE", FG, True) + " — " + \
                sp(f"below the line · re-entry above {money(r['reentry'])}", DIM)
        else:
            line = sp("NO TRADE", FG, True) + " — " + sp(r.get("why", "no level in reach"), DIM)

        body = f"{head}<br>&nbsp;&nbsp;{line}"
        if "range_lo" in r:
            body += ("<br>&nbsp;&nbsp;"
                     + sp(f"today {money(r['range_lo'])} – {money(r['range_hi'])}", DIM))
        a = acc_of(r["symbol"], acc)
        if a:
            def c(v):
                if v is None:
                    return sp("—", DIM)
                return sp(f"{v:.0f}%", UP if v >= 55 else (FLAT if v >= 50 else DOWN))
            body += ("<br>&nbsp;&nbsp;" + sp("accuracy&nbsp; 1D ", DIM) + c(a["d1"])
                     + sp("&nbsp; 1M ", DIM) + c(a["m1"]) + sp("&nbsp; 1Y ", DIM) + c(a["y1"])
                     + sp("&nbsp; · band ", DIM) + c(a["band"])
                     + sp(f"&nbsp; ({a['bars']} bars)", DIM))
        blocks.append(body)

    header = sp(stamp(), DIM)
    if private and account:
        header += "<br>" + "<br>".join(sp(ln, DIM) for ln in account_lines(account))

    # The link only makes sense on the public page: it is a sibling file there, and
    # the terminal/email surfaces have no browser to follow it.
    ask = ('<br><br><a href="ask.html" style="color:%s;text-decoration:none;'
           'border-bottom:1px dotted %s;">Any other ticker &rarr; 1D / 5D / 1M read</a>'
           % (ACC, ACC))
    note = ("" if private else
            ask + "<br><br>" + sp("Advice only. Positions and account figures are "
                                  "deliberately not published here.", DIM))

    return (f'<div style="background:{BG};color:{FG};padding:18px 20px;border-radius:10px;'
            f'font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:14px;'
            f'line-height:1.65;max-width:640px;">'
            f'{header}<br><br>' + "<br><br>".join(blocks) + note + '</div>')


def page(rows: list[dict], acc: dict) -> str:
    """Standalone public page. No account data, ever."""
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>i004 · NASDAQ card</title>'
            f'<link rel="icon" href="data:,"></head>'
            f'<body style="margin:0;padding:16px;background:#080d0a;">'
            f'{as_html(rows, acc, private=False)}'
            f'</body></html>')
