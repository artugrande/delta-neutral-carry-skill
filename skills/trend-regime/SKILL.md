---
name: trend-regime
description: |
  A trend-following skill for the major crypto assets, driven by CoinMarketCap data.
  For each major (BTC, ETH, BNB, SOL) it compares price to a moving average and holds
  the coin while it trends up, rotating that slice to stablecoins while it trends down —
  an equal-weight basket of whatever is currently trending. The goal is to capture the
  large uptrends and sit out the deep drawdowns: more return than buy-and-hold with a
  fraction of the max drawdown, diversified across coins.
  Use when users ask about trend-following, moving-average / regime strategies, risk-
  managed crypto exposure, "which coins should I hold vs cash", or how to avoid the big
  crypto crashes.
  Trigger: "trend following", "trend regime", "moving average strategy", "which majors
  are trending", "risk on risk off", "avoid the crash", "/trend-regime"
license: MIT
compatibility: ">=1.0.0"
user-invocable: true
allowed-tools:
  - mcp__cmc-mcp__get_crypto_quotes_latest
  - mcp__cmc-mcp__get_crypto_technical_analysis
  - mcp__cmc-mcp__get_global_metrics_latest
---

# Trend Regime — Trend-Following Majors Skill

Hold each major coin while it trends up, hold stablecoins while it trends down. For every
asset in the basket the signal is one comparison: **is price above or below its moving
average?** Above = trend up, hold that coin. Below = trend turned, rotate that slice to
stablecoins. The portfolio is an equal weight across whatever majors are currently above
their average; the rest sits in cash. The skill never calls the exact top or bottom — it
keeps you in the coins that are working and out of the ones that aren't, which is what
compounds over time.

This skill does **not** execute trades. It reads live CMC data and outputs, per asset,
`RISK-ON → hold` or `RISK-OFF → cash`, the resulting equal-weight allocation, plus the
exact price level that flips each. Every decision follows the explicit rule below, so the
strategy is deterministic and backtestable.

## Why this strategy (the research)

It was chosen, not assumed. We backtested **27 strategies across 7 families** on the
same data (daily, 2023–2026, 16 liquid coins, realistic turnover costs) and split the
timeline into in-sample / out-of-sample halves so a strategy has to work on data it
never saw. Results (`references/backtest.md`):

- **Trend-following wins as a whole family** — median out-of-sample Sharpe **2.15**,
  ahead of momentum (0.44), volatility (0.43), passive (0.18), contrarian (0.01) and
  mean-reversion (−0.38). It is not one lucky parameter; every trend config held up.
- The "exciting" strategies decayed out-of-sample: a Fear & Greed contrarian went from
  Sharpe 2.09 in-sample to 0.02 out-of-sample; cross-sectional momentum 1.23 → 0.21.
  Mean-reversion lost money outright.
- Trend-following on BTC (100-day MA) returned **far more than buy-and-hold with a
  fraction of the drawdown** (−17% vs −51%), and its out-of-sample Sharpe (2.27) held
  above its in-sample Sharpe — the opposite of overfitting. **Diversifying the rule across
  the majors (BTC/ETH/BNB/SOL)** lifted out-of-sample Sharpe further to **2.53** at a
  similar drawdown — that is the final strategy.

Trend-following is also the most robust documented anomaly across all asset classes, so
the edge has decades of out-of-crypto evidence behind it, not just this window.

## Prerequisites

Verify the CMC MCP tools are available. If they fail, ask the user to configure the MCP:

```json
{
  "mcpServers": {
    "cmc-mcp": {
      "url": "https://mcp.coinmarketcap.com/mcp",
      "headers": { "X-CMC-MCP-API-KEY": "your-api-key" }
    }
  }
}
```

Get an API key at https://pro.coinmarketcap.com/login

## Strategy Parameters

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `ASSETS` | BTC, ETH, BNB, SOL | Equal-weight basket of liquid majors; each followed independently |
| `MA_WINDOW` | 100 days | Moving-average lookback. Smaller = more active (50d); larger = calmer (200d) |
| `BUFFER` | 1.0% | Dead-band around each MA to avoid flip-flopping on tiny crossings (see Step 2) |
| `CASH` | stablecoins | Where each non-trending slice sits (USDT / USDC) |

> The `MA_WINDOW` is the one real knob and it sets the tempo, not the direction of the
> edge — the trend family worked at 50, 100, 150 and 200 days. Default **100-day** is a
> robust middle (basket out-of-sample Sharpe **2.53**, ~55 rotations/yr across the four
> coins). Use **50-day** for a more active, higher-turnover variant, **200-day** for the
> calmest. Do not over-tune it.

