#!/usr/bin/env python3
"""Apples-to-apples comparison of candidate strategies on the SAME daily data
(Binance spot, 2023-01-01 -> now; free, no API key) so we pick the pivot by real
numbers, not vibes.

Strategies (all long / long-cash, realistic turnover costs applied):
  1. Buy & hold BTC                      — benchmark
  2. Equal-weight basket (hold)          — benchmark
  3. Trend / regime BTC (price > MA)     — in BTC when trending up, else cash
  4. Momentum rotation (top-K weekly)    — hold the strongest K coins, rebalance weekly
  5. Momentum + regime filter            — #4, but only when BTC regime is risk-on
  6. Fear & Greed contrarian             — scale BTC by CMC's Fear & Greed index

Metrics: total return, CAGR (APR), max drawdown, Sharpe, trades/yr, % time in market.
Reference: the delta-neutral funding carry (separate 8h backtest) was ~5.3% APR / -0.35% DD.
"""
import os, time, datetime as dt
import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)

START = "2023-01-01"
BASKET = ["BTC", "ETH", "BNB", "XRP", "ADA", "DOGE", "SOL", "MATIC",
          "DOT", "LTC", "LINK", "AVAX", "TRX", "ATOM", "NEAR", "UNI"]
TURNOVER_COST = 0.0010   # 10 bps per unit of weight traded (per side) — gas+slippage proxy
CASH_APR = 0.04          # stablecoin yield while out of the market

def _start_ms(d): return int(dt.datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)

def fetch_daily(sym):
    cache = os.path.join(DATA, f"daily_{sym}USDT.csv")
    if os.path.exists(cache):
        d = pd.read_csv(cache, parse_dates=["date"])
        return d.set_index("date")["close"]
    url = "https://api.binance.com/api/v3/klines"
    start, rows = _start_ms(START), []
    while True:
        r = requests.get(url, params={"symbol": sym + "USDT", "interval": "1d", "startTime": start, "limit": 1000}, timeout=30)
        if r.status_code != 200:
            return None
        batch = r.json()
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < 1000:
            break
        start = batch[-1][0] + 1
        time.sleep(0.2)
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df[0], unit="ms", utc=True).dt.tz_localize(None).dt.floor("D")
    df["close"] = df[4].astype(float)
    df = df[["date", "close"]].drop_duplicates("date").sort_values("date")
    df.to_csv(cache, index=False)
    return df.set_index("date")["close"]

def fetch_fng():
    cache = os.path.join(DATA, "fng.csv")
    d = pd.read_csv(cache)
    d["date"] = pd.to_datetime(d["date"], utc=True).dt.tz_localize(None).dt.floor("D")
    return d.set_index("date")["fng"].astype(float)

def build_panel():
    cols = {}
    for s in BASKET:
        ser = fetch_daily(s)
        if ser is not None and len(ser) > 200:
            cols[s] = ser
    panel = pd.DataFrame(cols).sort_index()
    panel = panel[panel.index >= pd.Timestamp(START)]
    panel = panel.ffill().dropna(how="all")
    return panel

# ---- metrics from a daily weight matrix (rows=days, cols=assets), + cash ----
def run(weights, rets, label):
    # weights[t] applied to rets[t] (rets already shifted: return from t-1 to t)
    w = weights.reindex(rets.index).fillna(0.0)
    invested = w.sum(axis=1).clip(0, 1)
    gross = (w * rets).sum(axis=1)
    cash_w = (1 - invested).clip(lower=0)
    cash_ret = cash_w * (CASH_APR / 365.0)
    # turnover cost: |Δweight| summed across assets, charged on the day of change
    turn = w.diff().abs().sum(axis=1).fillna(0.0)
    cost = turn * TURNOVER_COST
    daily = gross + cash_ret - cost
    eq = (1 + daily).cumprod()
    return metrics(eq, daily, turn, invested, label)

