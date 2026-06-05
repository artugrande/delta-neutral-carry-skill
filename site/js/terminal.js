/* Live signal terminal: types the question, streams the CMC reading,
   then reveals the HOLD verdict. Runs once when scrolled into view. */
(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var body = document.getElementById('termBody');
  var term = document.getElementById('terminal');
  if (!body || !term) return;

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }
  function line(html, cls) { var d = el('div', cls, html); body.appendChild(d); return d; }
  function row(key, val, valcls) {
    var d = el('div', 'row');
    d.appendChild(el('span', 'key', key));
    d.appendChild(el('span', valcls || 'k', val));
    body.appendChild(d);
    return d;
  }
  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  function typeInto(node, text, speed) {
    return new Promise(function (resolve) {
      var i = 0;
      var cur = el('span', 'term-cursor');
      node.appendChild(cur);
      (function step() {
        if (i < text.length) {
          cur.insertAdjacentText('beforebegin', text[i]);
          i++;
          setTimeout(step, speed);
        } else { resolve(cur); }
      })();
    });
  }

  async function run() {
    body.innerHTML = '';
    // 1. prompt + typed question
    var p = line('', 'q');
    var prompt = el('span', 'prompt', '$ ');
    p.appendChild(prompt);
    var cur = await typeInto(p, 'Which majors are trending right now?', 36);
    await wait(420);
    cur.remove();

    line('&nbsp;');
    // 2. reading
    var r = line('<span class="dim">→ reading live CoinMarketCap data…</span>');
    await wait(620);

    // 3. signal rows (staggered)
    var rows = [
      ['BTC · vs 100-day avg', 'below ▼', 'neg'],
      ['ETH · vs 100-day avg', 'below ▼', 'neg'],
      ['BNB · vs 100-day avg', 'below ▼', 'neg'],
      ['SOL · vs 100-day avg', 'below ▼', 'neg'],
      ['fear &amp; greed index', '18 · Extreme Fear', 'neg']
    ];
    for (var i = 0; i < rows.length; i++) {
      var rr = row(rows[i][0], rows[i][1], rows[i][2]);
      rr.style.opacity = 0;
      rr.style.transition = 'opacity .35s ease';
      (function (x) { setTimeout(function () { x.style.opacity = 1; }, 16); })(rr);
      await wait(260);
    }

    await wait(300);
    line('&nbsp;');
    line('<span class="dim">→ trending up: <span class="neg">0 of 4 majors</span> · regime RISK-OFF</span>');
    await wait(520);

    // 4. verdict
    var v = el('div', 'verdict');
    v.innerHTML = '<span class="tag">100% CASH</span><span class="txt">No major is trending up — hold stablecoins and wait for the first to reclaim its average.</span>';
    body.appendChild(v);
    setTimeout(function () { v.classList.add('show'); }, 16);
    await wait(700);
    var t = line('<span class="dim">next action → <span class="pos">BUY</span> the first major that closes back above its 100-day average</span>');
    t.style.opacity = 0; t.style.transition = 'opacity .4s ease';
    setTimeout(function () { t.style.opacity = 1; }, 16);
  }

  function runStatic() {
    body.innerHTML = '';
    line('<span class="prompt">$ </span><span class="q">Should I be holding BTC right now?</span>');
    line('&nbsp;');
    line('<span class="dim">→ reading live CoinMarketCap data…</span>');
    row('BTC · vs 100-day avg', 'below ▼', 'neg');
    row('ETH · vs 100-day avg', 'below ▼', 'neg');
    row('BNB · vs 100-day avg', 'below ▼', 'neg');
    row('SOL · vs 100-day avg', 'below ▼', 'neg');
    row('fear &amp; greed index', '18 · Extreme Fear', 'neg');
    line('&nbsp;');
    line('<span class="dim">→ trending up: <span class="neg">0 of 4 majors</span> · regime RISK-OFF</span>');
    var v = el('div', 'verdict show');
    v.innerHTML = '<span class="tag">100% CASH</span><span class="txt">No major is trending up — hold stablecoins and wait for the first to reclaim its average.</span>';
    body.appendChild(v);
    line('<span class="dim">next action → <span class="pos">BUY</span> the first major that closes back above its 100-day average</span>');
  }

  var started = false;
  if (reduce) { runStatic(); return; }
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      if (en.isIntersecting && !started) { started = true; run(); io.disconnect(); }
    });
  }, { threshold: 0.35 });
  io.observe(term);
  // fallback: only if the global IO-dead signal is set (throttled iframe) —
  // show the static transcript. In working browsers we keep the typing on scroll.
  setTimeout(function () {
    if (started) return;
    if (document.documentElement.classList.contains('reveal-fallback')) { started = true; io.disconnect(); runStatic(); }
  }, 1400);
})();
