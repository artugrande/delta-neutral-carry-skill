#!/usr/bin/env python3
"""Can we make trend-following MORE ROBUST (better expected FORWARD return), without
overfitting? Test honest, well-documented enhancements vs the BTC-100d base and
report full-period + out-of-sample metrics. Goal: lift OOS Sharpe / cut whipsaw,
not crank the in-sample number."""
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
FIN = 0.04 / 365.0  # financing drag per day for the leverage variant


def zeros():
    return pd.DataFrame(0.0, index=idx, columns=cols)


def trend_btc(ma=100):
    w = zeros()
    w["BTC"] = (panel["BTC"] > panel["BTC"].rolling(ma).mean()).fillna(False).astype(float).values
    return w


def trend_majors(majors=("BTC", "ETH", "BNB", "SOL"), ma=100):
    w = zeros()
    for c in majors:
        if c in cols:
            w[c] = (panel[c] > panel[c].rolling(ma).mean()).fillna(False).astype(float).values / len(majors)
    return w


def trend_buffer(ma=100, band=0.02):
    ma_s = panel["BTC"].rolling(ma).mean()
    u = (panel["BTC"] > ma_s * (1 + band)).values
    d = (panel["BTC"] < ma_s * (1 - band)).values
    pos = 0.0
    col = np.zeros(n)
    for i in range(n):
        if u[i]:
            pos = 1.0
        elif d[i]:
            pos = 0.0
        col[i] = pos
    w = zeros()
    w["BTC"] = col
    return w


def trend_voltarget(ma=100, target=0.6, win=20):
    base = (panel["BTC"] > panel["BTC"].rolling(ma).mean()).fillna(False).astype(float)
    vol = rets["BTC"].rolling(win).std() * np.sqrt(365)
    scale = (target / vol).clip(0, 1).fillna(0.0)
    w = zeros()
    w["BTC"] = (base * scale).values
    return w


def majors_voltarget(ma=100):
    w = trend_majors(ma=ma)
    vol = rets["BTC"].rolling(20).std() * np.sqrt(365)
    scale = (0.6 / vol).clip(0, 1).fillna(0.0)
    return w.mul(scale.values, axis=0)


def perf_row(label, w, lev=1.0):
    daily, turn, inv = rs.to_daily(w, rets)
    if lev != 1.0:
        # scale returns by leverage, subtract financing on the borrowed part
        borrowed = (inv * (lev - 1)).clip(lower=0)
        daily = daily * lev - borrowed * FIN
    tot, apr, mdd, shp = rs.perf(daily)
    _, _, _, oos = rs.perf(daily.iloc[split:])
    tyr = (turn > 1e-6).sum() / years
    return label, tot, apr, mdd, shp, oos, tyr


VARIANTS = [
    perf_row("trend BTC 100d  (base)", trend_btc()),
    perf_row("trend majors x4 (BTC/ETH/BNB/SOL)", trend_majors()),
    perf_row("trend BTC + 2% buffer band", trend_buffer()),
    perf_row("trend BTC + vol target", trend_voltarget()),
    perf_row("majors x4 + vol target", majors_voltarget()),
    perf_row("trend BTC 100d @ 1.5x lev", trend_btc(), lev=1.5),
]

print(f"panel {len(cols)} assets, {idx[0].date()}->{idx[-1].date()}, OOS split {idx[split].date()}\n")
print(f"  {'variant':36s} {'ret':>8s} {'APR':>7s} {'maxDD':>7s} {'Sharpe':>7s} {'OOS':>6s} {'t/yr':>5s}")
for label, tot, apr, mdd, shp, oos, tyr in VARIANTS:
    print(f"  {label:36s} {tot*100:7.0f}% {apr*100:6.0f}% {mdd*100:6.0f}% {shp:7.2f} {oos:6.2f} {tyr:5.0f}")
print("\n  (honest read: we want HIGHER OOS Sharpe and/or LOWER maxDD vs base — robustness, not a bigger in-sample number)")
