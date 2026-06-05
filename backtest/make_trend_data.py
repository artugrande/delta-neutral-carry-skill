#!/usr/bin/env python3
"""Export the trend-following chart data + the 27-strategy research summary the
landing reads. Trend BTC at 50/100/200-day MA vs buy & hold BTC, normalized to
growth of $1, downsampled, with stats (incl. out-of-sample Sharpe)."""
import os, sys, json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare_strategies as cs
import research_strategies as rs

OUT = os.path.join(os.path.dirname(HERE), "site", "assets", "trend_data.json")
WINDOWS = [50, 100, 200]
DEFAULT = 100


def main():
    panel = cs.build_panel()
    rets = panel.pct_change().fillna(0.0)
    idx = panel.index
    n = len(panel)
    split = n // 2
    btc = panel["BTC"]
    years = (idx[-1] - idx[0]).days / 365.25

    # downsample positions
    step = max(1, n // 210)
    samp = list(range(0, n, step))
    if samp[-1] != n - 1:
        samp.append(n - 1)

    def ser(eq):
        return [round(float(eq.iloc[i]), 4) for i in samp]

    def zeros():
        return pd.DataFrame(0.0, index=idx, columns=panel.columns)

    # year ticks mapped to downsample positions
    yrs = idx.year.values
    xyears, seen = [], set()
    for i, y in enumerate(yrs):
        if y not in seen:
            seen.add(y)
            pos = min(range(len(samp)), key=lambda k: abs(samp[k] - i))
            xyears.append({"i": pos, "label": str(int(y))})

    # buy & hold BTC benchmark
    eq_bh = btc / btc.iloc[0]
    tot, apr, mdd, shp = rs.perf(rets["BTC"])
    _, _, _, oos = rs.perf(rets["BTC"].iloc[split:])
    benchmark = {"label": "Buy & hold BTC", "series": ser(eq_bh),
                 "ret": round(tot, 4), "apr": round(apr, 4), "dd": round(mdd, 4),
                 "sharpe": round(shp, 2), "oos": round(oos, 2), "trades": 0}

    windows = []
    print(f"  {'window':8s} {'ret':>8s} {'APR':>7s} {'maxDD':>7s} {'Sharpe':>7s} {'OOS':>6s} {'t/yr':>5s} {'in-mkt':>7s}")
    for ma in WINDOWS:
        w = zeros()
        w["BTC"] = (btc > btc.rolling(ma).mean()).fillna(False).astype(float).values
        daily, turn, invested = rs.to_daily(w, rets)
        eq = (1 + daily).cumprod()
        tot, apr, mdd, shp = rs.perf(daily)
        _, _, _, oos = rs.perf(daily.iloc[split:])
        tyr = (turn > 1e-6).sum() / years
        inmkt = float((invested > 0.01).mean())
        print(f"  {ma}d{'':5s} {tot*100:7.0f}% {apr*100:6.0f}% {mdd*100:6.0f}% {shp:7.2f} {oos:6.2f} {tyr:5.0f} {inmkt*100:6.0f}%")
        windows.append({"ma": ma, "label": f"{ma}-day MA", "series": ser(eq),
                        "ret": round(tot, 4), "apr": round(apr, 4), "dd": round(mdd, 4),
                        "sharpe": round(shp, 2), "oos": round(oos, 2),
                        "trades": int(round(tyr)), "inmkt": round(inmkt, 3)})

    data = {"years": round(years, 2), "n": len(samp), "split": str(idx[split].date()),
            "xYears": xyears, "benchmark": benchmark, "windows": windows, "default": DEFAULT}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"\nwrote {OUT} ({os.path.getsize(OUT)} bytes, {len(samp)} pts/series)")


if __name__ == "__main__":
    main()
