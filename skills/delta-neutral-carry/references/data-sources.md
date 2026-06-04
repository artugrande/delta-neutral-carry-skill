# Data Sources — what CMC actually exposes for funding

This skill's design is constrained by what CoinMarketCap actually provides. Documented from
the official CMC skills repo (`coinmarketcap-official/skills-for-ai-agents-by-CoinMarketCap`).

## Funding rate: market-wide aggregate only

The only funding data CMC exposes is **aggregate / market-wide**, via:

- **`get_global_crypto_derivatives_metrics`** (MCP) — returns total open interest (and 24h
  change), market-wide funding rate (positive = longs paying shorts), liquidations (long vs
  short bias), and a futures-vs-perpetuals breakdown.

There is **no per-asset funding rate** in the documented CMC surface:

- `/v1/exchange/market-pairs/latest?category=perpetual` lists perpetual pairs for an exchange
  but its response carries only price, volume, order-book depth, and liquidity — **no funding
  field**.
- No other endpoint or MCP tool in the repo returns a per-symbol or per-venue funding rate.

**Implication:** we cannot rank BTC vs ETH vs BNB by their individual funding using CMC alone.
The skill therefore uses aggregate funding as a *regime signal* and runs the carry on a single
deep-liquidity leg (BTC). This is a deliberate design choice, not a workaround — aggregate
funding is dominated by BTC/ETH, so the signal and the traded leg are well aligned.

> **Verified live (2026-06-04)** against `mcp.coinmarketcap.com`. The `get_global_crypto_derivatives_metrics`
> tool returns a single aggregate `fundingRate` object — e.g.
> `"fundingRate": {"current": "-0.00053135", "percentage_change_24h": "-111.7%", ...}` —
> plus aggregate `perpetuals.openInterest`, `perpetuals.volume`, and `btc_liquidations`.
> There is **no per-asset funding field**, confirming the aggregate-only design. If CMC ever
> adds per-symbol funding, Step 2 can be upgraded to rank assets; until then, aggregate-only.

## Supporting data used

- **`get_global_metrics_latest`** (MCP) — Fear & Greed Index, BTC/ETH dominance, altcoin
  season index. Used for the regime / stress guard.
- **`get_crypto_quotes_latest`** (MCP, id="1") — BTC spot price, to size the legs.

## Execution venues (out of scope for the skill, relevant for the backtest assumptions)

- **Spot leg:** PancakeSwap (deepest BSC spot liquidity).
- **Perp (short) leg:** ApolloX — the largest perpetual DEX on BSC mainnet. (KiloEx runs on
  opBNB / Base, not BSC mainnet.)
- The two legs do not cross-margin, which is why the strategy reserves a stablecoin margin
  buffer to defend the short leg.