def metrics(eq, daily, turn, invested, label):
    years = (eq.index[-1] - eq.index[0]).days / 365.25
    total = eq.iloc[-1] - 1
    apr = eq.iloc[-1] ** (1 / years) - 1
    peak = eq.cummax()
    mdd = ((eq - peak) / peak).min()
    sharpe = daily.mean() / daily.std() * np.sqrt(365) if daily.std() > 0 else float("nan")
    trades_yr = (turn > 1e-6).sum() / years
    in_mkt = (invested > 0.01).mean()
    return {"label": label, "total": total, "apr": apr, "mdd": mdd, "sharpe": sharpe,
            "trades_yr": trades_yr, "in_mkt": in_mkt}

def weekly_mask(index):
    # True on the first trading day of each ISO week (rebalance day)
    wk = index.to_series().dt.isocalendar().week.astype(int) + index.to_series().dt.year * 100
    return wk.ne(wk.shift()).values

def main():
    panel = build_panel()
    print(f"panel: {panel.shape[1]} assets, {panel.index[0].date()} -> {panel.index[-1].date()} ({len(panel)} days)")
    print("assets:", ", ".join(panel.columns), "\n")
    rets = panel.pct_change().fillna(0.0)
    n = len(panel)
    btc = panel["BTC"]
    btc_ma = btc.rolling(100).mean()
    regime_on = (btc > btc_ma).fillna(False)  # risk-on when BTC above its 100d MA
    fng = fetch_fng().reindex(panel.index).ffill()

    results = []

    # 1. buy & hold BTC
    w = pd.DataFrame(0.0, index=panel.index, columns=panel.columns); w["BTC"] = 1.0
    results.append(run(w, rets, "buy & hold BTC"))

    # 2. equal-weight basket hold
    w = pd.DataFrame(1.0 / panel.shape[1], index=panel.index, columns=panel.columns)
    results.append(run(w, rets, "equal-weight basket (hold)"))

    # 3. trend/regime BTC: in BTC when above 100d MA, else cash
    w = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    w["BTC"] = regime_on.astype(float).values
    results.append(run(w, rets, "trend/regime BTC (100d MA)"))

    # 4. momentum rotation: weekly, top-K by 30d return, equal weight
    K, LB = 5, 30
    mom = panel / panel.shift(LB) - 1
    wk = weekly_mask(panel.index)
    w = pd.DataFrame(0.0, index=panel.index, columns=panel.columns)
    cur = pd.Series(0.0, index=panel.columns)
    for i in range(n):
        if wk[i] and i >= LB:
            top = mom.iloc[i].dropna().sort_values(ascending=False).head(K).index
            cur = pd.Series(0.0, index=panel.columns)
            cur[top] = 1.0 / K
        w.iloc[i] = cur.values
    results.append(run(w, rets, f"momentum top{K} (weekly, {LB}d)"))

    # 5. momentum + regime filter (only hold when BTC regime risk-on)
    w5 = w.mul(regime_on.astype(float).values, axis=0)
    results.append(run(w5, rets, f"momentum top{K} + regime filter"))

    # 6. Fear & Greed contrarian on BTC: full in fear, flat in greed
    fw = pd.Series(0.5, index=panel.index)
    fw[fng <= 25] = 1.0
    fw[fng >= 75] = 0.0
    w = pd.DataFrame(0.0, index=panel.index, columns=panel.columns); w["BTC"] = fw.values
    results.append(run(w, rets, "fear&greed contrarian (BTC)"))

    print(f"  {'strategy':34s} {'return':>9s} {'APR':>8s} {'maxDD':>8s} {'Sharpe':>7s} {'trd/yr':>7s} {'in-mkt':>7s}")
    for m in results:
        print(f"  {m['label']:34s} {m['total']*100:8.1f}% {m['apr']*100:7.1f}% {m['mdd']*100:7.1f}% "
              f"{m['sharpe']:7.2f} {m['trades_yr']:7.0f} {m['in_mkt']*100:6.0f}%")
    print("\n  reference: delta-neutral funding carry 1x  ~ +19.4% total / 5.3% APR / -0.35% maxDD / Sharpe ~25 / 0.6 trd/yr")

if __name__ == "__main__":
    main()
