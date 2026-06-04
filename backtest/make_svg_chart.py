#!/usr/bin/env python3
"""Render the backtest equity curve as a crisp, self-contained SVG (brand-themed).

Dual independent y-axes (like the original matplotlib chart) so the low-volatility
strategy is the visual hero:
  - LEFT  axis: BTC price in USD (grey line)         -> shows the chaos
  - RIGHT axis: strategy equity, start = 1.0 (green) -> shows the smooth climb

Reads backtest/output/equity_curve.csv, downsamples, emits site/equity_curve.svg.
"""
import csv, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "backtest", "output", "equity_curve.csv")
OUT = os.path.join(ROOT, "site", "equity_curve.svg")

rows = []
with open(CSV) as f:
    for r in csv.DictReader(f):
        rows.append(r)

eq0 = float(rows[0]["equity"])
strat = [float(r["equity"]) / eq0 for r in rows]   # equity, normalized to start = 1.0
price = [float(r["price"]) for r in rows]           # BTC price in USD
years = [r["date"][:4] for r in rows]

N = len(rows)
STEP = max(1, N // 240)
idx = list(range(0, N, STEP))
if idx[-1] != N - 1:
    idx.append(N - 1)

# ---- geometry ----
W, H = 1000.0, 470.0
PL, PR, PT, PB = 88.0, 92.0, 56.0, 46.0
PW, PH = W - PL - PR, H - PT - PB

# left axis (BTC, USD) and right axis (strategy equity) — each linear, own range
blo, bhi = 15000.0, 130000.0
bticks = [20000, 40000, 60000, 80000, 100000, 120000]
elo, ehi = 1.0, 1.205
eticks = [1.00, 1.05, 1.10, 1.15, 1.20]

def X(i):
    return PL + (i / (N - 1)) * PW

def Yb(v):  # BTC price -> y
    return PT + (1 - (v - blo) / (bhi - blo)) * PH

def Ye(v):  # strategy equity -> y
    return PT + (1 - (v - elo) / (ehi - elo)) * PH

def poly(series, Y):
    return " ".join(f"{X(i):.1f},{Y(series[i]):.1f}" for i in idx)

btc_pts = poly(price, Yb)
strat_pts = poly(strat, Ye)

# gradient area under the (hero) strategy line, down to the equity baseline
base_y = Ye(elo)
area = f"M{X(idx[0]):.1f},{base_y:.1f} L" + strat_pts.replace(" ", " L") + f" L{X(idx[-1]):.1f},{base_y:.1f} Z"

# gridlines aligned to the LEFT (BTC) axis
grid = "".join(
    f'<line x1="{PL:.1f}" y1="{Yb(v):.1f}" x2="{W-PR:.1f}" y2="{Yb(v):.1f}" class="grid"/>'
    for v in bticks
)
# left tick labels (grey, BTC) — show as "20k".."120k"
blabels = "".join(
    f'<text x="{PL-12:.1f}" y="{Yb(v)+4:.1f}" class="ylab btc-ax" text-anchor="end">{int(v/1000)}k</text>'
    for v in bticks
)
# right tick labels (green, equity)
elabels = "".join(
    f'<text x="{W-PR+12:.1f}" y="{Ye(v)+4:.1f}" class="ylab strat-ax" text-anchor="start">{v:.2f}</text>'
    for v in eticks
)
# x ticks: first occurrence of each year
xticks, seen = "", set()
for i, yr in enumerate(years):
    if yr not in seen:
        seen.add(yr)
        xticks += f'<text x="{X(i):.1f}" y="{H-20:.1f}" class="xlab" text-anchor="middle">{yr}</text>'

# endpoint markers + value tags
sx, sy = X(N - 1), Ye(strat[-1])
bx, by = X(N - 1), Yb(price[-1])
strat_end = f"+{(strat[-1]-1)*100:.0f}%"
btc_end = f"+{(price[-1]/price[0]-1)*100:.0f}%"

# axis titles (rotated) — make the dual scale explicit, so it can't read as misleading
left_title = f'<text x="20" y="{PT+PH/2:.1f}" class="axtitle btc-ax" text-anchor="middle" transform="rotate(-90 20 {PT+PH/2:.1f})">BTC price (USD)</text>'
right_title = f'<text x="{W-20:.1f}" y="{PT+PH/2:.1f}" class="axtitle strat-ax" text-anchor="middle" transform="rotate(90 {W-20:.1f} {PT+PH/2:.1f})">Strategy equity (start = 1.0)</text>'

svg = f'''<svg viewBox="0 0 {W:.0f} {H:.0f}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Delta-neutral carry: flat rising strategy equity vs BTC price">
  <defs>
    <linearGradient id="stratFill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#4ade80" stop-opacity="0.22"/>
      <stop offset="100%" stop-color="#4ade80" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <style>
    .grid {{ stroke:#171717; stroke-width:1; }}
    .ylab {{ font-family:'Space Mono', monospace; font-size:13px; }}
    .xlab {{ font-family:'Space Mono', monospace; font-size:13px; fill:#5a5a5a; }}
    .btc-ax {{ fill:#7a7a7a; }}
    .strat-ax {{ fill:#4ade80; }}
    .axtitle {{ font-family:'Space Grotesk', sans-serif; font-size:13px; }}
    .btc  {{ fill:none; stroke:#6a6a6a; stroke-width:1.6; stroke-linejoin:round; stroke-linecap:round; }}
    .strat {{ fill:none; stroke:#4ade80; stroke-width:3.2; stroke-linejoin:round; stroke-linecap:round; }}
    .lgd {{ font-family:'Space Grotesk', sans-serif; font-size:14px; }}
    .tag {{ font-family:'Space Mono', monospace; font-size:13px; font-weight:700; }}
    .title {{ font-family:'Space Grotesk', sans-serif; font-size:17px; font-weight:600; fill:#ededed; }}
  </style>
  <text x="{W/2:.0f}" y="30" class="title" text-anchor="middle">Flat, rising PnL through BTC&#39;s chaos</text>
  {grid}
  {blabels}{elabels}{xticks}
  {left_title}{right_title}
  <path d="{area}" fill="url(#stratFill)"/>
  <polyline class="btc" points="{btc_pts}"/>
  <polyline class="strat" points="{strat_pts}"/>
  <circle cx="{bx:.1f}" cy="{by:.1f}" r="3.5" fill="#6a6a6a"/>
  <circle cx="{sx:.1f}" cy="{sy:.1f}" r="4.5" fill="#4ade80"/>
  <text x="{bx-10:.1f}" y="{by+18:.1f}" class="tag" fill="#8a8a8a" text-anchor="end">BTC {btc_end}</text>
  <text x="{sx-10:.1f}" y="{sy-12:.1f}" class="tag" fill="#4ade80" text-anchor="end">Strategy {strat_end}</text>
  <g transform="translate({PL+8:.0f},{PT+4:.0f})">
    <line x1="0" y1="0" x2="24" y2="0" class="strat"/>
    <text x="32" y="5" class="lgd" fill="#ededed">This skill — delta-neutral carry</text>
    <line x1="0" y1="23" x2="24" y2="23" class="btc"/>
    <text x="32" y="28" class="lgd" fill="#8a8a8a">BTC buy &amp; hold (price)</text>
  </g>
</svg>'''

with open(OUT, "w") as f:
    f.write(svg)

print(f"wrote {OUT} ({len(svg)} bytes, {len(idx)} pts)")
print(f"strategy {strat[-1]:.4f}x ({strat_end}); btc end ${price[-1]:,.0f} ({btc_end}); btc peak ${max(price):,.0f}")
