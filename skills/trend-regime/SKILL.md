---
name: trend-regime
description: |
  A trend-following BTC strategy skill driven by CoinMarketCap data. It reads BTC's
  price relative to its moving average and decides a single regime: hold BTC while
  price is above the average (uptrend), move to stablecoins while it is below
  (downtrend). The goal is to capture the large uptrends and sit out the deep
  drawdowns — more return than buy-and-hold with a fraction of the max drawdown.
  Use when users ask about trend-following, moving-average / regime strategies,
  "when should I hold BTC vs cash", risk-managed BTC exposure, or how to avoid the
  big crypto crashes.
  Trigger: "trend following", "trend regime", "moving average strategy", "when to
  hold BTC", "risk on risk off", "avoid the crash", "/trend-regime"
license: MIT
compatibility: ">=1.0.0"
user-invocable: true
allowed-tools:
  - mcp__cmc-mcp__get_crypto_quotes_latest
  - mcp__cmc-mcp__get_crypto_technical_analysis
  - mcp__cmc-mcp__get_global_metrics_latest
---

# Trend Regime — Trend-Following BTC Skill

Hold BTC while it trends up, hold stablecoins while it trends down. The signal is a
single comparison: **is BTC's price above or below its moving average?** Above = the
trend is up, stay long BTC and ride it. Below = the trend has turned, step aside to
stablecoins. The skill never tries to call the exact top or bottom — it keeps you in
for the long uptrends and out for the deep drawdowns, which is what compounds over time.

This skill does **not** execute trades. It reads live CMC data and outputs one of two
states — `RISK-ON → hold BTC` or `RISK-OFF → hold stablecoins` — plus the exact price
level that flips it. Every decision follows the explicit rule below, so the strategy is
deterministic and backtestable.

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
- Trend-following BTC (100-day MA) returned **far more than buy-and-hold with about a
  third of the drawdown** (−17% vs −51%), and its out-of-sample Sharpe (2.27) held
  above its in-sample Sharpe — the opposite of overfitting.

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
| `ASSET` | BTC (id 1) | The trend instrument — deepest liquidity, cleanest trend |
| `MA_WINDOW` | 100 days | Moving-average lookback. Smaller = more active (50d); larger = calmer (200d) |
| `BUFFER` | 1.0% | Dead-band around the MA to avoid flip-flopping on tiny crossings (see Step 2) |
| `CASH` | stablecoins | Where capital sits when RISK-OFF (USDT / USDC) |

> The `MA_WINDOW` is the one real knob and it sets the tempo, not the direction of the
> edge — the trend family worked at 50, 100, 150 and 200 days. Default **100-day** is a
> robust middle (out-of-sample Sharpe 2.27). Use **50-day** for a more active, higher-
> turnover variant (~21 trades/yr), **200-day** for the calmest. Do not over-tune it.

## Decision Workflow

A 2-state machine: **HOLD-BTC** (RISK-ON) and **HOLD-CASH** (RISK-OFF). Most days nothing
changes — the regime only flips a handful of times a year.

### Step 1: Read the trend

- `get_crypto_quotes_latest` with id="1" → current BTC price.
- `get_crypto_technical_analysis` for BTC → the moving average(s) and trend read. Use
  the `MA_WINDOW`-day moving average (or the nearest CMC exposes). This is the signal.
- `get_global_metrics_latest` → Fear & Greed Index, for context in the report (it does
  **not** change the decision — the price-vs-MA comparison is the only rule).

Compute the gap: `gap% = (price − MA) / MA × 100`.

### Step 2: Apply the rule (with a dead-band)

- If `gap% ≥ +BUFFER` → **RISK-ON**: hold BTC.
- If `gap% ≤ −BUFFER` → **RISK-OFF**: hold stablecoins.
- If price is within ±`BUFFER` of the MA → **HOLD the current state** (do not flip).

The `BUFFER` dead-band is deliberate: it stops the position from whipsawing every time
price brushes the average. Crossing it cleanly is what triggers a rotation. Do not set
`BUFFER` to zero "to be precise" — that maximizes turnover, which the backtest punishes.

### Step 3: Report

State the regime, the position to hold, and the **single trigger** that flips it — the
exact MA price level. On a flip from the prior state, say so explicitly (rotate BTC ↔
stablecoins once). Always make the action and its trigger explicit, so the
recommendation is auditable and rule-bound.

## Output Structure

```
## Trend Regime — Recommendation (<timestamp>)

Asset: BTC | MA window: 100-day
BTC price: $XX,XXX | 100-day MA: $XX,XXX | gap: <+/-X.X%>
Context: Fear & Greed XX (<label>)

### Regime: <RISK-ON / RISK-OFF>
### Action: <HOLD BTC / MOVE TO STABLECOINS / NO CHANGE>
- Position: <100% BTC  /  100% stablecoins>
- Trigger to flip: <RISK-OFF if BTC closes below $XX,XXX (the MA); else hold>

### Why
<1-2 lines: price vs its MA, which side of the line, and that the rule says hold/flip>
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
- This is **directional**: when RISK-ON you carry full BTC price risk. It cuts the depth
  and duration of drawdowns versus buy-and-hold; it does not remove them.
- **No leverage by default.** Leverage multiplies the whipsaw losses and adds liquidation
  risk a daily backtest cannot see. Keep it off unless you fully understand that.
- Judge the strategy on **risk-adjusted** terms (out-of-sample Sharpe, max drawdown), not
  raw return. Raw return in a bull market mostly measures the bull market.
