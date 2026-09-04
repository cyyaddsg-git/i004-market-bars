#!/usr/bin/env python3
"""Price + analysis chart for one name, written to docs/chart-<SYM>.html.

    ./chart.sh META [BARS]

Draws exactly what the engine decides on, and nothing decorative:
candles, MA20 (the regime line), MA200 (structural context), the invalidation
and re-entry levels, the 1D/5D/1M expected bands, and volume.

Renderer is TradingView Lightweight Charts v5.2.1, Apache-2.0, VENDORED into
docs/vendor/ rather than pulled from a CDN. The page has to open from the local
disk through show.sh and from GitHub Pages, and a CDN <script> is a silent blank
chart the moment either is offline. 198 KB is cheap insurance.
"""
from __future__ import annotations

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import feed                                                        # noqa: E402
from horizons import HORIZONS, evaluate                            # noqa: E402
from indicators import (BAND, HYST, _sorted_oldest_first,          # noqa: E402
                        atr_series, sma_series, state_series)

DOCS = os.path.normpath(os.path.join(HERE, "..", "docs"))
BG, FG, DIM, UP, DOWN, ACC, WARN = ("#0F1712", "#F2F0E9", "#8fa3b6",
                                    "#4ADE80", "#FF6B6B", "#7dd3fc", "#E8B84B")


def sma(closes: list[float], n: int) -> list[float | None]:
    out, run = [], 0.0
    for i, c in enumerate(closes):
        run += c
        if i >= n:
            run -= closes[i - n]
        out.append(run / n if i + 1 >= n else None)
    return out


