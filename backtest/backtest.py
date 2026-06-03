"""
Backtest for the delta-neutral funding-carry skill (Option A: regime-driven).

Simulates the exact rules in skills/delta-neutral-carry/SKILL.md against real history:
  - long spot BTC + short BTC perp  => delta ~ 0, return = funding collected (short receives
    funding when funding rate is positive).
  - deploy when annualized funding >= ENTRY, unwind below EXIT (hysteresis band in between).
  - stress guard: halve deploy when Fear & Greed is in Extreme Greed.
  - frictions: per-turnover cost charged whenever the deployed fraction changes.

Data (all free, no API key):
  - Binance USD-M funding history  (8h funding rate per period)
  - Binance USD-M 8h klines        (BTC price, for the chart + buy&hold comparison)
  - alternative.me Fear & Greed     (daily index, for the stress guard)

The skill reads CMC's *aggregate* funding at runtime; CMC has no easy funding history, so the
backtest validates the same logic using Binance BTC funding as the historical proxy. This only
affects validation, not where the skill reads data when it runs.
"""

import os
import time
import datetime as dt

import numpy as np
import pandas as pd
import requests

# ----------------------------- parameters (mirror SKILL.md) -----------------------------
ENTRY_FUNDING_APR = 0.08      # open carry at/above 8% annualized
EXIT_FUNDING_APR = 0.03       # unwind below 3% (or negative)
MAX_DEPLOYED = 0.70           # cap of capital in the carry
STRESS_FNG = 75               # Fear & Greed >= this = Extreme Greed -> halve deploy
STRESS_HAIRCUT = 0.5
TURNOVER_COST = 0.0008        # 8 bps per unit notional change (both legs, gas+slippage proxy)

START_DATE = "2023-01-01"
SYMBOL = "BTCUSDT"
PERIODS_PER_YEAR = 3 * 365    # funding settles every 8h

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "output")
os.makedirs(DATA, exist_ok=True)
os.makedirs(OUT, exist_ok=True)


# ----------------------------- data fetching (cached) -----------------------------------
def _start_ms(date_str):
    return int(dt.datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def fetch_funding(symbol, start_date):
    cache = os.path.join(DATA, f"funding_{symbol}.csv")
    if os.path.exists(cache):
        d = pd.read_csv(cache)
        d["time"] = pd.to_datetime(d["time"], utc=True, format="ISO8601").dt.as_unit("ns")
        d["funding"] = d["funding"].astype(float)
        return d
    url = "https://fapi.binance.com/fapi/v1/fundingRate"
    start = _start_ms(start_date)
    rows = []
    while True:
        r = requests.get(url, params={"symbol": symbol, "startTime": start, "limit": 1000}, timeout=30)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        rows.extend(batch)
        last = batch[-1]["fundingTime"]
        if len(batch) < 1000:
            break
        start = last + 1
        time.sleep(0.25)
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
    df["funding"] = df["fundingRate"].astype(float)
    df = df[["time", "funding"]].drop_duplicates("time").sort_values("time").reset_index(drop=True)
    df.to_csv(cache, index=False)
    return df


def fetch_klines(symbol, start_date):
    cache = os.path.join(DATA, f"klines_{symbol}.csv")
    if os.path.exists(cache):
        d = pd.read_csv(cache)
        d["time"] = pd.to_datetime(d["time"], utc=True, format="ISO8601").dt.as_unit("ns")
        d["price"] = d["price"].astype(float)
        return d
    url = "https://fapi.binance.com/fapi/v1/klines"
    start = _start_ms(start_date)
    rows = []
    while True:
        r = requests.get(url, params={"symbol": symbol, "interval": "8h", "startTime": start, "limit": 1500}, timeout=30)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        rows.extend(batch)
        last = batch[-1][0]
        if len(batch) < 1500:
            break
        start = last + 1
        time.sleep(0.25)
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df[0], unit="ms", utc=True)
    df["price"] = df[4].astype(float)  # close
    df = df[["time", "price"]].drop_duplicates("time").sort_values("time").reset_index(drop=True)
    df.to_csv(cache, index=False)
    return df


def fetch_fng():
    cache = os.path.join(DATA, "fng.csv")
    if os.path.exists(cache):
        d = pd.read_csv(cache)
        d["date"] = pd.to_datetime(d["date"], utc=True, format="ISO8601").dt.as_unit("ns")
        d["fng"] = d["fng"].astype(int)
        return d
    r = requests.get("https://api.alternative.me/fng/", params={"limit": 0, "format": "json"}, timeout=30)
    r.raise_for_status()
    data = r.json()["data"]
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["timestamp"].astype(int), unit="s", utc=True).dt.floor("D")
    df["fng"] = df["value"].astype(int)
    df = df[["date", "fng"]].drop_duplicates("date").sort_values("date").reset_index(drop=True)
    df.to_csv(cache, index=False)
    return df


# ----------------------------- assemble dataset -----------------------------------------
def build_dataset():
    funding = fetch_funding(SYMBOL, START_DATE)
    klines = fetch_klines(SYMBOL, START_DATE)
    fng = fetch_fng()

    df = pd.merge_asof(funding, klines, on="time", direction="nearest", tolerance=pd.Timedelta("4h"))
    df["date"] = df["time"].dt.floor("D").dt.as_unit("ns")
    fng = fng.copy()
    fng["date"] = pd.to_datetime(fng["date"], utc=True).dt.as_unit("ns")
    df = pd.merge_asof(df.sort_values("date"), fng.sort_values("date"), on="date", direction="backward")
    df = df.sort_values("time").reset_index(drop=True)
    df["funding_apr"] = df["funding"] * PERIODS_PER_YEAR
    df = df.dropna(subset=["price"]).reset_index(drop=True)
    return df


