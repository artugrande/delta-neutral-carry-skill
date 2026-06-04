#!/usr/bin/env python3
"""Render the backtest equity curve as a crisp, self-contained SVG (brand-themed).
Reads backtest/output/equity_curve.csv, normalizes both series to "growth of $1",
downsamples, and emits site/equity_curve.svg. No external deps beyond stdlib csv.
"""
import csv, os, math

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(ROOT, "backtest", "output", "equity_curve.csv")
OUT = os.path.join(ROOT, "site", "equity_curve.svg")

rows = []
with open(CSV) as f:
    for r in csv.DictReader(f):
        rows.append(r)

eq0 = float(rows[0]["equity"])
px0 = float(rows[0]["price"])
# normalized "growth of $1"
strat = [float(r["equity"]) / eq0 for r in rows]
btc = [float(r["price"]) / px0 for r in rows]
# year boundaries (for x ticks) from the date column
years = [r["date"][:4] for r in rows]

N = len(rows)
# downsample to ~220 points but keep first & last
STEP = max(1, N // 220)
idx = list(range(0, N, STEP))
if idx[-1] != N - 1:
    idx.append(N - 1)

# ---- geometry ----
W, H = 1000.0, 440.0
PL, PR, PT, PB = 64.0, 24.0, 24.0, 52.0  # padding: left/right/top/bottom
PW, PH = W - PL - PR, H - PT - PB

# log y-scale so the smooth ~1.2x strategy and the ~8x BTC are both readable
ytop = max(max(btc), max(strat)) * 1.08
ylo = 0.85
LT, LB = math.log(ytop), math.log(ylo)

def X(i):
    return PL + (i / (N - 1)) * PW

def Y(v):
    return PT + (1 - (math.log(v) - LB) / (LT - LB)) * PH

def path(series):
    pts = []
    for i in idx:
        pts.append(f"{X(i):.1f},{Y(series[i]):.1f}")
    return " ".join(pts)

strat_pts = path(strat)
btc_pts = path(btc)

# area fill under strategy: same points + close down to baseline
base_y = Y(ylo)
area = f"M{X(idx[0]):.1f},{base_y:.1f} L" + strat_pts.replace(" ", " L") + f" L{X(idx[-1]):.1f},{base_y:.1f} Z"

# y gridlines at clean multiples (log spacing)
gridvals = [v for v in (1, 2, 4, 8) if v <= ytop]
ylines, ylabels = [], []
for v in gridvals:
    y = Y(v)
    ylines.append(f'<line x1="{PL:.1f}" y1="{y:.1f}" x2="{W-PR:.1f}" y2="{y:.1f}" class="grid"/>')
    ylabels.append(f'<text x="{PL-10:.1f}" y="{y+4:.1f}" class="ylab" text-anchor="end">{v}×</text>')

# x ticks at first occurrence of each year
xticks = []
seen = set()
for i, yr in enumerate(years):
    if yr not in seen:
        seen.add(yr)
        x = X(i)
        xticks.append(f'<text x="{x:.1f}" y="{H-22:.1f}" class="xlab" text-anchor="middle">{yr}</text>')

# endpoint markers + value labels
sx, sy = X(N - 1), Y(strat[-1])
bx, by = X(N - 1), Y(btc[-1])
strat_end = f"+{(strat[-1]-1)*100:.0f}%"
btc_end = f"+{(btc[-1]-1)*100:.0f}%"

svg = f'''<svg viewBox="0 0 {W:.0f} {H:.0f}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Backtest: growth of $1, strategy vs BTC buy and hold">
  <defs>
    <linearGradient id="stratFill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#4ade80" stop-opacity="0.28"/>
      <stop offset="100%" stop-color="#4ade80" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <style>
    .grid {{ stroke:#1c1c1c; stroke-width:1; }}
    .ylab, .xlab {{ font-family:'Space Mono', monospace; font-size:13px; fill:#5a5a5a; }}
    .btc  {{ fill:none; stroke:#5a5a5a; stroke-width:2; stroke-linejoin:round; stroke-linecap:round; }}
    .strat {{ fill:none; stroke:#4ade80; stroke-width:2.8; stroke-linejoin:round; stroke-linecap:round; }}
    .lgd {{ font-family:'Space Grotesk', sans-serif; font-size:14px; }}
    .tag {{ font-family:'Space Mono', monospace; font-size:13px; font-weight:700; }}
  </style>
  {''.join(ylines)}
  {''.join(ylabels)}
  {''.join(xticks)}
  <path d="{area}" fill="url(#stratFill)"/>
  <polyline class="btc" points="{btc_pts}"/>
  <polyline class="strat" points="{strat_pts}"/>
  <circle cx="{bx:.1f}" cy="{by:.1f}" r="3.5" fill="#5a5a5a"/>
  <circle cx="{sx:.1f}" cy="{sy:.1f}" r="4" fill="#4ade80"/>
  <text x="{bx-8:.1f}" y="{by-8:.1f}" class="tag" fill="#8a8a8a" text-anchor="end">BTC {btc_end}</text>
  <text x="{sx-8:.1f}" y="{sy+18:.1f}" class="tag" fill="#4ade80" text-anchor="end">Strategy {strat_end}</text>
  <!-- legend -->
  <g transform="translate({PL+6:.0f},{PT+6:.0f})">
    <line x1="0" y1="0" x2="22" y2="0" class="strat"/>
    <text x="30" y="5" class="lgd" fill="#e8e8e8">This skill — delta-neutral carry</text>
    <line x1="0" y1="22" x2="22" y2="22" class="btc"/>
    <text x="30" y="27" class="lgd" fill="#8a8a8a">BTC buy &amp; hold</text>
  </g>
</svg>'''

with open(OUT, "w") as f:
    f.write(svg)

print(f"wrote {OUT} ({len(svg)} bytes, {len(idx)} pts)")
print(f"strategy end {strat[-1]:.4f}x ({strat_end}), btc end {btc[-1]:.4f}x ({btc_end}), ytop {ytop:.2f}, btc peak {max(btc):.2f}x")
