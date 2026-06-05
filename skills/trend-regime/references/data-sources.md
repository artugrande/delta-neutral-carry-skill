# Data sources — what the skill reads

The skill is fully **CoinMarketCap-native**. Live, it needs three reads:

- **`get_crypto_quotes_latest`** (id="1") — current BTC price, to size the gap to the
  moving average.
- **`get_crypto_technical_analysis`** (BTC) — the moving average(s) and trend read. This
  is the signal: is price above or below its `MA_WINDOW`-day average. Use the configured
  window, or the nearest CMC exposes.
- **`get_global_metrics_latest`** — Fear & Greed Index, for context only. It does **not**
  change the decision; the price-vs-MA comparison is the sole rule.

## Backtest data (validation only)

The skill reads CMC at runtime. For historical validation we use **free Binance daily
spot klines** (no API key) as the price history, because CMC does not expose long daily
price history conveniently. The moving average and the trend rule are computed exactly the
way the skill applies them live, so the backtest validates the same logic — it only swaps
the historical price feed.

- Binance spot daily klines (16 liquid coins — BTC plus a basket for the strategy sweep)
- alternative.me Fear & Greed (daily) — used by the contrarian baselines in the sweep

## Execution venue (out of scope for the skill, relevant for live trading)

When RISK-ON, hold BTC (BTCB) spot on **PancakeSwap** (deepest BSC spot liquidity). When
RISK-OFF, hold a stablecoin (USDT / USDC). No perpetuals, no shorting, no leverage — the
strategy is a single long ↔ cash rotation.