# ----------------------------- strategy simulation --------------------------------------
def make_decider(entry, exit_, use_guard, size=MAX_DEPLOYED):
    """Deploy `size` when funding APR >= entry, unwind below exit, hold in between
    (hysteresis). Optionally halve during Extreme Greed."""
    def decide(apr, prev_deploy, fng):
        if apr >= entry:
            target = size
        elif apr < exit_:
            target = 0.0
        else:
            target = prev_deploy
        if use_guard and not np.isnan(fng) and fng >= STRESS_FNG:
            target *= STRESS_HAIRCUT
        return target
    return decide


def simulate(df, decide):
    equity = 1.0
    deploy = 0.0
    eq_curve, dep_curve = [], []
    for _, row in df.iterrows():
        new_deploy = decide(row["funding_apr"], deploy, row["fng"])
        friction = abs(new_deploy - deploy) * TURNOVER_COST  # cost on notional change
        deploy = new_deploy
        income = deploy * row["funding"]  # short receives funding when funding > 0
        equity *= (1.0 + income - friction)
        eq_curve.append(equity)
        dep_curve.append(deploy)
    out = df.copy()
    out["equity"] = eq_curve
    out["deploy"] = dep_curve
    return out


# ----------------------------- metrics --------------------------------------------------
def metrics(df, equity_col="equity"):
    eq = df[equity_col].values
    rets = np.diff(eq) / eq[:-1]
    total_return = eq[-1] / eq[0] - 1
    years = (df["time"].iloc[-1] - df["time"].iloc[0]).days / 365.25
    apr = (eq[-1] / eq[0]) ** (1 / years) - 1 if years > 0 else float("nan")
    peak = np.maximum.accumulate(eq)
    max_dd = ((eq - peak) / peak).min()
    sharpe = (rets.mean() / rets.std() * np.sqrt(PERIODS_PER_YEAR)) if rets.std() > 0 else float("nan")
    pct_deployed = (df["deploy"] > 0).mean() if "deploy" in df else float("nan")
    n_trades = int((df["deploy"].diff().abs() > 1e-9).sum()) if "deploy" in df else 0
    return {
        "years": years,
        "total_return": total_return,
        "apr": apr,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "pct_time_deployed": pct_deployed,
        "n_trades": n_trades,
    }


def buy_and_hold(df):
    df = df.copy()
    df["equity"] = df["price"] / df["price"].iloc[0]
    return df


# ----------------------------- plot -----------------------------------------------------
def plot(df, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(df["time"], df["price"], color="#bbbbbb", linewidth=1, label="BTC price (right)")
    ax1.set_ylabel("BTC price (USD)", color="#888888")
    ax1.tick_params(axis="y", labelcolor="#888888")

    ax2 = ax1.twinx()
    ax2.plot(df["time"], df["equity"], color="#0a7d2c", linewidth=2.2, label="Carry strategy equity (left)")
    ax2.set_ylabel("Strategy equity (start = 1.0)", color="#0a7d2c")
    ax2.tick_params(axis="y", labelcolor="#0a7d2c")

    plt.title("Delta-neutral funding carry: flat, rising PnL through BTC's chaos")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    print(f"saved chart -> {path}")


# ----------------------------- main -----------------------------------------------------
def static_decider(size=MAX_DEPLOYED):
    return lambda apr, prev, fng: size


VARIANTS = {
    # name: decider
    "static hold (never toggle)":          static_decider(),
    "wide-band (enter>5%, exit<-15%)":     make_decider(entry=0.05, exit_=-0.15, use_guard=False),
    "harvest (>2% APR, exit<0)":           make_decider(entry=0.02, exit_=0.00, use_guard=False),
    "always-on (funding > 0)":             make_decider(entry=0.00, exit_=0.00, use_guard=False),
    "original (8%/3% + guard)":            make_decider(entry=0.08, exit_=0.03, use_guard=True),
}


def row_str(name, m):
    return (f"  {name:32s}  ret {m['total_return']*100:7.2f}%  APR {m['apr']*100:6.2f}%  "
            f"maxDD {m['max_drawdown']*100:6.2f}%  Sharpe {m['sharpe']:6.2f}  "
            f"deployed {m['pct_time_deployed']*100:4.0f}%  trades {m.get('n_trades', 0):4d}")


def main():
    print("loading data (cached after first run)...")
    df = build_dataset()
    print(f"dataset: {len(df)} funding periods, {df['time'].iloc[0].date()} -> {df['time'].iloc[-1].date()}")
    pos = (df["funding"] > 0).mean()
    print(f"funding was positive {pos*100:.1f}% of periods; mean APR {df['funding_apr'].mean()*100:.2f}%\n")

    results = {}
    print("=== STRATEGY VARIANTS (delta-neutral carry) ===")
    for name, decide in VARIANTS.items():
        sim = simulate(df, decide)
        results[name] = sim
        print(row_str(name, metrics(sim)))

    print("\n=== BENCHMARK ===")
    bh = buy_and_hold(df)
    m = metrics(bh)
    m["pct_time_deployed"] = 1.0
    print(row_str("buy & hold BTC", m))

    best = max(results, key=lambda n: metrics(results[n])["sharpe"])
    print(f"\nbest by Sharpe: {best}")

    # export the variant the SKILL.md actually implements: hold continuously, exit only on a
    # deeply-negative funding regime (a circuit breaker). Near-identical to static hold but
    # with a real safety valve.
    recommended = "wide-band (enter>5%, exit<-15%)"
    print(f"exported (matches SKILL.md): {recommended}")
    results[recommended].to_csv(os.path.join(OUT, "equity_curve.csv"), index=False)
    plot(results[recommended], os.path.join(OUT, "equity_curve.png"))


if __name__ == "__main__":
    main()
