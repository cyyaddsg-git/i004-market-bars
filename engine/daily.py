#!/usr/bin/env python3
"""The daily run, in two halves — YY's requirement, stated 2026-09-05:

    one prediction  pre-market, 09:00 SGT
    one settlement  after the close, 08:00 SGT

    python engine/daily.py --settle    08:00 SGT / 00:00 UTC, Tue-Sat
    python engine/daily.py --predict   09:00 SGT / 01:00 UTC, Mon-Fri
    python engine/daily.py             both, in order (local use and recovery)
    python engine/daily.py --dry-run   build and print; writes NOTHING, sends nothing

SETTLE runs first and PREDICT second because a prediction may not be issued
against a book whose previous orders have not been filled yet. That is not a
preference: an unfilled buy reads as a flat position, which produces the same BUY
again the next day and doubles the position. So --predict also settles and fills
before it lodges anything, as a catch-up if the 08:00 run was missed.

SGT is UTC+8 and the US session runs 21:30-04:00 SGT, so 08:00 SGT is four hours
after the close and 09:00 SGT is well before the next open. Both are therefore in
the ET *previous* day, which is why the session date is derived rather than taken
from the clock — see next_session() / last_closed_session().

The two surfaces carry deliberately different content (plan R12):

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
import predictions                             # noqa: E402
import sim                                     # noqa: E402
import render                                  # noqa: E402

ET = zoneinfo.ZoneInfo("America/New_York")
PAGE = os.path.join(REPO, "docs", "index.html")
SIM_PAGE = os.path.join(REPO, "docs", "sim.html")


CLOSE = datetime.time(16, 0)


def next_session(now_et: datetime.datetime) -> datetime.date:
    """The US session this prediction is FOR.

    Never `now_et.date()`. The predict job fires at 01:00 UTC, which is 21:00 ET
    the previous day — so the naive date is one day early, and on a Monday run it
    is a Sunday, which the old weekday gate rejected outright.
    """
    d = now_et.date()
    if now_et.time() >= CLOSE or now_et.weekday() >= 5:
        d += datetime.timedelta(days=1)
    while d.weekday() >= 5:
        d += datetime.timedelta(days=1)
    return d


def last_closed_session(now_et: datetime.datetime) -> datetime.date:
    """The US session whose close has already happened."""
    d = now_et.date()
    if now_et.time() < CLOSE or now_et.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    return d


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


def do_settle(now_et: datetime.datetime, write: bool = True) -> None:
    """Mark the result of what was already claimed. Reads bars from disk only.

    Deliberately touches no market API: it needs nothing Webull has, so an auth
    problem cannot stop yesterday's score from being recorded.
    """
    closed = last_closed_session(now_et)
    settled = predictions.settle()
    filled = sim.fill()
    book = sim.mark()
    print(f"settle {closed} -> {settled} predictions scored, {filled} orders filled, "
          f"equity {book['equity']:,.2f} ({book['pl_pct']:+.2f}%)")
    if write:
        sim.save_book()
        with open(SIM_PAGE, "w") as f:
            f.write(sim.page(book))
        print(f"page  -> {os.path.relpath(SIM_PAGE, REPO)}")


def do_predict(now_et: datetime.datetime, write: bool = True,
               email: bool = True) -> None:
    """Issue one prediction for the session that has not opened yet."""
    session = next_session(now_et)
    cfg = card.load("config.json")
    symbols = card.tradeable(cfg)      # universe + anything the book still holds
    rows, acct, _ = card.build(symbols, cfg)
    acc = card.load("accuracy.json")

    if not [r for r in rows if r["action"] != "NO_DATA"]:
        print("every ticker returned NO DATA — not publishing a card built on nothing")
        sys.exit(1)

    if write:
        # Settle and fill BEFORE lodging, even though --settle normally did it an
        # hour ago. If that run was missed, an unfilled buy reads as a flat
        # position and the same regime lodges the buy a second time — which is
        # exactly how the book ended up doubled and on margin once already.
        # Both calls are idempotent, so the catch-up costs nothing.
        settled, filled = predictions.settle(), sim.fill()

        # Log what we are about to claim BEFORE publishing it. This is the only
        # out-of-sample record of the rule — docs/index.html is overwritten every
        # run and keeps nothing.
        logged = predictions.log(rows, str(session))
        lodged = sim.lodge(rows, str(session))
        live = {r["symbol"]: r["price"] for r in rows if r.get("price")}
        book = sim.mark(live)
        sim.save_book()
        print(f"predict {session} -> {logged} logged, {lodged} lodged "
              f"({settled} settled, {filled} filled on catch-up), "
              f"equity {book['equity']:,.2f} ({book['pl_pct']:+.2f}%)")
        with open(SIM_PAGE, "w") as f:
            f.write(sim.page(book))
        os.makedirs(os.path.dirname(PAGE), exist_ok=True)
        with open(PAGE, "w") as f:
            f.write(render.page(rows, acc))
        print(f"page  -> {os.path.relpath(PAGE, REPO)}")

    private_html = render.as_html(rows, acc, acct, private=True)
    if not email:
        print(render.as_text(rows, acc, acct))
        print("no email sent")
        return

    calls = ", ".join(f"{r['symbol']} {r['action'].replace('_', ' ')}"
                      for r in render.sort_rows(rows)
                      if r["action"] in ("BUY", "SELL"))
    subject = (f"NASDAQ {session:%d %b} — {calls}" if calls else
               f"NASDAQ {session:%d %b} — no new trades")
    print("email ->", send_email(private_html, subject))


def main() -> None:
    a = sys.argv[1:]
    # --dry-run writes NOTHING and sends nothing. It used to log a prediction and
    # lodge paper orders, which made the "safe" flag the unsafe one: dispatching
    # the job by hand to check something silently corrupted the measurement record.
    dry = "--dry-run" in a
    settle_only, predict_only = "--settle" in a, "--predict" in a
    now_et = datetime.datetime.now(ET)

    if settle_only or not predict_only:
        do_settle(now_et, write=not dry)
    if predict_only or not settle_only:
        do_predict(now_et, write=not dry, email=not dry)


if __name__ == "__main__":
    main()
