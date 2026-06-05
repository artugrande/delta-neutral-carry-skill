/* Interactive trend chart: reads assets/trend_data.json and draws the
   trend-following BTC strategy (selected MA window: 50/100/200-day) against
   buy & hold BTC. Buttons update the curve, the stat strip, and the table row.
   Growth of $1, log scale. Animates the strategy line on first view. */
(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var host = document.getElementById('chart');
  var fallback = document.getElementById('chartFallback');
  if (!host) return;

  var DATA = null, drawnOnce = false, curMa = 100;

  var W = 1000, H = 460, PL = 60, PR = 26, PT = 44, PB = 42;
  var PW = W - PL - PR, PH = H - PT - PB;
  var YMIN = 0.85, YMAX = 26, LB = Math.log(YMIN), LT = Math.log(YMAX);
  function X(i, n) { return PL + (i / (n - 1)) * PW; }
  function Y(v) { return PT + (1 - (Math.log(v) - LB) / (LT - LB)) * PH; }

  function fmtSigned(v) { return (v < 0 ? '−' : '+') + Math.abs(v * 100).toFixed(v >= 1 ? 0 : 2) + '%'; }
  function fmtApr(v) { return (v < 0 ? '−' : '') + Math.abs(v * 100).toFixed(1) + '%'; }
  function fmtDd(v) { return '−' + Math.abs(v * 100).toFixed(1) + '%'; }

  function winByMa(ma) {
    for (var i = 0; i < DATA.windows.length; i++) if (DATA.windows[i].ma === ma) return DATA.windows[i];
    return DATA.windows[0];
  }
  function points(arr) {
    var n = arr.length, p = '';
    for (var i = 0; i < n; i++) p += (i ? ' ' : '') + X(i, n).toFixed(1) + ',' + Y(arr[i]).toFixed(1);
    return p;
  }

  function buildSVG(ma) {
    var win = winByMa(ma);
    var s = win.series, b = DATA.benchmark.series, n = s.length;
    var stratPts = points(s), btcPts = points(b);
    var baseY = Y(YMIN).toFixed(1);
    var area = 'M' + X(0, n).toFixed(1) + ',' + baseY + ' L' + stratPts.split(' ').join(' L') +
               ' L' + X(n - 1, n).toFixed(1) + ',' + baseY + ' Z';

    var grid = '', ylab = '';
    [1, 2, 5, 10, 20].forEach(function (v) {
      var y = Y(v).toFixed(1);
      grid += '<line x1="' + PL + '" y1="' + y + '" x2="' + (W - PR) + '" y2="' + y + '" class="grid"/>';
      ylab += '<text x="' + (PL - 10) + '" y="' + (Y(v) + 4).toFixed(1) + '" class="ylab" text-anchor="end">' + v + '×</text>';
    });
    var xlab = '';
    DATA.xYears.forEach(function (xy) {
      xlab += '<text x="' + X(xy.i, n).toFixed(1) + '" y="' + (H - 16) + '" class="xlab" text-anchor="middle">' + xy.label + '</text>';
    });

    var ex = X(n - 1, n), ey = Y(s[n - 1]);
    var bx = X(n - 1, n), by = Y(b[n - 1]);
    var endTag = '<circle cx="' + ex.toFixed(1) + '" cy="' + ey.toFixed(1) + '" r="4.5" fill="#4ade80"/>' +
      '<text x="' + (ex - 10).toFixed(1) + '" y="' + (ey - 12).toFixed(1) + '" class="tag" fill="#4ade80" text-anchor="end">Trend ' + ma + 'd · ' + fmtSigned(win.ret) + '</text>' +
      '<text x="' + (bx - 10).toFixed(1) + '" y="' + (by + 16).toFixed(1) + '" class="tag" fill="#8a8a8a" text-anchor="end">Hold BTC · ' + fmtSigned(DATA.benchmark.ret) + '</text>';

    var title = '<text x="500" y="28" class="title" text-anchor="middle">Ride the uptrends, sit out the crashes</text>';
    var legend = '<g transform="translate(' + (PL + 8) + ',46)">' +
      '<line x1="0" y1="0" x2="22" y2="0" class="strat"/><text x="30" y="5" class="lgd" fill="#ededed">Trend-following BTC · ' + ma + '-day</text>' +
      '<line x1="0" y1="22" x2="22" y2="22" class="btc-line"/><text x="30" y="27" class="lgd" fill="#8a8a8a">Buy &amp; hold BTC</text></g>';

    return '<svg viewBox="0 0 ' + W + ' ' + H + '" class="eqsvg" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Trend-following BTC (' + ma + '-day MA) vs buy and hold BTC, growth of one dollar, log scale">' +
      '<defs><linearGradient id="stratFill" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="#4ade80" stop-opacity="0.22"/><stop offset="100%" stop-color="#4ade80" stop-opacity="0"/>' +
      '</linearGradient></defs>' +
      title + grid + ylab + xlab +
      '<polyline class="btc-line" points="' + btcPts + '"/>' +
      '<path d="' + area + '" fill="url(#stratFill)" class="stratfill"/>' +
      '<polyline class="strat" points="' + stratPts + '"/>' +
      endTag + legend +
      '</svg>';
  }

  function render(ma, animate) {
    host.innerHTML = buildSVG(ma);
    if (reduce) return;
    var svg = host.querySelector('svg');
    if (!svg) return;
    var strat = svg.querySelector('.strat');
    var fill = svg.querySelector('.stratfill');
    if (animate && strat && strat.getTotalLength) {
      var len = strat.getTotalLength();
      strat.style.strokeDasharray = len;
      strat.style.strokeDashoffset = len;
      if (fill) fill.style.opacity = '0';
      strat.getBoundingClientRect();
      strat.style.transition = 'stroke-dashoffset 1.2s cubic-bezier(.4,0,.2,1)';
      strat.style.strokeDashoffset = '0';
      if (fill) { fill.style.transition = 'opacity .9s ease .3s'; fill.style.opacity = '1'; }
    }
  }

  function setText(id, v) { var e = document.getElementById(id); if (e) { e.textContent = v; e.dataset.done = '1'; } }
  function updateStats(ma) {
    var win = winByMa(ma);
    setText('stat-ret', fmtSigned(win.ret));
    setText('stat-apr', fmtApr(win.apr));
    setText('stat-dd', fmtDd(win.dd));
    setText('stat-sharpe', win.sharpe.toFixed(2));
  }
  function highlightRow(ma) {
    document.querySelectorAll('#trendTableBody tr[data-ma]').forEach(function (tr) {
      tr.classList.toggle('skill', parseInt(tr.getAttribute('data-ma'), 10) === ma);
    });
  }
  function setMa(ma, animate, withStats) {
    curMa = ma;
    render(ma, animate);
    if (withStats) updateStats(ma);
    highlightRow(ma);
    document.querySelectorAll('.lev-btn').forEach(function (b) {
      b.classList.toggle('active', parseInt(b.getAttribute('data-ma'), 10) === ma);
    });
  }

  fetch('assets/trend_data.json')
    .then(function (r) { if (!r.ok) throw new Error('no data'); return r.json(); })
    .then(function (d) {
      DATA = d;
      curMa = d.default || 100;
      if (fallback) fallback.remove();
      document.querySelectorAll('.lev-btn').forEach(function (b) {
        b.addEventListener('click', function () { setMa(parseInt(b.getAttribute('data-ma'), 10), true, true); });
      });
      setMa(curMa, false, false); // HTML already shows default stats; let reveal.js count them up
      if (reduce) return;
      var io = new IntersectionObserver(function (es) {
        es.forEach(function (e) { if (e.isIntersecting && !drawnOnce) { drawnOnce = true; render(curMa, true); io.disconnect(); } });
      }, { threshold: 0.3 });
      io.observe(host);
      setTimeout(function () {
        if (!drawnOnce && document.documentElement.classList.contains('reveal-fallback')) { drawnOnce = true; render(curMa, true); }
      }, 1300);
    })
    .catch(function () { /* keep img fallback */ });
})();
