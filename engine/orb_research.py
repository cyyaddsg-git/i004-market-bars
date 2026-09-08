#!/usr/bin/env python3
"""Intraday ORB research. Sweeps the engine/intraday.py rule over the sessions
Webull will return (count is capped at 1200 bars) for one symbol plus controls.
Written 2026-09-08 for the ORBS study -- see research-orbs-intraday.html.

Original docstring:
Intraday ORB research. Replays the engine/intraday.py rule bar-by-bar over
every complete session available, with the parameters swept.

Nothing is imported from the daily engine. Fills are conservative: entry at the
CLOSE of the bar that triggers (you cannot fill inside a bar you have not seen),
stop/target checked on the FOLLOWING bars' high/low, stop taking precedence when
a single bar spans both (the pessimistic assumption).
"""
import sys, os, json, itertools, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import intraday

SPAN_MIN = {"M1":1,"M5":5,"M15":15,"M30":30}
RTH_START = "13:30"          # 09:30 ET in UTC (EDT)
RTH_END   = "20:00"

def sessions(sym, ts, count=1200):
    bs = intraday.bars(sym, ts, count)
    byday = {}
    for b in bs:
        hm = b["t"][11:16]
        if hm < RTH_START or hm >= RTH_END:      # regular hours only
            continue
        byday.setdefault(b["t"][:10], []).append(b)
    return byday

def atr_from(bs, n=14):
    if len(bs) < n+1: return None
    trs=[max(c["h"]-c["l"],abs(c["h"]-p["c"]),abs(c["l"]-p["c"])) for p,c in zip(bs,bs[1:])]
    a=sum(trs[:n])/n
    for tr in trs[n:]: a=(a*(n-1)+tr)/n
    return a

def replay_day(day_bars, prior_bars, ts, orb_min, stop_pad, r_mult,
               use_vwap=True, exit_on_vwap=True):
    """One session. Returns a trade dict or None (no setup)."""
    span = SPAN_MIN[ts]
    n_orb = max(1, orb_min // span)
    if len(day_bars) < n_orb + 3: return None
    orb = day_bars[:n_orb]
    orh = max(b["h"] for b in orb); orl = min(b["l"] for b in orb)
    a = atr_from(prior_bars + day_bars[:n_orb]) or atr_from(day_bars)
    if not a: return None

    state=None; entry=stop=target=None; entry_i=None
    run_v=run_pv=0.0
    for i,b in enumerate(day_bars):
        run_v += b["v"]; run_pv += (b["h"]+b["l"]+b["c"])/3*b["v"]
        vw = run_pv/run_v if run_v else b["c"]
        if state is None and i >= n_orb:
            long_ok  = b["c"] > orh and (b["c"] > vw or not use_vwap)
            short_ok = b["c"] < orl and (b["c"] < vw or not use_vwap)
            if long_ok:
                state="LONG";  entry=b["c"]; stop=max(orh,vw)-stop_pad*a
            elif short_ok:
                state="SHORT"; entry=b["c"]; stop=min(orl,vw)+stop_pad*a
            if state:
                risk=abs(entry-stop)
                if risk<=0: state=None; continue
                target = entry + r_mult*risk if state=="LONG" else entry - r_mult*risk
                entry_i=i
                continue
        if state and i>entry_i:
            hit_stop = b["l"]<=stop if state=="LONG" else b["h"]>=stop
            hit_tgt  = b["h"]>=target if state=="LONG" else b["l"]<=target
            if hit_stop:  return _t(state,entry,stop,target,stop,"STOP",day_bars,entry_i,i)
            if hit_tgt:   return _t(state,entry,stop,target,target,"TARGET",day_bars,entry_i,i)
            if exit_on_vwap and ((state=="LONG" and b["c"]<vw) or (state=="SHORT" and b["c"]>vw)):
                return _t(state,entry,stop,target,b["c"],"VWAP",day_bars,entry_i,i)
    if state:
        return _t(state,entry,stop,target,day_bars[-1]["c"],"EOD",day_bars,entry_i,len(day_bars)-1)
    return None

def _t(side,entry,stop,target,exitp,why,bars,i0,i1):
    risk=abs(entry-stop)
    pnl=(exitp-entry) if side=="LONG" else (entry-exitp)
    return dict(side=side,entry=entry,stop=stop,target=target,exit=exitp,why=why,
                R=pnl/risk if risk else 0.0, ret_pct=pnl/entry*100,
                risk_pct=risk/entry*100, bars_held=i1-i0,
                t_in=bars[i0]["t"][11:16], t_out=bars[i1]["t"][11:16])

def summarise(trades, label, n_sessions):
    if not trades:
        return dict(label=label, n=0, sessions=n_sessions)
    Rs=[t["R"] for t in trades]
    wins=[r for r in Rs if r>0]
    return dict(label=label, n=len(trades), sessions=n_sessions,
                fired_pct=round(100*len(trades)/n_sessions,1),
                win_pct=round(100*len(wins)/len(Rs),1),
                totR=round(sum(Rs),2), avgR=round(sum(Rs)/len(Rs),3),
                medR=round(st.median(Rs),3),
                avg_risk_pct=round(sum(t["risk_pct"] for t in trades)/len(trades),2),
                exits={w: sum(1 for t in trades if t["why"]==w) for w in ("TARGET","STOP","VWAP","EOD")})
