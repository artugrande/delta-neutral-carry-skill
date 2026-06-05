---
name: delta-neutral-carry
description: |
  Generates a regime-driven, delta-neutral funding-carry strategy from CoinMarketCap data.
  It reads the market-wide funding rate (the price longs pay shorts on perpetuals) plus
  market regime, and decides when to run a market-neutral carry (long spot + short perp) to
  harvest that funding, versus when to sit in stablecoins. Market price risk is hedged out;
  the return is the funding.
  Use when users ask how to earn yield without taking price risk, about funding-rate carry,
  delta-neutral / basis trades, or "make money while I sleep" on BNB Chain / BSC.
  Trigger: "funding carry", "delta neutral", "basis trade", "market neutral yield",
  "funding rate strategy", "/delta-neutral-carry"
license: MIT
compatibility: ">=1.0.0"
user-invocable: true
allowed-tools:
  - mcp__cmc-mcp__get_global_crypto_derivatives_metrics
  - mcp__cmc-mcp__get_global_metrics_latest
  - mcp__cmc-mcp__get_crypto_quotes_latest
---

# Delta-Neutral Funding-Carry Skill (regime-driven)

Harvest perpetual funding while staying market-neutral. Hold an asset spot (long) and short
the same notional in a perpetual future: price moves cancel (delta ≈ 0), so the only return
left is the **funding rate** longs pay shorts. When the market pays well to be short funding,
you collect it; when funding dries up, flips negative, or the market gets dangerous, you sit
in stablecoins.

CoinMarketCap exposes funding as a **market-wide aggregate** (not per-asset — see
`references/data-sources.md`). This skill embraces that: it treats aggregate funding as a
*regime signal* and runs the carry on the single most-liquid leg (BTC), rather than chasing
per-asset funding it cannot see. Simpler, more robust, fully CMC-native.

**Backtest-validated core rule: minimize turnover.** A 3.4-year backtest (see
`references/backtest.md`) showed the dominant cost is transaction friction. Strategies that
toggle in/out on small funding moves churned 400+ trades and *lost* money (Sharpe < 0).
Strategies that held the carry continuously and only exited on sustained, deeply-negative
funding made +19% with a max drawdown of −0.3% and a Sharpe of ~25, over 2 trades. So the
strategy is **not** "time the funding" — it is "hold the carry and only step aside in a
genuinely adverse funding regime."

This skill does **not** execute trades. It reads live CMC data and outputs a concrete,
rule-based action a user (or a downstream execution agent) can act on. Every decision
follows the explicit rules below, so the strategy is deterministic and backtestable.

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
| `CARRY_ASSET` | BTC (id 1) | Single carry leg — deepest perp liquidity on BSC (ApolloX) |
| `TARGET_DEPLOY` | 70% | Fraction of capital held in the carry while active |
| `REENTRY_APR` | 5% | (Re)enter the carry when aggregate funding APR ≥ this |
| `BREAKER_APR` | −15% | Circuit breaker: exit to stablecoin when funding APR falls below this |
| `MARGIN_BUFFER` | 30% | Stablecoin reserved to defend the short leg's margin |
| `LEVERAGE` | 1× | Optional multiplier on the carry notional (1× / 2× / 5×) — see below |
| `STRESS_GUARD` | off | Live-only safety (see Step 3); off in the return-optimal config |

> Funding is usually quoted per 8h interval. Annualize with: `APR = funding_8h × 3 × 365`.
> The wide gap between `REENTRY_APR` (+5%) and `BREAKER_APR` (−15%) is deliberate hysteresis:
> it keeps the position stable and the trade count near zero. Do not narrow it to "optimize"
> entries — the backtest shows that destroys returns via turnover.

### Leverage (optional, off by default)

Because the position is delta-neutral (no price exposure), the carry notional can be levered
to raise the yield. `LEVERAGE` multiplies the deployed notional on **both** legs equally, so
delta stays ≈ 0. Backtested net (after a ~4% financing cost on the borrowed notional, 3.4-year
window): **1× → 5.3% APR / −0.35% maxDD**, **2× → 7.9% APR / −1.4% maxDD**, **5× → 15.8% APR /
−4.5% maxDD**. Returns and drawdown scale together; risk-adjusted return (Sharpe) actually
*falls* with leverage (≈25 → 19 → 15) because financing is a drag and the curve gets bumpier —
leverage is **not** free yield.

