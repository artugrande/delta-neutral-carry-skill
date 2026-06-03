# Backtest — how the strategy rules were validated

The strategy in `SKILL.md` is not hand-waved; it is what survived a 3.4-year backtest. The
runnable code and data fetchers live in `backtest/backtest.py` (repo root). This file records
the method, the result, and what the backtest does and does not prove.

## Method

- **Window:** 2023-01-01 → 2026-06-03 (3.42 years, 3750 funding periods at 8h each).
- **Funding data:** Binance USD-M `BTCUSDT` funding history (free, no key). Used as the
  historical proxy for CMC's aggregate funding, which has no easy public history. This affects
  *validation only* — at runtime the skill reads CMC, per `data-sources.md`.
- **Price data:** Binance USD-M 8h klines (for the chart and the buy-and-hold benchmark).
- **Regime data:** alternative.me Fear & Greed daily index (for the optional stress guard).
- **PnL model:** delta-neutral, so directional price PnL is assumed hedged to ~0. Each 8h
  period the deployed notional collects `deploy × funding_rate` (the short receives funding
  when funding is positive). A turnover cost of **8 bps per unit notional change** is charged
  whenever the deployed fraction moves (proxy for DEX fees + slippage on both legs).
- **Metrics:** total return, annualized return, max drawdown, Sharpe (annualized with 1095
  8h periods/yr), and trade count (number of deploy changes).

## Result

Funding on BTC was positive **85.9%** of periods (mean **7.41% APR**) over the window.

| Strategy | Return | APR | Max DD | Sharpe | Trades |
|----------|-------:|----:|-------:|-------:|-------:|
| **static hold (never toggle)**            | +19.43% | 5.33% | −0.29% | 26.13 | 0 |
| **wide-band (enter>5%, exit<−15%)** ← skill | +19.35% | 5.31% | −0.35% | 25.48 | 2 |
| harvest (>2% APR, exit<0)                 | −6.51% | −1.95% | −10.08% | −2.92 | 456 |
| always-on (funding>0)                     | −9.44% | −2.86% | −11.93% | −4.07 | 514 |
| original (8%/3% entry + greed guard)      | −6.86% | −2.06% | −8.12% | −3.65 | 416 |
| *benchmark:* buy & hold BTC               | +290.2% | 48.9% | −49.68% | 1.10 | 0 |

## What it proves

1. **Turnover is the dominant cost.** The losing strategies are exactly the ones that toggle
   in/out around the funding zero-line (400–500 trades). The winning ones barely trade (0–2).
   The strategy rule "hold continuously, only exit on a deeply-negative funding regime" falls
   directly out of this — it was *discovered*, not assumed.
2. **The carry is low-variance, not high-return.** ~5% APR with a −0.3% max drawdown and a
   Sharpe of ~25. It must be judged on risk-adjusted terms; buy-and-hold returns far more but
   with a −50% drawdown and Sharpe ~1. Different products for different risk appetites.
3. **The "smart" overlays hurt.** Both the funding-entry threshold and the Extreme-Greed guard
   *reduced* returns as funding-timing rules. The greed guard is retained in `SKILL.md` only as
   an **optional live-execution safety**, off by default, because it protects a liquidation risk
   the backtest's perfect-hedge assumption cannot see.

## What it does NOT prove (honest limits)

- **Perfect hedge assumed.** Real delta-neutral has basis drift, funding-interval timing slip,
  and short-leg liquidation risk if margin isn't actively defended. Net live returns will be
  lower than the ~5% APR shown.
- **Binance funding ≠ ApolloX funding.** Execution is on BSC (ApolloX); its funding and
  liquidity differ from Binance's deep CEX market. The backtest is a proxy, not the venue.
- **One asset, one regime epoch.** BTC, 2023–2026. Funding can stay negative for longer
  stretches in other regimes; the −15% breaker is a guardrail, not a guarantee.
- **Costs are a flat proxy.** 8 bps/turn is an estimate; real gas + slippage vary with size
  and conditions.

## Reproduce

```bash
python -m venv .venv && ./.venv/bin/pip install pandas numpy matplotlib requests
./.venv/bin/python backtest/backtest.py
# outputs: backtest/output/equity_curve.csv and equity_curve.png
```
