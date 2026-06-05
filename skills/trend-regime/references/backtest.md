# Backtest — how trend-following was chosen

The strategy in `SKILL.md` was not assumed; it survived a deliberate sweep designed to
catch overfitting.

## Method

- **Data:** Binance daily spot klines, 2023-01-01 → 2026-06, 16 liquid coins. Daily
  Fear & Greed from alternative.me. All free, no API key.
- **27 strategies, 7 families:** passive (buy & hold, equal-weight), trend / regime
  (price vs MA, several windows and assets, dual-MA crossovers), cross-sectional momentum
  (top-K rotation, several K / lookbacks / cadences), mean-reversion (RSI, buy-the-dip),
  Fear & Greed contrarian, volatility targeting, low-vol, and combos.
- **Costs:** 10 bps of turnover charged on every weight change; idle capital earns a 4%
  stablecoin yield. So the active strategies are not flattered.
- **In-sample / out-of-sample split:** calibrate on the first half, judge on the unseen
  second half. A strategy only counts if it holds up on data it never saw.

Code: `backtest/compare_strategies.py` (head-to-head) and `backtest/research_strategies.py`
(the full 27-strategy sweep with the IS/OOS split and per-family medians).

## Result — trend wins as a family

Median **out-of-sample Sharpe** per family:

| Family | Median OOS Sharpe |
|--------|------------------:|
| **Trend** | **2.15** |
| Momentum | 0.44 |
| Volatility | 0.43 |
| Passive | 0.18 |
| Contrarian | 0.01 |
| Mean-reversion | −0.38 |

Trend is the only family that holds up across *every* parameter and out of sample. The
"exciting" strategies decayed: a Fear & Greed contrarian went 2.09 (IS) → 0.02 (OOS);
cross-sectional momentum 1.23 → 0.21. Mean-reversion lost money.

## The chosen config — trend-following BTC

| MA window | Return (3.4y) | APR | Max DD | Sharpe (full) | Sharpe (OOS) | Trades/yr |
|-----------|--------------:|----:|-------:|--------------:|-------------:|----------:|
| 50-day    | +2193% | 150% | −15% | 2.92 | 3.22 | 21 |
| **100-day (default)** | **+872%** | **94%** | **−17%** | **2.18** | **2.27** | 15 |
| 200-day   | +471% | 66% | −21% | 1.67 | 1.60 | 9 |
| *buy & hold BTC* | +265% | 46% | −51% | 1.03 | 0.23 | 0 |

Read it honestly: **2023–2026 was net bullish, which inflates every APR here.** The
durable, repeatable findings are (1) trend cut max drawdown to roughly a third of
buy-and-hold's, and (2) its out-of-sample Sharpe held above its in-sample Sharpe — the
opposite of overfitting. Sell the risk-adjusted edge and the drawdown reduction, not the
headline return.

## Honest limits

- Daily close execution with a flat cost model; live slippage, gas, and intraday timing
  differ. Whipsaw in choppy markets is the real recurring cost.
- One out-of-sample split over one ~3.5-year window is not a walk-forward across decades.
  Trend-following has broad cross-asset, multi-decade evidence behind it, which is the
  main reason to trust it beyond this sample.
- Reproduce: `python backtest/research_strategies.py` (data is cached after first run).
