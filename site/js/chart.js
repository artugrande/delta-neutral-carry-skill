/* Equity curve: inline the real SVG so document CSS styles it,
   then draw the green strategy line on when scrolled into view. */
(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var host = document.getElementById('chart');
  var fallback = document.getElementById('chartFallback');
  if (!host) return;

  fetch('assets/equity_curve.svg')
    .then(function (r) { if (!r.ok) throw new Error('no svg'); return r.text(); })
    .then(function (txt) {
      var tmp = document.createElement('div');
      tmp.innerHTML = txt.trim();
      var svg = tmp.querySelector('svg');
      if (!svg) throw new Error('no svg el');
      svg.classList.add('eqsvg');
      svg.removeAttribute('width');
      svg.removeAttribute('height');
      svg.style.width = '100%';
      svg.style.height = 'auto';

      // replace fallback img with live svg
      if (fallback) fallback.remove();
      host.appendChild(svg);

      var strat = svg.querySelector('.strat');
      var btc = svg.querySelector('.btc');
      var fill = svg.querySelector('path[fill="url(#stratFill)"]') || svg.querySelector('defs ~ path');
      // legend strat line is also class .strat (short) — pick the longest one as the curve
      var allStrat = svg.querySelectorAll('.strat');
      if (allStrat.length > 1) {
        var best = null, bestLen = 0;
        allStrat.forEach(function (s) {
          var L = (s.getTotalLength ? s.getTotalLength() : 0);
          if (L > bestLen) { bestLen = L; best = s; }
        });
        strat = best || strat;
      }

      var dots = svg.querySelectorAll('circle');
      var tags = svg.querySelectorAll('.tag');

      function prep() {
        if (!strat || !strat.getTotalLength) return;
        var len = strat.getTotalLength();
        strat.style.strokeDasharray = len;
        strat.style.strokeDashoffset = len;
        if (btc) btc.style.opacity = '0';
        if (fill) fill.style.opacity = '0';
        dots.forEach(function (d) { d.style.opacity = '0'; });
        tags.forEach(function (t) { t.style.opacity = '0'; });
      }

      function draw() {
        if (!strat || !strat.getTotalLength) return;
        if (btc) { btc.style.transition = 'opacity 1.2s ease'; btc.style.opacity = '0.55'; }
        strat.style.transition = 'stroke-dashoffset 2.4s cubic-bezier(.4,0,.2,1)';
        setTimeout(function () { strat.style.strokeDashoffset = '0'; }, 16);
        setTimeout(function () {
          if (fill) { fill.style.transition = 'opacity 1s ease'; fill.style.opacity = '1'; }
          dots.forEach(function (d) { d.style.transition = 'opacity .6s ease'; d.style.opacity = '1'; });
          tags.forEach(function (t) { t.style.transition = 'opacity .6s ease'; t.style.opacity = '1'; });
        }, 1700);
      }

      function showStatic() {
        if (!strat || !strat.getTotalLength) return;
        strat.style.transition = 'none'; strat.style.strokeDashoffset = '0';
        if (btc) { btc.style.transition = 'none'; btc.style.opacity = '0.55'; }
        if (fill) { fill.style.transition = 'none'; fill.style.opacity = '1'; }
        dots.forEach(function (d) { d.style.transition = 'none'; d.style.opacity = '1'; });
        tags.forEach(function (t) { t.style.transition = 'none'; t.style.opacity = '1'; });
      }

      if (reduce) return; // leave fully drawn
      prep();
      var drawn = false;
      function go() { if (drawn) return; drawn = true; draw(); }
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) { go(); io.disconnect(); }
        });
      }, { threshold: 0.3 });
      io.observe(host);
      // fallback: only if the global IO-dead signal is set (throttled iframe) —
      // snap the curve to its drawn state with no transition.
      setTimeout(function () {
        if (drawn) return;
        if (document.documentElement.classList.contains('reveal-fallback')) { drawn = true; io.disconnect(); showStatic(); }
      }, 1300);
    })
    .catch(function () {
      /* keep the <img> fallback that's already in the DOM */
    });
})();
