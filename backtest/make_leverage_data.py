#!/usr/bin/env python3
"""Compute the delta-neutral carry at several leverage levels + a stablecoin-lending
benchmark, and export a compact JSON the landing's interactive chart reads.

Leverage model (transparent, conservative):
  per 8h period, on $1 of capital with leverage L and deployed fraction d:
     income     =  L * d * funding            # carry notional = L*d, earns funding
     friction   =  L * |Δd| * TURNOVER_COST   # bigger position => bigger rebalancing cost
     financing  = (L-1) * d * (FIN_APR / P)   # cost to finance the levered-up notional
     equity    *= 1 + income - friction - financing
  Leverage scales BOTH return and drawdown by ~L. The perfect-hedge backtest CANNOT
  see liquidation risk — the real danger of leverage — which is why the page disclaims it.
"""
import os, sys, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import backtest as bt  # build_dataset, make_decider, PERIODS_PER_YEAR, TURNOVER_COST

OUT = os.path.join(os.path.dirname(HERE), "site", "assets", "equity_data.json")

# ----- assumptions (documented on the page) -----
FIN_APR = 0.04        # blended stablecoin financing cost on the leveraged-up notional
STABLE_APR = 0.05     # passive stablecoin-lending benchmark (flat, compounding)
LEVELS = [1, 2, 5]
P = bt.PERIODS_PER_YEAR

# the rule SKILL.md implements: hold the carry, exit only on a deeply-negative regime
decide = bt.make_decider(entry=0.05, exit_=-0.15, use_guard=False)


def sim_leverage(df, L):
    equity, deploy = 1.0, 0.0
    fin = FIN_APR / P
    eq = np.empty(len(df))
    dep = np.empty(len(df))
    fundings = df["funding"].values
    aprs = df["funding_apr"].values
    fngs = df["fng"].values
    for i in range(len(df)):
        new_d = decide(aprs[i], deploy, fngs[i])
        friction = L * abs(new_d - deploy) * bt.TURNOVER_COST
        deploy = new_d
        income = L * deploy * fundings[i]
        financing = (L - 1) * deploy * fin
        equity *= (1.0 + income - friction - financing)
        eq[i] = equity
        dep[i] = deploy
    return eq, dep


def stats(eq, dep, years):
    rets = np.diff(eq) / eq[:-1]
    total = eq[-1] / eq[0] - 1
    apr = (eq[-1] / eq[0]) ** (1 / years) - 1
    peak = np.maximum.accumulate(eq)
    max_dd = ((eq - peak) / peak).min()
    sharpe = rets.mean() / rets.std() * np.sqrt(P) if rets.std() > 0 else float("nan")
    trades = int((np.abs(np.diff(dep)) > 1e-9).sum())
    return total, apr, max_dd, sharpe, trades


def downsample(arr, n=200):
    N = len(arr)
    step = max(1, N // n)
    idx = list(range(0, N, step))
    if idx[-1] != N - 1:
        idx.append(N - 1)
    return idx


def main():
    df = bt.build_dataset()
    N = len(df)
    years = (df["time"].iloc[-1] - df["time"].iloc[0]).days / 365.25
    t0 = df["time"].iloc[0]
    tyears = ((df["time"] - t0).dt.total_seconds() / (365.25 * 86400)).values

    idx = downsample(df["equity"].values if "equity" in df else df["funding"].values, 200)

    # x-axis year boundaries (first occurrence of each calendar year)
    yrs = df["time"].dt.year.values
    xyears, seen = [], set()
    for i, y in enumerate(yrs):
        if y not in seen:
            seen.add(y)
            xyears.append({"i": i, "label": str(y)})

    # stablecoin-lending benchmark: flat compounding line
    bench = (1.0 + STABLE_APR) ** tyears

    levels = []
    print(f"dataset {N} periods, {years:.2f}y, financing {FIN_APR*100:.0f}% APR, stable bench {STABLE_APR*100:.0f}%\n")
    print(f"  {'leverage':10s} {'return':>9s} {'APR':>8s} {'maxDD':>8s} {'Sharpe':>8s} {'trades':>7s}")
    for L in LEVELS:
        eq, dep = sim_leverage(df, L)
        total, apr, dd, sharpe, trades = stats(eq, dep, years)
        print(f"  {L}x{'':8s} {total*100:8.2f}% {apr*100:7.2f}% {dd*100:7.2f}% {sharpe:8.1f} {trades:7d}")
        levels.append({
            "lev": L,
            "ret": round(float(total), 4),
            "apr": round(float(apr), 4),
            "dd": round(float(dd), 4),
            "sharpe": round(float(sharpe), 1),
            "trades": trades,
            "series": [round(float(eq[i]), 4) for i in idx],
        })

    data = {
        "years": round(float(years), 2),
        "n": len(idx),
        "xYears": xyears if False else [{"i": idx.index(min(idx, key=lambda j: abs(j - xy["i"]))), "label": xy["label"]} for xy in xyears],
        "financingApr": FIN_APR,
        "benchmark": {
            "label": f"Stablecoin lending (~{int(STABLE_APR*100)}% APR)",
            "apr": STABLE_APR,
            "series": [round(float(bench[i]), 4) for i in idx],
        },
        "levels": levels,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"\nwrote {OUT} ({os.path.getsize(OUT)} bytes, {len(idx)} pts/series)")


if __name__ == "__main__":
    main()