## Decision Workflow

A per-coin 2-state machine — each major is **RISK-ON** (held) or **RISK-OFF** (its slice in
cash) — combined into one equal-weight book. Most days nothing changes; each coin only
flips a handful of times a year.

### Step 1: Read the trend, for each major

For each asset in `ASSETS` (BTC, ETH, BNB, SOL):
- `get_crypto_quotes_latest` → the coin's current price.
- `get_crypto_technical_analysis` → its `MA_WINDOW`-day moving average and trend read.
- Compute its gap: `gap% = (price − MA) / MA × 100`.

`get_global_metrics_latest` → Fear & Greed Index, for context in the report only (it does
**not** change the decision — the price-vs-MA comparison per coin is the entire rule).

### Step 2: Apply the rule per coin, then equal-weight

Classify each major:
- `gap% ≥ +BUFFER` → **RISK-ON**: this coin is trending, hold it.
- `gap% ≤ −BUFFER` → **RISK-OFF**: this coin's slice goes to stablecoins.
- within ±`BUFFER` of the MA → **keep its current state** (do not flip).

Then size the book: **equal-weight across the RISK-ON coins**, remainder in stablecoins.
(2 of 4 trending → 50% in those two, 50% cash. 0 of 4 → 100% cash. 4 of 4 → 25% each.)

The `BUFFER` dead-band is deliberate: it stops a coin's slice from whipsawing every time
price brushes its average. Do not set `BUFFER` to zero "to be precise" — that maximizes
turnover, which the backtest punishes.

### Step 3: Report

Give the per-coin regime, the resulting allocation, and for each coin the **single
trigger** that flips its slice — the exact MA price level. Call out any coin that flipped
since the prior run (rotate that slice in or out). Always make the actions and triggers
explicit, so the recommendation is auditable and rule-bound.

## Output Structure

```
## Trend Regime — Recommendation (<timestamp>)

Basket: BTC, ETH, BNB, SOL | MA window: 100-day
Context: Fear & Greed XX (<label>)

| Coin | Price | 100-day MA | Gap | Regime |
|------|------:|-----------:|----:|--------|
| BTC  | $XX,XXX | $XX,XXX | <+/-X.X%> | <RISK-ON / RISK-OFF> |
| ETH  | $X,XXX  | $X,XXX  | <+/-X.X%> | <RISK-ON / RISK-OFF> |
| BNB  | $XXX    | $XXX    | <+/-X.X%> | <RISK-ON / RISK-OFF> |
| SOL  | $XXX    | $XXX    | <+/-X.X%> | <RISK-ON / RISK-OFF> |

### Allocation
- <e.g. 25% BTC · 25% ETH · 50% stablecoins>  (equal-weight across the RISK-ON coins)
- Per-coin trigger: <COIN goes RISK-OFF if it closes below $XX,XXX (its MA)>

### Changes since last run
<which coins flipped, if any — rotate those slices; otherwise "no change">
```

## Handling Tool Failures

- `get_crypto_technical_analysis` fails: this is the core signal. Retry once; if it still
  fails, do NOT guess the trend — fall back to comparing the latest price against a MA you
  reconstruct from recent quotes if available, otherwise state that no recommendation can
  be made safely.
- `get_crypto_quotes_latest` fails: you cannot size the gap; report the last known regime
  and flag that the price read is stale.
- `get_global_metrics_latest` fails: proceed — Fear & Greed is context only and does not
  change the decision. Just omit it from the report.

## Notes & Honest Caveats

- **Whipsaw is the real cost.** In choppy, directionless markets the price crosses its MA
  repeatedly — the skill gets shaken out low and buys back high, bleeding small losses.
  The `BUFFER` dead-band and a longer `MA_WINDOW` reduce but never eliminate this.
- **The backtest window (2023–2026) was net bullish**, which flatters any long/trend
  strategy. The headline returns will not repeat. The durable, repeatable edge is the
  **drawdown reduction** and the **out-of-sample** Sharpe — sell those, not the APR.
- This is **directional**: you carry full price risk on whichever coins are RISK-ON. The
  basket and the trend rule cut the depth and duration of drawdowns versus buy-and-hold;
  they do not remove them, and the coins are correlated, so they can fall together.
- **No leverage by default.** Leverage multiplies the whipsaw losses and adds liquidation
  risk a daily backtest cannot see. Keep it off unless you fully understand that.
- Judge the strategy on **risk-adjusted** terms (out-of-sample Sharpe, max drawdown), not
  raw return. Raw return in a bull market mostly measures the bull market.
