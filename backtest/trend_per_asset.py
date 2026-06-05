#!/usr/bin/env python3
"""Does trend-following work BETTER on BNB than BTC? Same rule, same costs, same
period — just swap the asset. Report full + out-of-sample metrics."""
import os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare_strategies as cs
import research_strategies as rs

panel = cs.build_panel()
rets = panel.pct_change().fillna(0.0)
idx = panel.index
n = len(panel)
split = n // 2
cols = panel.columns
years = (idx[-1] - idx[0]).days / 365.25


def zeros():
    return pd.DataFrame(0.0, index=idx, columns=cols)


def trend(asset, ma):
    w = zeros()
    w[asset] = (panel[asset] > panel[asset].rolling(ma).mean()).fillna(False).astype(float).values
    return w


def hold(asset):
    w = zeros(); w[asset] = 1.0
    return w


def row(label, w):
    daily, turn, inv = rs.to_daily(w, rets)
    tot, apr, mdd, shp = rs.perf(daily)
    _, _, _, oos = rs.perf(daily.iloc[split:])
    tyr = (turn > 1e-6).sum() / years
    return label, tot, apr, mdd, shp, oos, tyr


tests = []
for asset in ["BTC", "BNB", "ETH", "SOL"]:
    tests.append(row(f"buy & hold {asset}", hold(asset)))
    for ma in [50, 100, 200]:
        tests.append(row(f"trend {asset} {ma}d", trend(asset, ma)))

print(f"panel {idx[0].date()}->{idx[-1].date()}, OOS split {idx[split].date()}\n")
print(f"  {'strategy':22s} {'ret':>9s} {'APR':>7s} {'maxDD':>7s} {'Sharpe':>7s} {'OOS':>6s} {'t/yr':>5s}")
last = None
for label, tot, apr, mdd, shp, oos, tyr in tests:
    a = label.split()[-2] if "trend" in label else label.split()[-1]
    if last and a != last:
        print()
    print(f"  {label:22s} {tot*100:8.0f}% {apr*100:6.0f}% {mdd*100:6.0f}% {shp:7.2f} {oos:6.2f} {tyr:5.0f}")
    last = a
