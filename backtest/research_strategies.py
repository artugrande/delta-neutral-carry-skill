#!/usr/bin/env python3
"""Deep research sweep: backtest ~30 candidate strategies on the SAME daily data
and rank them, with an in-sample / out-of-sample split so the winner has to prove
it generalizes (guards against picking the luckiest of many).

Families: passive benchmarks, trend/regime (time-series momentum), cross-sectional
momentum, mean-reversion, Fear & Greed, volatility targeting, low-vol, and combos.
Same realistic turnover cost + cash yield as compare_strategies.py.
"""
import os, sys, json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import compare_strategies as cs   # build_panel, fetch_fng, TURNOVER_COST, CASH_APR

OUT = os.path.join(os.path.dirname(HERE), "site", "assets", "research.json")


def to_daily(weights, rets):
    w = weights.reindex(rets.index).fillna(0.0)
    invested = w.sum(axis=1).clip(0, 1)
    gross = (w * rets).sum(axis=1)
    cash = (1 - invested).clip(lower=0) * (cs.CASH_APR / 365.0)
    turn = w.diff().abs().sum(axis=1).fillna(0.0)
    daily = gross + cash - turn * cs.TURNOVER_COST
    return daily, turn, invested


def perf(daily):
    eq = (1 + daily).cumprod()
    years = (daily.index[-1] - daily.index[0]).days / 365.25
    total = eq.iloc[-1] - 1
    apr = eq.iloc[-1] ** (1 / years) - 1 if years > 0 else float("nan")
    mdd = ((eq - eq.cummax()) / eq.cummax()).min()
    sharpe = daily.mean() / daily.std() * np.sqrt(365) if daily.std() > 0 else float("nan")
    return total, apr, mdd, sharpe


