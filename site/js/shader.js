/* Hero shader: layered flowing sine waves, green on black.
   Calm + premium — slow drift, soft glow, subtle mouse parallax. */
(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var canvas = document.getElementById('shader');
  if (!canvas || reduce) return;
  var ctx = canvas.getContext('2d');
  var dpr = Math.min(window.devicePixelRatio || 1, 2);
  var W = 0, H = 0;
  var mx = 0, my = 0;        // target mouse offset (-1..1)
  var px = 0, py = 0;        // smoothed parallax

  // Each layer is a horizontal band of flowing sine lines.
  var LAYERS = [
    { y: 0.34, amp: 46, len: 0.0016, speed: 0.10, lines: 5, gap: 9,  alpha: 0.9,  w: 1.6, par: 26 },
    { y: 0.52, amp: 62, len: 0.0012, speed: 0.07, lines: 6, gap: 11, alpha: 0.55, w: 1.3, par: 16 },
    { y: 0.66, amp: 80, len: 0.0009, speed: 0.05, lines: 5, gap: 14, alpha: 0.30, w: 1.1, par: 9  }
  ];

  function resize() {
    W = canvas.clientWidth = window.innerWidth;
    H = canvas.clientHeight = window.innerHeight;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  window.addEventListener('resize', resize);
  resize();

  window.addEventListener('pointermove', function (e) {
    mx = (e.clientX / window.innerWidth - 0.5) * 2;
    my = (e.clientY / window.innerHeight - 0.5) * 2;
  });

  var t0 = performance.now();
  function drawFrame(now) {
    var t = (now - t0) / 1000;
    // smooth parallax
    px += (mx - px) * 0.04;
    py += (my - py) * 0.04;

    ctx.clearRect(0, 0, W, H);
    ctx.globalCompositeOperation = 'lighter';

    for (var li = 0; li < LAYERS.length; li++) {
      var L = LAYERS[li];
      var baseY = H * L.y + py * L.par;
      var phase = t * L.speed * Math.PI;
      for (var n = 0; n < L.lines; n++) {
        var off = (n - (L.lines - 1) / 2) * L.gap;
        var a = L.alpha * (1 - Math.abs(n - (L.lines - 1) / 2) / L.lines * 0.7);
        ctx.beginPath();
        ctx.lineWidth = L.w;
        ctx.strokeStyle = 'rgba(74,222,128,' + a.toFixed(3) + ')';
        ctx.shadowColor = 'rgba(74,222,128,0.5)';
        ctx.shadowBlur = li === 0 ? 8 : 4;
        var step = 14;
        for (var x = -40; x <= W + 40; x += step) {
          var xx = x + px * L.par * 1.4;
          // two summed sines for organic motion
          var y = baseY + off
            + Math.sin(x * L.len + phase + n * 0.5) * L.amp
            + Math.sin(x * L.len * 2.3 - phase * 0.7 + n) * (L.amp * 0.28);
          if (x === -40) ctx.moveTo(xx, y); else ctx.lineTo(xx, y);
        }
        ctx.stroke();
      }
    }
    ctx.shadowBlur = 0;
    ctx.globalCompositeOperation = 'source-over';
  }
  function loop(now) { drawFrame(now); requestAnimationFrame(loop); }
  // draw one frame synchronously so the canvas is never blank, then animate
  drawFrame(performance.now());
  requestAnimationFrame(loop);

  // fade in once first frame is up (setTimeout, not rAF: fires even if the
  // frame is throttled/not painting, so the canvas never stays invisible)
  setTimeout(function () { canvas.classList.add('on'); }, 30);
})();
