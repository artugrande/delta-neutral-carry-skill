# Trend Regime — a CoinMarketCap Strategy Skill

> A CoinMarketCap Agent Skill that follows BTC's trend: **hold BTC while price is above
> its moving average, move to stablecoins when it drops below.** It rides the uptrends and
> sits out the deep drawdowns.
>
> Built for **BNB HACK: AI Trading Agent Edition** — Track 2 (Strategy Skills).

**🌐 Live overview → [trend-regime.vercel.app](https://trend-regime.vercel.app)**

## The idea in one line

Compare BTC's price to its moving average. Above it → the trend is up, **hold BTC**. Below
it → the trend has turned, **hold stablecoins**. One rule, two states. No prediction, no
shorting, no leverage.

## Chosen by research, not by guess

We backtested **27 strategies across 7 families** on the same data (daily, 2023–2026, 16
coins, realistic turnover costs), split into in-sample / out-of-sample halves so a strategy
has to work on data it never saw. **Trend-following won as a whole family** — median
out-of-sample Sharpe **2.15**, far ahead of momentum (0.44), volatility (0.43), passive
(0.18), contrarian (0.01) and mean-reversion (−0.38). The "exciting" strategies decayed
out-of-sample (a Fear & Greed contrarian went 2.09 → 0.02); mean-reversion lost money.
Full method + table in [`backtest.md`](skills/trend-regime/references/backtest.md).

## Results — trend-following BTC vs buy & hold (2023–2026)

| Setting | Return (3.4y) | APR | Max DD | Sharpe (OOS) |
|---------|--------------:|----:|-------:|-------------:|
| Trend BTC · 50-day | +2193% | 150% | −15% | 3.22 |
| **Trend BTC · 100-day (default)** | **+872%** | **94%** | **−17%** | **2.27** |
| Trend BTC · 200-day | +471% | 66% | −21% | 1.60 |
| *buy & hold BTC* | +265% | 46% | **−51%** | 0.23 |

> **Read this honestly:** 2023–2026 was net bullish, which inflates every APR here — the
> headline returns will not repeat. The durable, repeatable edge is the **drawdown cut**
> (roughly a third of buy-and-hold's) and the **out-of-sample Sharpe** (which held *above*
> its in-sample value — the opposite of overfitting). Judge it on risk-adjusted terms.

## How the skill works

A 2-state machine the agent runs on live CMC data:

1. **Read** — BTC price (`get_crypto_quotes_latest`) and its moving average
   (`get_crypto_technical_analysis`); Fear & Greed (`get_global_metrics_latest`) for context.
2. **Decide** — `price > MA → RISK-ON` (hold BTC); `price < MA → RISK-OFF` (hold cash); a
   small dead-band around the MA prevents whipsaw flips.
3. **Report** — the regime, the position, and the exact MA price level that flips it.

The one real parameter is the MA window (default **100-day**; 50-day is more active, 200-day
calmer). Everything else is fixed, so the strategy is deterministic and backtestable.

## Install (Claude Desktop / any Claude-skill host)

```bash
cp -r skills/trend-regime /path/to/your/skills/directory/
```

Then connect the CoinMarketCap MCP (get a key at https://pro.coinmarketcap.com/login):

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

Ask: *"Is BTC above its trend right now?"* or `/trend-regime`.

## Reproduce the research

```bash
python -m venv .venv && ./.venv/bin/pip install pandas numpy requests
./.venv/bin/python backtest/research_strategies.py   # the full 27-strategy sweep, IS/OOS
./.venv/bin/python backtest/compare_strategies.py    # head-to-head shortlist
```

All data is fetched free, no API key (Binance daily klines + alternative.me Fear & Greed),
and cached after the first run.

## Repo structure

```
skills/trend-regime/
  SKILL.md                     the strategy as deterministic rules (the deliverable)
  references/
    backtest.md                the 27-strategy sweep, IS/OOS split, and results
    data-sources.md            exactly which CMC reads the skill uses
backtest/
  research_strategies.py       27-strategy sweep with in-sample / out-of-sample split
  compare_strategies.py        head-to-head comparison
  make_trend_data.py           exports the landing's chart data
site/                          the live overview at trend-regime.vercel.app
```

## Honest limits

Trend-following **whipsaws** in choppy markets — shaken out low, bought back high. It always
lags the exact top and bottom. The backtest uses daily Binance data with costs applied, but
live slippage, gas, and timing differ. The 2023–2026 window was bullish, which flatters any
long/trend strategy. It is **directional** (full BTC price risk when RISK-ON) — it shrinks
drawdowns versus holding, it does not remove them. Full caveats in
[`backtest.md`](skills/trend-regime/references/backtest.md).

---

Built with CoinMarketCap data. MIT licensed.
