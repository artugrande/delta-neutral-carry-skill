/* Reveal engine: scroll-triggered fade+rise, word-by-word headings,
   count-up numbers, nav state, and pointer glow on leg cards. */
(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---- split headings into word spans (for the reveal-words effect) ---- */
  function splitWords(el) {
    // Walk child nodes; wrap text words, keep element children (e.g. <span class="g">) intact.
    var nodes = Array.prototype.slice.call(el.childNodes);
    el.innerHTML = '';
    nodes.forEach(function (node) {
      if (node.nodeType === 3) {
        var parts = node.textContent.split(/(\s+)/);
        parts.forEach(function (p) {
          if (p.trim() === '') { el.appendChild(document.createTextNode(p)); return; }
          el.appendChild(makeWord(p));
        });
      } else if (node.nodeType === 1) {
        // element such as <span class="g">not to trade.</span> — split its inner words too
        var keepClass = node.className;
        var inner = node.textContent.split(/(\s+)/);
        inner.forEach(function (p) {
          if (p.trim() === '') { el.appendChild(document.createTextNode(p)); return; }
          el.appendChild(makeWord(p, keepClass));
        });
      }
    });
  }
  function makeWord(text, cls) {
    var w = document.createElement('span');
    w.className = 'word';
    var inner = document.createElement('span');
    if (cls) inner.className = cls;
    inner.textContent = text;
    w.appendChild(inner);
    return w;
  }

  var headings = document.querySelectorAll('.reveal-words');
  headings.forEach(function (h) {
    if (reduce) { h.classList.add('in'); return; }
    splitWords(h);
    // stagger each word's inner span
    var words = h.querySelectorAll('.word > span');
    words.forEach(function (s, i) { s.style.transitionDelay = (i * 45) + 'ms'; });
  });

  /* ---- count-up numbers ---- */
  function countUp(el) {
    var to = parseFloat(el.getAttribute('data-to'));
    var dec = parseInt(el.getAttribute('data-dec') || '0', 10);
    var pre = el.getAttribute('data-prefix') || '';
    var suf = el.getAttribute('data-suffix') || '';
    var neg = to < 0;
    var abs = Math.abs(to);
    var dur = 1300, t0 = null;
    function fmt(v) {
      var s = v.toFixed(dec);
      return pre + (neg ? '−' : '') + s + suf;
    }
    function tick(now) {
      if (!t0) t0 = now;
      var p = Math.min((now - t0) / dur, 1);
      var e = 1 - Math.pow(1 - p, 3); // easeOutCubic
      el.textContent = fmt(abs * e);
      if (p < 1) requestAnimationFrame(tick);
      else el.textContent = fmt(abs);
    }
    if (reduce) { el.textContent = fmt(abs); return; }
    requestAnimationFrame(tick);
  }

  /* ---- intersection observer for reveals ---- */
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      if (!en.isIntersecting) return;
      var el = en.target;
      el.classList.add('in');
      // fire count-ups inside this element
      el.querySelectorAll('.count').forEach(function (c) {
        if (!c.dataset.done) { c.dataset.done = '1'; countUp(c); }
      });
      // standalone count element
      if (el.classList.contains('count') && !el.dataset.done) { el.dataset.done = '1'; countUp(el); }
      io.unobserve(el);
    });
  }, { threshold: 0.18, rootMargin: '0px 0px -8% 0px' });

  document.querySelectorAll('.reveal, .reveal-words').forEach(function (el) {
    if (reduce) { el.classList.add('in'); el.querySelectorAll('.count').forEach(function (c) { countUp(c); }); return; }
    io.observe(el);
  });
  // chips hold standalone .count not wrapped in .reveal parent count handling — observe them too
  document.querySelectorAll('.count').forEach(function (c) { if (!reduce) io.observe(c); });

  /* ---- safety fallback ----
     In some embedded/throttled iframes IntersectionObserver callbacks are
     never delivered. If nothing has revealed shortly after load, reveal
     everything directly so content is never stuck at opacity:0. Authored
     text already holds the final count values, so skipping the count-up is fine. */
  if (!reduce) {
    setTimeout(function () {
      if (document.querySelector('.reveal.in, .reveal-words.in')) return; // IO is working
      document.documentElement.classList.add('reveal-fallback');
      document.querySelectorAll('.reveal, .reveal-words').forEach(function (el) {
        el.classList.add('in');
        el.querySelectorAll('.count').forEach(function (c) { if (!c.dataset.done) { c.dataset.done = '1'; countUp(c); } });
      });
    }, 700);
  }

  /* ---- nav scrolled state ---- */
  var nav = document.getElementById('nav');
  function onScroll() { if (nav) nav.classList.toggle('scrolled', window.scrollY > 24); }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* ---- pointer glow follows cursor on leg cards ---- */
  document.querySelectorAll('.leg').forEach(function (leg) {
    leg.addEventListener('pointermove', function (e) {
      var r = leg.getBoundingClientRect();
      leg.style.setProperty('--mx', (e.clientX - r.left) + 'px');
      leg.style.setProperty('--my', (e.clientY - r.top) + 'px');
    });
  });
})();
