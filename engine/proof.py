#!/usr/bin/env python3
"""
Does the advice card actually work? Scored against a baseline, because a hit rate
without one proves nothing.

    python3 engine/proof.py

WHY (YY, 2026-08-31): "at the end of the day, this simulation shall serve as a proof of
your advice card accuracy." Agreed -- and measured against that purpose the log had a
hole in it. On 2026-08-31 the settled predictions read: direction 10/14, 71%. That looks
like skill. It is not. On the same rows, ALWAYS SAYING "IN" would also have scored 71%,
because 10 of those 14 names simply rose. The edge over the naive alternative was
exactly ZERO, and nothing in the scoring said so.

THE THREE THINGS THAT MAKE A HIT RATE MEAN SOMETHING

  1. A BASELINE. Direction is scored against "always IN", the dumbest possible rule. If
     the model cannot beat it, the model is a costlier way to be long. A band claim is
     scored against its own backtested 82%, since that is the number it was sold on.

  2. THE HONEST n. Fourteen rows issued across two sessions is not fourteen
     observations: on a broadly rising day every IN call is right at once, so the rows
     within a day are one bet, not seven. This reports SESSIONS as well as rows, and the
     session count is the one that governs.

  3. A REFUSAL TO CLAIM. Below MIN_SESSIONS the verdict is "not enough evidence" and no
     edge is asserted, however good the percentage looks. The previous build's headline
     was a 93% band containment that was almost never actionable; the way that happens is
     by reporting a flattering number without the thing it should be compared against.

This file only reads. It never writes to the prediction log, and it is deliberately not
importable by the card -- a scorer that can touch what it scores is not a scorer.
"""
import collections
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PRED = os.path.join(os.path.dirname(HERE), "data", "predictions.csv")

BAND_CLAIM = 0.82        # what the 0.8 x ATR sweep promised, over 800 bars x 7 tickers
MIN_SESSIONS = 30        # independent sessions, not rows


def load():
    if not os.path.exists(PRED):
        sys.exit(f"no prediction log at {PRED}")
    with open(PRED, newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("settle_close")]


def report(rows):
    if not rows:
        print("no settled predictions yet — nothing to prove either way")
        return
    sessions = sorted({r["issued_date"] for r in rows})
    n, s = len(rows), len(sessions)

    up = sum(1 for r in rows if float(r["settle_close"]) > float(r["base_close"]))
    hit = sum(1 for r in rows if r["dir_hit"] == "1")
    band = sum(1 for r in rows if r["band_hit"] == "1")
    inn = sum(1 for r in rows if r["regime"] == "IN")

    print(f"settled rows        {n}")
    print(f"independent sessions {s}   <- the n that governs")
    print()
    print(f"{'':22}{'model':>10}{'baseline':>12}{'edge':>10}")
    print(f"{'direction':22}{hit/n*100:>9.0f}%{up/n*100:>11.0f}%"
          f"{(hit-up)/n*100:>+9.0f}pts")
    print(f"{'band containment':22}{band/n*100:>9.0f}%{BAND_CLAIM*100:>11.0f}%"
          f"{(band/n-BAND_CLAIM)*100:>+9.0f}pts")
    print(f"{'said IN':22}{inn/n*100:>9.0f}%")
    print()
    print("baseline = 'always say IN', which scores whatever fraction of names rose.")
    print("band baseline = the 82% the 0.8 x ATR sweep promised.")
    print()
    print("per session:")
    for d in sessions:
        dr = [r for r in rows if r["issued_date"] == d]
        u = sum(1 for r in dr if float(r["settle_close"]) > float(r["base_close"]))
        h = sum(1 for r in dr if r["dir_hit"] == "1")
        b = sum(1 for r in dr if r["band_hit"] == "1")
        print(f"  {d}  {len(dr)} names · {u} rose · direction {h}/{len(dr)} · "
              f"band {b}/{len(dr)}")

    print()
    if s < MIN_SESSIONS:
        print(f"VERDICT: NOT ENOUGH EVIDENCE — {s} session(s) against {MIN_SESSIONS} "
              f"needed. No edge is claimed, whatever the percentages above look like.")
        if n > s * 3:
            print(f"         And note the shape of it: {n} rows over {s} session(s). On a "
                  f"broadly rising day every IN call is right at once, so those rows are "
                  f"not independent observations.")
    else:
        edge = (hit - up) / n
        if edge <= 0:
            print(f"VERDICT: NO DIRECTIONAL EDGE — the model scores {hit/n*100:.0f}% and "
                  f"always-IN scores {up/n*100:.0f}%. That is not a reason to stop: "
                  f"§1 never claimed direction. Judge it on band and on R.")
        else:
            print(f"VERDICT: direction beats always-IN by {edge*100:+.0f}pts over {s} "
                  f"sessions.")


def main():
    report(load())


if __name__ == "__main__":
    main()