def build(sym: str, show: int = 180) -> str:
    r = evaluate(sym)
    bars = _sorted_oldest_first(feed.bars(sym, count=800))
    closes = [b["close"] for b in bars]
    atr = atr_series(bars)
    states = state_series(bars, atr, sma_series(bars))
    m20, m200 = sma(closes, 20), sma(closes, 200)

    lo = max(0, len(bars) - show)
    candles = [{"time": b["date"], "open": b["open"], "high": b["high"],
                "low": b["low"], "close": b["close"]} for b in bars[lo:]]
    vol = [{"time": b["date"], "value": b["volume"],
            "color": (UP if b["close"] >= b["open"] else DOWN) + "55"}
           for b in bars[lo:]]
    line = lambda s: [{"time": b["date"], "value": s[i]}
                      for i, b in enumerate(bars) if i >= lo and s[i] is not None]

    # Regime shading: one marker where the state actually flips, not one per bar.
    flips = [{"time": bars[i]["date"], "position": "belowBar" if states[i] == "IN" else "aboveBar",
              "color": UP if states[i] == "IN" else DOWN,
              "shape": "arrowUp" if states[i] == "IN" else "arrowDown",
              "text": states[i]}
             for i in range(lo, len(bars)) if states[i] != states[i - 1]]

    levels = [{"price": r["invalidation"], "color": DOWN, "title": "exit"},
              {"price": r["reentry"], "color": WARN, "title": "re-entry"}]
    for row, col in zip(r["rows"], (ACC, ACC, ACC)):
        levels += [{"price": row["hi"], "color": col, "title": f"{row['label']} hi"},
                   {"price": row["lo"], "color": col, "title": f"{row['label']} lo"}]

    rows_html = "".join(
        f"<tr><td>{x['label']}</td><td>{x['lo']:,.0f} – {x['hi']:,.0f}</td>"
        f"<td>±{x['half_pct']:.1f}%</td><td>{x['band_pct']:.0f}%</td>"
        f"<td class='{'neg' if x['edge'] <= 0 else 'pos'}'>{x['edge']:+.0f}pp</td></tr>"
        for x in r["rows"])

    ctx = {"candles": candles, "vol": vol, "m20": line(m20), "m200": line(m200),
           "flips": flips, "levels": levels}
    # <meta charset> is not optional: served by python http.server or opened from
    # file://, Chrome guesses latin-1 and every em-dash and ± becomes mojibake.
    # MEASURED 2026-09-04 on the first render of this page.
    return f"""<meta charset="utf-8">
<title>{sym} — price &amp; regime</title>
<style>
 body {{ background:{BG}; color:{FG}; font:14px -apple-system,Helvetica,Arial,sans-serif;
        margin:0; padding:24px; }}
 h1 {{ font-size:1.2em; margin:0 0 2px; }} h1 span {{ color:{DIM}; font-weight:400; }}
 .sub {{ color:{DIM}; margin-bottom:14px; font-size:.9em; }}
 /* line-height:0 — the chart's panes are inline-level, so the body's 14px
    line-height pushed them down 17px and the time axis overflowed the box. */
 #c {{ height:540px; border:1px solid #24312a; border-radius:6px;
       box-sizing:border-box; line-height:0; }}
 /* SCOPED to .h — a bare `table` rule also hit the chart library's own internal
    <table>, whose margin-top pushed the time axis 16px out of a clipped wrapper.
    MEASURED 2026-09-04. Never style bare tags on a page hosting a widget. */
 table.h {{ border-collapse:collapse; margin-top:16px; font-size:.92em; }}
 table.h th, table.h td {{ padding:5px 14px 5px 0; text-align:left;
                           border-bottom:1px solid #24312a; }}
 table.h th {{ color:{DIM}; font-weight:500; }}
 .pos {{ color:{UP}; }} .neg {{ color:{DOWN}; }}
 .note {{ color:{DIM}; font-size:.85em; margin-top:12px; max-width:640px; line-height:1.5; }}
</style>
<h1>{sym} <span>{r['price']:,.2f} ({r['change_pct']:+.2f}%) · regime {r['regime']}</span></h1>
<div class="sub">{r['bars']} bars {r['first']} → {r['last_bar']} · price source {r['src']}
 · MA20 {r['sma20']:,.0f} · MA200 {r.get('sma200', float('nan')):,.0f}
 · ATR {r['atr_pct']:.1f}% · 52w {r['r52']['pos']:.0f}% of range</div>
<div id="c"></div>
<table class="h"><tr><th>horizon</th><th>expected range</th><th>half-width</th>
 <th>band held</th><th>edge vs hold</th></tr>{rows_html}</table>
<div class="note">Dashed lines are the levels the rule acts on: red = exit
 ({r['invalidation']:,.2f}), amber = re-entry, blue = the 1D/5D/1M expected bands.
 <b>Edge</b> is the model's hit-rate minus the share of windows the stock rose anyway —
 at or below zero the direction call adds nothing and only the band is worth reading.</div>
<script src="vendor/lightweight-charts.standalone.production.js"></script>
<script>
const D = {json.dumps(ctx)};
// autoSize, not a resize listener: createChart measures the container ONCE, so a
// chart built in a narrow window stayed narrow after the window grew. MEASURED
// 2026-09-04 — the canvas was 452px inside an 880px box.
const chart = LightweightCharts.createChart(document.getElementById('c'), {{
  autoSize: true,
  layout: {{ background: {{ color: '{BG}' }}, textColor: '{DIM}', attributionLogo: false }},
  grid: {{ vertLines: {{ color: '#1a241e' }}, horzLines: {{ color: '#1a241e' }} }},
  rightPriceScale: {{ borderColor: '#24312a', scaleMargins: {{ top: 0.08, bottom: 0.28 }} }},
  timeScale: {{ borderColor: '#24312a' }},
  crosshair: {{ mode: 0 }},
}});
const candles = chart.addSeries(LightweightCharts.CandlestickSeries, {{
  upColor: '{UP}', downColor: '{DOWN}', borderVisible: false,
  wickUpColor: '{UP}', wickDownColor: '{DOWN}' }});
candles.setData(D.candles);
for (const l of D.levels)
  candles.createPriceLine({{ price: l.price, color: l.color, lineWidth: 1,
    lineStyle: 2, axisLabelVisible: true, title: l.title }});
LightweightCharts.createSeriesMarkers(candles, D.flips);
chart.addSeries(LightweightCharts.LineSeries, {{ color: '{WARN}', lineWidth: 1,
  priceLineVisible: false, lastValueVisible: false, title: 'MA20' }}).setData(D.m20);
chart.addSeries(LightweightCharts.LineSeries, {{ color: '{DIM}', lineWidth: 1,
  priceLineVisible: false, lastValueVisible: false, title: 'MA200' }}).setData(D.m200);
const v = chart.addSeries(LightweightCharts.HistogramSeries, {{
  priceFormat: {{ type: 'volume' }}, priceScaleId: 'v' }});
v.setData(D.vol);
chart.priceScale('v').applyOptions({{ scaleMargins: {{ top: 0.82, bottom: 0 }} }});
chart.timeScale().fitContent();
</script>
"""


def main() -> None:
    sym = (sys.argv[1] if len(sys.argv) > 1 else "META").upper()
    show = int(sys.argv[2]) if len(sys.argv) > 2 else 180
    out = os.path.join(DOCS, f"chart-{sym}.html")
    os.makedirs(DOCS, exist_ok=True)
    with open(out, "w") as f:
        f.write(build(sym, show))
    print(out)


if __name__ == "__main__":
    main()
