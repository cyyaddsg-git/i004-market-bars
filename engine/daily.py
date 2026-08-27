#!/usr/bin/env python3
"""The daily run: build the card once, publish it two ways.

    python engine/daily.py            # page + email
    python engine/daily.py --dry-run  # build and print, send nothing

Runs on GitHub Actions at 13:00 UTC (21:00 SGT) on weekdays — 30 minutes before
the US open — so it does not matter whether YY's Mac is awake.

The two surfaces carry deliberately different content (plan R12):

    docs/index.html   PUBLIC   advice only. No holdings, no equity, no P&L.
    email             PRIVATE  the same advice plus the account lines.

It also serves a second purpose: the Webull token dies after 15 consecutive days
without an API call, and the Yahoo bars job does not touch Webull. This run does,
every weekday, which is what keeps the token alive.
"""
from __future__ import annotations

import datetime
import os
import smtplib
import sys
import zoneinfo
from email.message import EmailMessage

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import card                                    # noqa: E402
import render                                  # noqa: E402

ET = zoneinfo.ZoneInfo("America/New_York")
PAGE = os.path.join(REPO, "docs", "index.html")


def trading_day(now_et: datetime.datetime) -> bool:
    """Weekday only. US market holidays are not handled — a holiday produces a
    card whose prices simply have not moved, which is visible rather than wrong."""
    return now_et.weekday() < 5


def send_email(html: str, subject: str) -> str:
    user = os.environ.get("SMTP_USER", "genalphai.production@gmail.com")
    pw = os.environ.get("SMTP_APP_PASSWORD")
    to = os.environ.get("REPORT_TO")
    if not (pw and to):
        return "skipped — SMTP_APP_PASSWORD or REPORT_TO not set"

    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.set_content("This card needs an HTML-capable mail client.")
    msg.add_alternative(f"<html><body style='margin:0;background:#080d0a;padding:12px'>"
                        f"{html}</body></html>", subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, pw)
        s.send_message(msg)
    return f"sent to {to}"


def main() -> None:
    dry = "--dry-run" in sys.argv
    now_et = datetime.datetime.now(ET)
    if not trading_day(now_et) and not dry:
        print(f"{now_et:%Y-%m-%d} is not a trading day — no card")
        return

    cfg = card.load("config.json")
    symbols = list(dict.fromkeys(cfg["watchlist"]))
    rows, acct, _ = card.build(symbols, cfg)
    acc = card.load("accuracy.json")

    if not [r for r in rows if r["action"] != "NO_DATA"]:
        print("every ticker returned NO DATA — not publishing a card built on nothing")
        sys.exit(1)

    os.makedirs(os.path.dirname(PAGE), exist_ok=True)
    with open(PAGE, "w") as f:
        f.write(render.page(rows, acc))
    print(f"page  -> {os.path.relpath(PAGE, REPO)}")

    private_html = render.as_html(rows, acc, acct, private=True)
    if dry:
        print(render.as_text(rows, acc, acct))
        print("dry run — no email sent")
        return

    calls = ", ".join(f"{r['symbol']} {r['action'].replace('_', ' ')}"
                      for r in render.sort_rows(rows)
                      if r["action"] in ("BUY", "SELL"))
    subject = f"NASDAQ {now_et:%d %b} — {calls}" if calls else \
              f"NASDAQ {now_et:%d %b} — no new trades"
    print("email ->", send_email(private_html, subject))


if __name__ == "__main__":
    main()