Default is **1× (unlevered)**: the idealized backtest cannot see liquidation risk, which is
the real danger of leverage. A sharp adverse move can liquidate the levered short before the
hedging spot gain can be moved to defend it. If `LEVERAGE > 1`, widen `MARGIN_BUFFER`
accordingly and treat the strategy as materially riskier than the smooth equity curve implies.

## Decision Workflow

This is a 3-state machine: **FLAT** (in stablecoin), **DEPLOYED** (carry on), and the
transitions between them. Most of the time the correct action is **HOLD — do nothing.**

### Step 1: Pull the signal + regime

- `get_global_crypto_derivatives_metrics` → market-wide funding rate, total open interest
  (and its change), liquidations (long vs short bias).
- `get_global_metrics_latest` → Fear & Greed Index, BTC dominance (regime context).
- `get_crypto_quotes_latest` with id="1" → BTC spot price (to size the legs).

Annualize the aggregate funding: `APR = funding_8h × 3 × 365`.

### Step 2: Apply the state machine

- If **FLAT** and `APR ≥ REENTRY_APR` → **ENTER**: deploy `TARGET_DEPLOY` into the BTC carry.
- If **DEPLOYED** and `APR < BREAKER_APR` → **EXIT**: unwind the carry to stablecoin. Funding
  this negative means you'd pay meaningfully to stay short the funding — step aside.
- Otherwise → **HOLD**. This includes brief dips of funding to mildly negative: do NOT exit.
  The cost of toggling out and back (fees + slippage on two legs, twice) exceeds the small
  negative funding you'd avoid. Turnover is the enemy — the backtest is unambiguous on this.

### Step 3: Stress guard (live execution only — off by default)

In a perfect-hedge backtest this guard only costs return, so it is **off** in the
return-optimal config. In *live* trading it addresses a real risk the backtest cannot model:
a violent long-squeeze can liquidate the short leg's margin before the hedging spot gain can
be moved to defend it (the legs don't cross-margin). If you enable it, halve `TARGET_DEPLOY`
when Fear & Greed is in "Extreme Greed" AND open interest is spiking, or when liquidation data
shows a one-sided cascade. Treat this as tail-risk insurance, not a return lever.

### Step 4: Size and report

On **ENTER**, deploy `TARGET_DEPLOY`; spot leg notional = perp short notional (delta-neutral);
reserve `MARGIN_BUFFER` as stablecoin to defend the short leg (the legs live on different
venues — PancakeSwap spot, ApolloX perp — and don't cross-margin). On **HOLD/EXIT**, state the
current position and the single trigger that would change it. Always make the action and its
trigger explicit, so the recommendation is auditable and rule-bound.

## Output Structure

```
## Delta-Neutral Carry — Recommendation (<timestamp>)

State: <FLAT / DEPLOYED> | Aggregate funding APR: XX%
Context: Fear & Greed XX (<label>) | OI 24h <+/-X%>

### Action: <ENTER / HOLD / EXIT→stablecoin>
- BTC carry: deploy XX% of capital
  - Spot leg:  long  $X of BTC (PancakeSwap)
  - Short leg: short $X of BTC-PERP (ApolloX)
- Stablecoin: XX% (incl. margin buffer)
- Trigger to change: EXIT if funding APR < BREAKER_APR (−15%); else HOLD

### Expected
- Funding APR on deployed capital: ~XX%
- Net of est. fees: ~XX% (turnover is near-zero by design)

### Why
<1-2 lines: current funding level, current state, why HOLD/ENTER/EXIT>
```

## Handling Tool Failures

- `get_global_crypto_derivatives_metrics` fails: this is the core signal. Retry once; if it
  still fails, do NOT guess funding — state that no recommendation can be made safely.
- `get_global_metrics_latest` fails: proceed without the stress guard but flag that the
  regime check was skipped and size conservatively (halve the deploy).
- `get_crypto_quotes_latest` fails: you can still output the deploy %/action; mark the spot
  notional as "size at execution price."

## Notes & Honest Caveats

- CMC funding is a **market-wide aggregate**, not per-asset (`references/data-sources.md`).
  This skill is designed around that on purpose — aggregate funding is dominated by BTC/ETH,
  so "aggregate rich → carry BTC" is well aligned, and avoids pretending to a precision the
  data doesn't support.
- This is a **low-variance** strategy: it wins slowly and avoids drawdowns rather than
  chasing upside. Judge it on risk-adjusted return (Sharpe, max drawdown), not raw return.
- Real-world frictions (gas, DEX slippage, margin top-ups, the spot/perp basis) reduce the
  net carry; they should be modeled in the backtest, not assumed away.