def main():
    panel = cs.build_panel()
    rets = panel.pct_change().fillna(0.0)
    cols = panel.columns
    n = len(panel)
    idx = panel.index
    fng = cs.fetch_fng().reindex(idx).ffill()
    split = n // 2  # in-sample / out-of-sample boundary

    def zeros():
        return pd.DataFrame(0.0, index=idx, columns=cols)

    def hold(asset):
        w = zeros(); w[asset] = 1.0; return w

    def trend(asset, win):
        w = zeros(); ma = panel[asset].rolling(win).mean()
        w[asset] = (panel[asset] > ma).fillna(False).astype(float).values
        return w

    def dual_ma(asset, fast, slow):
        w = zeros()
        f, s = panel[asset].rolling(fast).mean(), panel[asset].rolling(slow).mean()
        w[asset] = (f > s).fillna(False).astype(float).values
        return w

    def trend_basket(win):
        w = zeros()
        for c in cols:
            ma = panel[c].rolling(win).mean()
            w[c] = (panel[c] > ma).fillna(False).astype(float).values / len(cols)
        return w

    def rebal_mask(freq):
        s = idx.to_series()
        if freq == "W":
            key = s.dt.isocalendar().week.astype(int) + s.dt.year * 100
        else:  # monthly
            key = s.dt.month + s.dt.year * 100
        return key.ne(key.shift()).values

    def momentum(K, LB, freq="W", regime=False):
        mom = panel / panel.shift(LB) - 1
        mask = rebal_mask(freq)
        regime_on = (panel["BTC"] > panel["BTC"].rolling(100).mean()).fillna(False).values
        w = zeros(); cur = pd.Series(0.0, index=cols)
        for i in range(n):
            if mask[i] and i >= LB:
                top = mom.iloc[i].dropna().sort_values(ascending=False).head(K).index
                cur = pd.Series(0.0, index=cols); cur[top] = 1.0 / K
            row = cur.copy()
            if regime and not regime_on[i]:
                row[:] = 0.0
            w.iloc[i] = row.values
        return w

    def rsi_strat(asset, lo=30, hi=70, period=14):
        d = panel[asset].diff()
        up = d.clip(lower=0).rolling(period).mean()
        dn = (-d.clip(upper=0)).rolling(period).mean()
        rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
        w = zeros(); pos = 0.0; col = np.zeros(n)
        rv = rsi.values
        for i in range(n):
            if not np.isnan(rv[i]):
                if rv[i] < lo: pos = 1.0
                elif rv[i] > hi: pos = 0.0
            col[i] = pos
        w[asset] = col
        return w

    def buydip(asset, drop=-0.15, hold_days=20):
        r7 = panel[asset] / panel[asset].shift(7) - 1
        w = zeros(); cnt = 0; col = np.zeros(n); rv = r7.values
        for i in range(n):
            if not np.isnan(rv[i]) and rv[i] < drop:
                cnt = hold_days
            col[i] = 1.0 if cnt > 0 else 0.0
            cnt = max(0, cnt - 1)
        w[asset] = col
        return w

    def fng_contra(asset="BTC", basket=False):
        fw = pd.Series(0.5, index=idx)
        fw[fng <= 25] = 1.0
        fw[fng >= 75] = 0.0
        w = zeros()
        if basket:
            for c in cols:
                w[c] = fw.values / len(cols)
        else:
            w[asset] = fw.values
        return w

    def voltarget(asset, target=0.60, win=20):
        vol = rets[asset].rolling(win).std() * np.sqrt(365)
        wt = (target / vol).clip(0, 1).fillna(0.0)
        w = zeros(); w[asset] = wt.values
        return w

    def lowvol(K, win=30, freq="W"):
        vol = rets.rolling(win).std()
        mask = rebal_mask(freq)
        w = zeros(); cur = pd.Series(0.0, index=cols)
        for i in range(n):
            if mask[i] and i >= win:
                lo = vol.iloc[i].dropna().sort_values().head(K).index
                cur = pd.Series(0.0, index=cols); cur[lo] = 1.0 / K
            w.iloc[i] = cur.values
        return w

    def combo_mom_regime_vol(K=5, LB=30):
        w = momentum(K, LB, "W", regime=True)
        # scale whole book by BTC vol target
        vol = rets["BTC"].rolling(20).std() * np.sqrt(365)
        scale = (0.6 / vol).clip(0, 1).fillna(0.0)
        return w.mul(scale.values, axis=0)

    STRATS = [
        ("buy & hold BTC", hold("BTC"), "passive"),
        ("buy & hold ETH", hold("ETH"), "passive"),
        ("equal-weight basket (hold)", pd.DataFrame(1.0/len(cols), index=idx, columns=cols), "passive"),
        ("60% BTC / 40% cash", hold("BTC")*0.6, "passive"),
        ("trend BTC 50d MA", trend("BTC", 50), "trend"),
        ("trend BTC 100d MA", trend("BTC", 100), "trend"),
        ("trend BTC 150d MA", trend("BTC", 150), "trend"),
        ("trend BTC 200d MA", trend("BTC", 200), "trend"),
        ("trend ETH 100d MA", trend("ETH", 100), "trend"),
        ("dual-MA BTC 50/200", dual_ma("BTC", 50, 200), "trend"),
        ("dual-MA BTC 20/100", dual_ma("BTC", 20, 100), "trend"),
        ("trend basket 100d MA", trend_basket(100), "trend"),
        ("trend basket 50d MA", trend_basket(50), "trend"),
        ("momentum top1 (W,30d)", momentum(1, 30), "momentum"),
        ("momentum top3 (W,30d)", momentum(3, 30), "momentum"),
        ("momentum top5 (W,30d)", momentum(5, 30), "momentum"),
        ("momentum top5 (W,90d)", momentum(5, 90), "momentum"),
        ("momentum top5 (M,30d)", momentum(5, 30, "M"), "momentum"),
        ("momentum top3 + regime", momentum(3, 30, "W", regime=True), "momentum"),
        ("momentum top5 + regime", momentum(5, 30, "W", regime=True), "momentum"),
        ("RSI(14) BTC 30/70", rsi_strat("BTC"), "mean-rev"),
        ("buy-the-dip BTC (-15%,20d)", buydip("BTC"), "mean-rev"),
        ("fear&greed contrarian BTC", fng_contra("BTC"), "contrarian"),
        ("fear&greed contrarian basket", fng_contra(basket=True), "contrarian"),
        ("vol-target BTC (60%)", voltarget("BTC"), "vol"),
        ("low-vol basket top5 (W)", lowvol(5), "vol"),
        ("combo: mom+regime+voltarget", combo_mom_regime_vol(), "combo"),
    ]

    rows = []
    for label, w, fam in STRATS:
        daily, turn, invested = to_daily(w, rets)
        t_full, apr, mdd, shp = perf(daily)
        _, _, _, shp_is = perf(daily.iloc[:split])
        _, _, _, shp_oos = perf(daily.iloc[split:])
        years = (idx[-1] - idx[0]).days / 365.25
        rows.append({
            "label": label, "family": fam,
            "total": t_full, "apr": apr, "mdd": mdd, "sharpe": shp,
            "sharpe_is": shp_is, "sharpe_oos": shp_oos,
            "trades_yr": (turn > 1e-6).sum() / years,
            "in_mkt": float((invested > 0.01).mean()),
        })

    rows.sort(key=lambda r: (r["sharpe_oos"] if not np.isnan(r["sharpe_oos"]) else -9), reverse=True)

    print(f"panel: {len(cols)} assets, {idx[0].date()} -> {idx[-1].date()}, {n} days")
    print(f"IS/OOS split at {idx[split].date()}  (ranked by out-of-sample Sharpe)\n")
    print(f"  {'#':>2} {'strategy':32s} {'ret':>8s} {'APR':>7s} {'maxDD':>7s} {'Shrp':>6s} {'IS':>6s} {'OOS':>6s} {'t/yr':>5s}")
    for i, r in enumerate(rows, 1):
        print(f"  {i:>2} {r['label']:32s} {r['total']*100:7.0f}% {r['apr']*100:6.0f}% {r['mdd']*100:6.0f}% "
              f"{r['sharpe']:6.2f} {r['sharpe_is']:6.2f} {r['sharpe_oos']:6.2f} {r['trades_yr']:5.0f}")

    # family robustness: median OOS Sharpe per family (is the EDGE consistent, not one lucky config?)
    fams = {}
    for r in rows:
        fams.setdefault(r["family"], []).append(r["sharpe_oos"])
    print("\n  family median OOS Sharpe (robustness of the edge, not one lucky config):")
    for f, v in sorted(fams.items(), key=lambda kv: -np.nanmedian(kv[1])):
        print(f"    {f:12s} {np.nanmedian(v):5.2f}   (n={len(v)})")
    print("\n  reference: delta-neutral funding carry 1x ~ +19% / 5.3% APR / -0.35% maxDD / Sharpe ~25 (market-neutral)")

    with open(OUT, "w") as fh:
        json.dump({"split": str(idx[split].date()), "n_strategies": len(rows), "rows": [
            {k: (None if isinstance(v, float) and np.isnan(v) else round(v, 4) if isinstance(v, float) else v)
             for k, v in r.items()} for r in rows]}, fh, separators=(",", ":"))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
