/* Interactive leverage chart: reads assets/equity_data.json and draws the
   delta-neutral carry equity at the selected leverage (1x/2x/5x) against a
   stablecoin-lending benchmark. Buttons update the curve, the stat strip, and
   the table highlight. Animates the strategy line on first view. */
(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var host = document.getElementById('chart');
  var fallback = document.getElementById('chartFallback');
  if (!host) return;

  var DATA = null, drawnOnce = false;

  // ---- geometry (fixed y-scale so the leverage effect is visible) ----
  var W = 1000, H = 460, PL = 60, PR = 26, PT = 44, PB = 42;
  var PW = W - PL - PR, PH = H - PT - PB;
  var YMIN = 0.93, YMAX = 1.72;
  function X(i, n) { return PL + (i / (n - 1)) * PW; }
  function Y(v) { return PT + (1 - (v - YMIN) / (YMAX - YMIN)) * PH; }

  function fmtSigned(v) { return (v < 0 ? '−' : '+') + Math.abs(v * 100).toFixed(2) + '%'; }
  function fmtApr(v) { return (v < 0 ? '−' : '') + Math.abs(v * 100).toFixed(2) + '%'; }
  function fmtDd(v) { return '−' + Math.abs(v * 100).toFixed(2) + '%'; }

  function levelByLev(L) {
    for (var i = 0; i < DATA.levels.length; i++) if (DATA.levels[i].lev === L) return DATA.levels[i];
    return DATA.levels[0];
  }

  function points(arr) {
    var n = arr.length, p = '';
    for (var i = 0; i < n; i++) p += (i ? ' ' : '') + X(i, n).toFixed(1) + ',' + Y(arr[i]).toFixed(1);
    return p;
  }

  function buildSVG(L) {
    var lvl = levelByLev(L);
    var s = lvl.series, b = DATA.benchmark.series, n = s.length;
    var stratPts = points(s), benchPts = points(b);
    var baseY = Y(YMIN).toFixed(1);
    var area = 'M' + X(0, n).toFixed(1) + ',' + baseY + ' L' + stratPts.split(' ').join(' L') +
               ' L' + X(n - 1, n).toFixed(1) + ',' + baseY + ' Z';

    var grid = '', ylab = '';
    [1.0, 1.2, 1.4, 1.6].forEach(function (v) {
      var y = Y(v).toFixed(1);
      grid += '<line x1="' + PL + '" y1="' + y + '" x2="' + (W - PR) + '" y2="' + y + '" class="grid"/>';
      ylab += '<text x="' + (PL - 10) + '" y="' + (Y(v) + 4).toFixed(1) + '" class="ylab" text-anchor="end">' + v.toFixed(1) + '×</text>';
    });

    var xlab = '';
    DATA.xYears.forEach(function (xy) {
      xlab += '<text x="' + X(xy.i, n).toFixed(1) + '" y="' + (H - 16) + '" class="xlab" text-anchor="middle">' + xy.label + '</text>';
    });

    var ex = X(n - 1, n), ey = Y(s[n - 1]);
    var endTag = '<circle cx="' + ex.toFixed(1) + '" cy="' + ey.toFixed(1) + '" r="4.5" fill="#4ade80"/>' +
      '<text x="' + (ex - 10).toFixed(1) + '" y="' + (ey - 12).toFixed(1) + '" class="tag" fill="#4ade80" text-anchor="end">' + L + '× · ' + fmtSigned(lvl.ret) + '</text>';

    var title = '<text x="500" y="28" class="title" text-anchor="middle">Market-neutral — dial your return with leverage</text>';
    var legend = '<g transform="translate(' + (PL + 8) + ',46)">' +
      '<line x1="0" y1="0" x2="22" y2="0" class="strat"/><text x="30" y="5" class="lgd" fill="#ededed">Delta-neutral carry · ' + L + '×</text>' +
      '<line x1="0" y1="22" x2="22" y2="22" class="bench-line"/><text x="30" y="27" class="lgd" fill="#8a8a8a">' + DATA.benchmark.label + '</text></g>';

    return '<svg viewBox="0 0 ' + W + ' ' + H + '" class="eqsvg" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Strategy equity at ' + L + 'x leverage vs stablecoin lending">' +
      '<defs><linearGradient id="stratFill" x1="0" y1="0" x2="0" y2="1">' +
      '<stop offset="0%" stop-color="#4ade80" stop-opacity="0.22"/><stop offset="100%" stop-color="#4ade80" stop-opacity="0"/>' +
      '</linearGradient></defs>' +
      title + grid + ylab + xlab +
      '<polyline class="bench-line" points="' + benchPts + '"/>' +
      '<path d="' + area + '" fill="url(#stratFill)" class="stratfill"/>' +
      '<polyline class="strat" points="' + stratPts + '"/>' +
      endTag + legend +
      '</svg>';
  }

  function render(L, animate) {
    host.innerHTML = buildSVG(L);
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
      strat.getBoundingClientRect(); // force reflow so the transition runs
      strat.style.transition = 'stroke-dashoffset 1.1s cubic-bezier(.4,0,.2,1)';
      strat.style.strokeDashoffset = '0';
      if (fill) { fill.style.transition = 'opacity .9s ease .25s'; fill.style.opacity = '1'; }
    }
  }

  function setText(id, v) { var e = document.getElementById(id); if (e) { e.textContent = v; e.dataset.done = '1'; } }
  function updateStats(L) {
    var lvl = levelByLev(L);
    setText('stat-ret', fmtSigned(lvl.ret));
    setText('stat-apr', fmtApr(lvl.apr));
    setText('stat-dd', fmtDd(lvl.dd));
    setText('stat-sharpe', lvl.sharpe.toFixed(1));
  }

  function highlightRow(L) {
    var rows = document.querySelectorAll('#levTableBody tr[data-lev]');
    rows.forEach(function (tr) { tr.classList.toggle('skill', parseInt(tr.getAttribute('data-lev'), 10) === L); });
  }

  function setLev(L, animate, withStats) {
    render(L, animate);
    if (withStats) updateStats(L);
    highlightRow(L);
    document.querySelectorAll('.lev-btn').forEach(function (b) {
      b.classList.toggle('active', parseInt(b.getAttribute('data-lev'), 10) === L);
    });
  }

  fetch('assets/equity_data.json')
    .then(function (r) { if (!r.ok) throw new Error('no data'); return r.json(); })
    .then(function (d) {
      DATA = d;
      if (fallback) fallback.remove();

      document.querySelectorAll('.lev-btn').forEach(function (b) {
        b.addEventListener('click', function () {
          setLev(parseInt(b.getAttribute('data-lev'), 10), true, true);
        });
      });

      // initial: render 1x WITHOUT touching the stat strip, so reveal.js still
      // count-ups the (1x) HTML values. Animate the curve when it scrolls in.
      setLev(1, false, false);
      if (reduce) return;
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting && !drawnOnce) { drawnOnce = true; render(1, true); io.disconnect(); }
        });
      }, { threshold: 0.3 });
      io.observe(host);
      setTimeout(function () {
        if (!drawnOnce && document.documentElement.classList.contains('reveal-fallback')) {
          drawnOnce = true; render(1, true);
        }
      }, 1300);
    })
    .catch(function () { /* keep the <img> fallback already in the DOM */ });
})();
