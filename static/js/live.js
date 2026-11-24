(function () {
  "use strict";
  var cfg = document.getElementById("cfg");
  var URLS = JSON.parse(cfg.dataset.urls), WS_URL = cfg.dataset.ws, MODE = cfg.dataset.mode, CLOSE_URL = cfg.dataset.close;
  var TF_WS = { "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "4h": "4h", "8h": "8h", "1d": "1d", "1w": "7d" };
  var TF_SEC = { "1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "8h": 28800, "1d": 86400, "1w": 604800 };
  var state = { symbol: cfg.dataset.symbol || "BTC_USDT", tf: "1h", ws: null, wsOk: false, lines: [], fibLines: [], tick: 0 };
  var csrf = document.querySelector("input[name=csrfmiddlewaretoken]").value;
  var $ = function (id) { return document.getElementById(id); };
  var prices = {}, L = {}, fibData = null, fibOn = true, headSym = null;
  var smc = null, smcOn = true, markerBase = [], markerScan = [], zsig = "";
  var ALL = Array.prototype.map.call(document.querySelectorAll(".pair"), function (e) { return e.dataset.sym; });
  var lastScan = null;

  function icons() { try { if (window.lucide && window.lucide.createIcons) window.lucide.createIcons(); } catch (e) {} }
  function ic(name) { return '<i data-lucide="' + name + '"></i>'; }
  function f(v) {
    if (v === null || v === undefined || isNaN(v)) return "—";
    var a = Math.abs(v), d = a >= 1000 ? 2 : a >= 1 ? 4 : 6;
    return (+v).toFixed(d).replace(/\.?0+$/, "");
  }
  function mk(el, h, interactive) {
    return LightweightCharts.createChart(el, {
      width: el.clientWidth || undefined, height: el.clientHeight || h,
      layout: { background: { color: "#0a1530" }, textColor: "#cbd5e1" },
      grid: { vertLines: { color: "#12306b33" }, horzLines: { color: "#12306b33" } },
      timeScale: { timeVisible: true, secondsVisible: false, rightOffset: 4 }, crosshair: { mode: 0 },
      handleScroll: interactive ? { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false } : false,
      handleScale: interactive ? { mouseWheel: true, pinch: true, axisPressedMouseMove: true, axisDoubleClickReset: true } : false,
      kineticScroll: { touch: true, mouse: false }
    });
  }
  var chart = mk($("chart"), 430, true), rsiChart = mk($("rsi"), 105, false), macdChart = mk($("macd"), 105, false), stochChart = mk($("stoch"), 105, false);
  var candle = chart.addCandlestickSeries({ upColor: "#26a69a", downColor: "#ef5350", borderVisible: false, wickUpColor: "#26a69a", wickDownColor: "#ef5350" });
  var vol = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "" });
  vol.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
  function line(color, ch) { return (ch || chart).addLineSeries({ color: color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false }); }
  var ema = { e9: line("#38bdf8"), e21: line("#f59e0b"), e50: line("#e879f9"), e200: line("#f8fafc") };
  var bb = { up: line("#3b82f6"), lo: line("#3b82f6"), mid: line("#64748b") };
  var vwap = line("#22d3ee"); vwap.applyOptions({ visible: false });
  var ma = { m5: line("#fbbf24"), m10: line("#34d399"), m30: line("#f59e0b") };
  Object.keys(ma).forEach(function (k) { ma[k].applyOptions({ visible: false }); });
  var maOn = false;
  var rsi = rsiChart.addLineSeries({ color: "#a78bfa", lineWidth: 1 });
  rsi.createPriceLine({ price: 70, color: "#64748b", lineStyle: 2 }); rsi.createPriceLine({ price: 30, color: "#64748b", lineStyle: 2 });
  var mLine = macdChart.addLineSeries({ color: "#38bdf8", lineWidth: 1 }), mSig = macdChart.addLineSeries({ color: "#f59e0b", lineWidth: 1 });
  var mHist = macdChart.addHistogramSeries({});
  var sK = stochChart.addLineSeries({ color: "#38bdf8", lineWidth: 1 }), sD = stochChart.addLineSeries({ color: "#f59e0b", lineWidth: 1 });
  sK.createPriceLine({ price: 80, color: "#64748b", lineStyle: 2 }); sK.createPriceLine({ price: 20, color: "#64748b", lineStyle: 2 });
  var subs = [rsiChart, macdChart, stochChart];
  chart.timeScale().subscribeVisibleLogicalRangeChange(function (r) { if (r) subs.forEach(function (c) { c.timeScale().setVisibleLogicalRange(r); }); });
  function resizeAll() {
    [[chart, "chart"], [rsiChart, "rsi"], [macdChart, "macd"], [stochChart, "stoch"]].forEach(function (x) {
      var el = $(x[1]); if (el.clientWidth > 0 && el.clientHeight > 0) x[0].applyOptions({ width: el.clientWidth, height: el.clientHeight });
    });
  }
  window.addEventListener("resize", resizeAll);
  window.addEventListener("orientationchange", function () { setTimeout(resizeAll, 300); });
  if (window.ResizeObserver) { new ResizeObserver(resizeAll).observe($("chart").parentElement); }

  function msg(t) { $("msg").textContent = t || ""; }
  function api(url, opt) {
    return fetch(url, opt).then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || "Erreur"); return j; }); });
  }
  function last(a) { return a && a.length ? a[a.length - 1] : null; }

  // ---- legendes (valeurs au curseur, sinon derniere bougie) ----
  function paintLegend(v) {
    var o = v.ohlc, h = "";
    if (o) { var up = o.close >= o.open; h += '<div class="' + (up ? "up" : "down") + '">O ' + f(o.open) + " H " + f(o.high) + " L " + f(o.low) + " C " + f(o.close) + "</div>"; }
    h += '<div style="color:#38bdf8">EMA 9 close 0 &nbsp; ' + f(v.e9) + "</div>";
    h += '<div style="color:#f59e0b">EMA 21 close 0 &nbsp; ' + f(v.e21) + "</div>";
    h += '<div style="color:#e879f9">EMA 50 close 0 &nbsp; ' + f(v.e50) + "</div>";
    h += '<div style="color:#f8fafc">EMA 200 close 0 &nbsp; ' + f(v.e200) + "</div>";
    if (maOn) h += '<div><span style="color:#fbbf24">MA5 ' + f(v.ma5) + '</span> <span style="color:#34d399">MA10 ' + f(v.ma10) + '</span> <span style="color:#f59e0b">MA30 ' + f(v.ma30) + "</span></div>";
    h += '<div style="color:#26a69a">Volume ' + f(v.vol) + "</div>";
    $("legend").innerHTML = h;
    $("lbl-rsi").textContent = "RSI (14)  " + f(v.rsi);
    $("lbl-macd").textContent = "MACD (12, 26, 9)  " + f(v.macd) + "  " + f(v.sig) + "  " + f(v.hist);
    $("lbl-stoch").textContent = "Stoch RSI (14, 14, 3, 3)  " + f(v.sk) + "  " + f(v.sd);
  }
  function val(p, s) { var x = p.seriesData.get(s); return x ? x.value : undefined; }
  chart.subscribeCrosshairMove(function (p) {
    if (!p.time || !p.seriesData) { paintLegend(L); return; }
    var c = p.seriesData.get(candle), v = {};
    for (var k in L) v[k] = L[k];
    if (c) v.ohlc = c;
    v.vol = val(p, vol); v.e9 = val(p, ema.e9); v.e21 = val(p, ema.e21); v.e50 = val(p, ema.e50); v.e200 = val(p, ema.e200);
    paintLegend(v);
  });
  rsiChart.subscribeCrosshairMove(function (p) { if (p.time && p.seriesData) $("lbl-rsi").textContent = "RSI (14)  " + f(val(p, rsi)); });
  macdChart.subscribeCrosshairMove(function (p) { if (p.time && p.seriesData) $("lbl-macd").textContent = "MACD (12, 26, 9)  " + f(val(p, mLine)) + "  " + f(val(p, mSig)) + "  " + f(val(p, mHist)); });
  stochChart.subscribeCrosshairMove(function (p) { if (p.time && p.seriesData) $("lbl-stoch").textContent = "Stoch RSI (14, 14, 3, 3)  " + f(val(p, sK)) + "  " + f(val(p, sD)); });

  // ---- Smart Money sur le graphique : zones (canvas) + etiquettes (marqueurs) ----
  var zc = $("zones"), zx = zc.getContext("2d");
  function setMarkers() { candle.setMarkers(markerBase.concat(markerScan).sort(function (a, b) { return a.time - b.time; })); }
  function smcMarkers() {
    markerBase = [];
    if (smc && smcOn) {
      smc.labels.forEach(function (l) { markerBase.push({ time: l.time, position: l.pos === "above" ? "aboveBar" : "belowBar", color: (l.label === "HH" || l.label === "HL") ? "#22c55e" : "#ef4444", shape: "circle", text: l.label }); });
      smc.displacement.forEach(function (d) { markerBase.push({ time: d.time, position: "inBar", color: "#fb923c", shape: "circle", text: "D" }); });
      smc.sweeps.forEach(function (sw) { markerBase.push({ time: sw.time, position: sw.side === "BSL" ? "aboveBar" : "belowBar", color: "#facc15", shape: "square", text: "Sweep" }); });
    }
    setMarkers();
  }
  function rightEdge() { var w = $("chart").clientWidth, pw = 0; try { pw = chart.priceScale("right").width(); } catch (e) {} return w - (pw || 58); }
  function drawSmc() {
    var w = $("chart").clientWidth, h = $("chart").clientHeight, dpr = window.devicePixelRatio || 1;
    if (!w || !h) return;
    if (zc.width !== Math.round(w * dpr) || zc.height !== Math.round(h * dpr)) { zc.width = Math.round(w * dpr); zc.height = Math.round(h * dpr); zc.style.width = w + "px"; zc.style.height = h + "px"; }
    zx.setTransform(dpr, 0, 0, dpr, 0, 0); zx.clearRect(0, 0, w, h);
    if (!smc || !smcOn) return;
    var ts = chart.timeScale(), R = rightEdge();
    function X(t) { var x = ts.timeToCoordinate(t); return x === null || x === undefined ? 0 : Math.max(0, x); }
    function Y(p) { return candle.priceToCoordinate(p); }
    function box(z, color, label) {
      var y0 = Y(z.hi), y1 = Y(z.lo); if (y0 === null || y1 === null) return;
      var x0 = X(z.time); if (x0 >= R) return;
      zx.fillStyle = color; zx.fillRect(x0, Math.min(y0, y1), R - x0, Math.max(2, Math.abs(y1 - y0)));
      zx.fillStyle = "#e2e8f0"; zx.font = "11px sans-serif"; zx.fillText(label, x0 + 4, Math.min(y0, y1) + 11);
    }
    smc.fvg.forEach(function (z) { box(z, z.type === "bullish" ? "rgba(34,197,94,0.20)" : "rgba(239,68,68,0.20)", "FVG"); });
    smc.ob.forEach(function (z) { box(z, z.type === "bullish" ? "rgba(34,197,94,0.34)" : "rgba(239,68,68,0.34)", "Order Block"); });
    smc.liquidity.forEach(function (l) {
      var y = Y(l.price); if (y === null) return;
      var x0 = X(l.time), col = l.side === "BSL" ? "#f87171" : "#4ade80";
      zx.strokeStyle = col; zx.fillStyle = col; zx.lineWidth = l.equal ? 2 : 1; zx.setLineDash([6, 4]);
      zx.beginPath(); zx.moveTo(x0, y); zx.lineTo(R, y); zx.stroke(); zx.setLineDash([]);
      zx.font = "11px sans-serif"; zx.fillText((l.equal ? (l.side === "BSL" ? "EQH · " : "EQL · ") : "") + (l.side === "BSL" ? "Buy-Side Liquidity" : "Sell-Side Liquidity"), Math.max(x0 + 4, R - 165), y - 3);
    });
    function extreme(e, high, label, col, rgba, dash, atr) {
      var y = Y(e.price); if (y === null) return;
      var x0 = X(e.time), yb = atr ? Y(e.price + (high ? 1 : -1) * 0.15 * atr) : null;
      if (yb !== null) { zx.fillStyle = rgba; zx.fillRect(x0, Math.min(y, yb), R - x0, Math.max(2, Math.abs(yb - y))); }
      zx.strokeStyle = col; zx.fillStyle = col; zx.lineWidth = 1; zx.setLineDash(dash);
      zx.beginPath(); zx.moveTo(x0, y); zx.lineTo(R, y); zx.stroke(); zx.setLineDash([]);
      zx.font = "11px sans-serif"; zx.fillText(f(e.price), x0 + 2, high ? y - 4 : y + 12);
      zx.fillText(label + " " + f(e.price) + (high ? " (liquidite haute)" : " (liquidite basse)"), Math.max(x0 + 4, R - 210), high ? y - 4 : y + 12);
    }
    var a24 = smc.range24;
    if (a24) { extreme(a24.high, true, "24h High", "#f87171", "rgba(248,113,113,0.16)", [2, 3], a24.atr); extreme(a24.low, false, "24h Low", "#4ade80", "rgba(74,222,128,0.16)", [2, 3], a24.atr); }
    var pd = smc.prev_day;
    if (pd) { extreme(pd.high, true, "PDH", "#fbbf24", "rgba(251,191,36,0.12)", [8, 4], a24 ? a24.atr : 0); extreme(pd.low, false, "PDL", "#38bdf8", "rgba(56,189,248,0.12)", [8, 4], a24 ? a24.atr : 0); }
    smc.events.forEach(function (e) {
      var y = Y(e.level); if (y === null) return;
      var x0 = X(e.from), x1 = X(e.to);
      zx.strokeStyle = "#60a5fa"; zx.lineWidth = 1; zx.setLineDash([4, 3]); zx.beginPath(); zx.moveTo(x0, y); zx.lineTo(x1, y); zx.stroke(); zx.setLineDash([]);
      zx.fillStyle = "#93c5fd"; zx.font = "bold 11px sans-serif"; zx.fillText(e.type, (x0 + x1) / 2 - 12, y - 3);
    });
  }
  setInterval(function () {   // redessine quand le graphique bouge (zoom, deplacement, echelle de prix)
    var r = chart.timeScale().getVisibleLogicalRange(), y = L.ohlc ? candle.priceToCoordinate(L.ohlc.close) : 0;
    var sig = [r && r.from, r && r.to, y, $("chart").clientWidth, $("chart").clientHeight].join();
    if (sig !== zsig) { zsig = sig; drawSmc(); }
  }, 200);

  // ---- Fibonacci ----
  function drawFib() {
    state.fibLines.forEach(function (l) { candle.removePriceLine(l); }); state.fibLines = [];
    if (!fibOn || !fibData) return;
    fibData.levels.forEach(function (lv) {
      state.fibLines.push(candle.createPriceLine({ price: lv.price, color: "#a78bfa99", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: (lv.ratio * 100).toFixed(1) + "%" }));
    });
  }

  // ---- chargement des donnees (REST Gate via Django) ----
  function paint(d) {
    candle.setData(d.candles);
    vol.setData(d.candles.map(function (c) { return { time: c.time, value: c.volume, color: c.close >= c.open ? "#26a69a66" : "#ef535066" }; }));
    ema.e9.setData(d.ema9); ema.e21.setData(d.ema21); ema.e50.setData(d.ema50); ema.e200.setData(d.ema200);
    bb.up.setData(d.bb_upper); bb.lo.setData(d.bb_lower); bb.mid.setData(d.bb_middle); vwap.setData(d.vwap);
    ma.m5.setData(d.ma5); ma.m10.setData(d.ma10); ma.m30.setData(d.ma30);
    rsi.setData(d.rsi); mLine.setData(d.macd); mSig.setData(d.signal);
    mHist.setData(d.hist.map(function (h) { return { time: h.time, value: h.value, color: h.value >= 0 ? "#26a69a" : "#ef5350" }; }));
    sK.setData(d.stoch_k); sD.setData(d.stoch_d);
    var c = last(d.candles);
    L = { ohlc: c, vol: c.volume, e9: (last(d.ema9) || {}).value, e21: (last(d.ema21) || {}).value, e50: (last(d.ema50) || {}).value, e200: (last(d.ema200) || {}).value,
      rsi: (last(d.rsi) || {}).value, macd: (last(d.macd) || {}).value, sig: (last(d.signal) || {}).value, hist: (last(d.hist) || {}).value,
      sk: (last(d.stoch_k) || {}).value, sd: (last(d.stoch_d) || {}).value,
      ma5: (last(d.ma5) || {}).value, ma10: (last(d.ma10) || {}).value, ma30: (last(d.ma30) || {}).value };
    $("last").textContent = f(c.close); paintLegend(L);
    fibData = d.fib; drawFib();
    smc = d.smc || null; smcMarkers(); drawSmc();
    var r24 = smc && smc.range24;
    $("h24").textContent = r24 ? "Plus haut 24h " + f(r24.high.price) + " · Plus bas 24h " + f(r24.low.price) : "";
  }
  function fetchAndPaint() {
    return api(URLS.candles + "?symbol=" + state.symbol + "&tf=" + state.tf).then(function (d) { paint(d); msg(""); }).catch(function (e) { msg(e.message); });
  }
  function headInfo() {
    $("title").textContent = state.symbol.replace("_", "/") + " · " + state.tf.toUpperCase();
    if (headSym !== state.symbol) { headSym = state.symbol; $("head-logo").innerHTML = logoHTML(state.symbol); }
    var p = prices[state.symbol];
    if (p) { var e = $("head-chg"); e.textContent = (p.change >= 0 ? "+" : "") + p.change.toFixed(2) + "%"; e.className = p.change >= 0 ? "up" : "down"; }
  }
  function scheduleScan(delay) { clearTimeout(scanTimer); scanTimer = setTimeout(function () { scan(!!lastScan && lastScan.symbol === state.symbol && lastScan.timeframe === state.tf); }, delay); }
  function load() { msg("Chargement..."); headInfo(); clearScan(); clearDrawings(); orderDirty = false; lastScan = null; lastBarTime = null; fetchAndPaint().then(connectLive); scheduleScan(500); }

  // ---- duree restante avant la cloture de la bougie en cours ----
  var cdRefreshed = 0;
  function fmtCd(sec) {
    var d = Math.floor(sec / 86400), h = Math.floor(sec % 86400 / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60;
    var p = function (n) { return (n < 10 ? "0" : "") + n; };
    return (d ? d + "j " : "") + (h || d ? p(h) + ":" : "") + p(m) + ":" + p(s);
  }
  function tickCountdown() {
    if (!L.ohlc || !L.ohlc.time) return;
    var rem = L.ohlc.time + TF_SEC[state.tf] - Math.floor(Date.now() / 1000);
    var txt = rem > 0 ? fmtCd(rem) : "00:00";
    $("countdown").textContent = txt; $("scan-cd").textContent = "Bougie " + state.tf.toUpperCase() + " en cours : cloture dans " + txt + " (le scanner analyse les bougies deja cloturees)";
    if (rem <= 0 && Date.now() - cdRefreshed > 5000) { cdRefreshed = Date.now(); fetchAndPaint(); }
  }
  setInterval(tickCountdown, 1000);

  // ---- direct : WebSocket Gate (candlesticks + tickers) avec repli ----
  function setLive(ok, text) {
    $("livestate").textContent = text; $("foot-state").textContent = ok ? "En direct" : text;
    $("foot-dot").style.background = ok ? "#22c55e" : "#f59e0b";
  }
  function stopLive() { if (state.ws) { state.ws.onclose = null; try { state.ws.close(); } catch (e) {} state.ws = null; } state.wsOk = false; }
  function applyCandle(c) {
    candle.update(c); vol.update({ time: c.time, value: c.volume, color: c.close >= c.open ? "#26a69a66" : "#ef535066" });
    if (lastBarTime !== null && c.time !== lastBarTime) scheduleScan(1500);  // nouvelle bougie : on relance l'analyse
    lastBarTime = c.time;
    L.ohlc = c; L.vol = c.volume; $("last").textContent = f(c.close); paintLegend(L);
  }
  var paintQueued = false;
  function queuePaint() { if (paintQueued) return; paintQueued = true; requestAnimationFrame(function () { paintQueued = false; paintPairs(); headInfo(); }); }
  function watchedSymbols() {
    var set = {}; ALL.forEach(function (x) { set[x] = 1; }); set[state.symbol] = 1;
    document.querySelectorAll("#openpos tr[data-sym]").forEach(function (tr) { set[tr.dataset.sym] = 1; });
    return Object.keys(set).slice(0, 150);
  }
  function subscribeTickers() {
    if (state.ws && state.ws.readyState === 1) state.ws.send(JSON.stringify({ time: Math.floor(Date.now() / 1000), channel: "futures.tickers", event: "subscribe", payload: watchedSymbols() }));
  }
  function connectLive() {
    stopLive();
    var sym = state.symbol, tf = state.tf, ws;
    try { ws = new WebSocket(WS_URL); } catch (e) { setLive(false, "actualisation 10 s"); return; }
    state.ws = ws;
    ws.onopen = function () {
      var now = Math.floor(Date.now() / 1000);
      ws.send(JSON.stringify({ time: now, channel: "futures.candlesticks", event: "subscribe", payload: [TF_WS[tf], sym] }));
      subscribeTickers();
    };
    ws.onmessage = function (ev) {
      var m; try { m = JSON.parse(ev.data); } catch (e) { return; }
      if (m.event !== "update" || !Array.isArray(m.result)) return;
      if (m.channel === "futures.candlesticks") {
        state.wsOk = true; setLive(true, "● en direct (WebSocket Gate)");
        m.result.forEach(function (r) { applyCandle({ time: r.t, open: +r.o, high: +r.h, low: +r.l, close: +r.c, volume: +r.v }); });
      } else if (m.channel === "futures.tickers") {
        m.result.forEach(function (r) { if (r.contract && r.last) prices[r.contract] = { price: +r.last, change: +(r.change_percentage || 0) }; });
        queuePaint();
      }
    };
    ws.onerror = function () { if (!state.wsOk) setLive(false, "actualisation 10 s"); };
    ws.onclose = function () { state.wsOk = false; setLive(false, "reconnexion..."); setTimeout(function () { if (state.symbol === sym && state.tf === tf) connectLive(); }, 4000); };
    setTimeout(function () { if (state.ws === ws && !state.wsOk) setLive(false, "actualisation 10 s"); }, 8000);
  }
  setInterval(function () {  // indicateurs recalcules : 60 s si direct, 10 s sinon
    state.tick += 1; if (state.wsOk ? state.tick % 6 === 0 : true) fetchAndPaint();
  }, 10000);

  // ---- scanner ----
  function clearScan() { state.lines.forEach(function (l) { candle.removePriceLine(l); }); state.lines = []; markerScan = []; setMarkers(); }
  function addLine(price, color, title, style) { state.lines.push(candle.createPriceLine({ price: price, color: color, lineWidth: 2, lineStyle: style || 0, axisLabelVisible: true, title: title })); }
  function row(ico, l, v, cls) { return '<div class="lv"><span>' + ic(ico) + " " + l + '</span><b class="' + (cls || "") + '">' + v + "</b></div>"; }
  function pct(v) { return (v >= 0 ? "+" : "") + v.toFixed(2) + " %"; }
  function usdt(v) { return (v >= 0 ? "+" : "") + v.toFixed(2) + " USDT"; }
  function renderPotential() {
    var r = lastScan; if (!r || r.entry === undefined) { $("potential").innerHTML = ""; return; }
    var lev = Math.max(1, parseFloat($("in-lev").value) || 1), cap = Math.max(1, parseFloat($("in-cap").value) || 1), sign = r.direction === "LONG" ? 1 : -1;
    var risk = Math.abs(r.entry - r.stop_loss), h = '<div class="pot"><b>Gain / perte potentiels</b><small> (capital ' + cap + " USDT, levier x" + lev + ")</small>";
    r.take_profits.forEach(function (tp, i) {
      var g = sign * (tp - r.entry) / r.entry * 100;
      h += '<div class="lv"><span>TP' + (i + 1) + " : " + f(tp) + '</span><b class="up">' + pct(g) + " prix · " + pct(g * lev) + " marge · ≈ " + usdt(cap * g * lev / 100) + " · R " + (Math.abs(tp - r.entry) / risk).toFixed(1) + "</b></div>";
    });
    var l = sign * (r.stop_loss - r.entry) / r.entry * 100;
    h += '<div class="lv"><span>Stop Loss : ' + f(r.stop_loss) + '</span><b class="down">' + pct(l) + " prix · " + pct(l * lev) + " marge · ≈ " + usdt(cap * l * lev / 100) + "</b></div>";
    var liq = r.direction === "LONG" ? r.entry * (1 - 1 / lev) : r.entry * (1 + 1 / lev);
    h += "<small>Liquidation approx. " + f(liq) + " (marge isolee, hors frais). Hors frais et funding : le levier multiplie gains ET pertes.</small>";
    if (risk / r.entry >= 0.8 / lev) h += '<small class="down">ATTENTION : le Stop Loss est au-dela de la liquidation. Reduis le levier.</small>';
    h += '<small>Probabilite de reussite : cliquer sur « Reussite historique » (calculee sur des donnees reelles, jamais inventee).</small></div>';
    $("potential").innerHTML = h;
  }
  $("in-cap").oninput = function () { renderPotential(); orderCalc(); }; $("in-lev").oninput = function () { renderPotential(); orderCalc(); };
  function renderConfluence(r) {
    var h = "";
    if (r.confluence) {
      var c = r.confluence, cls = c.class === "fort" || c.class === "modere" ? "ok" : "warn";
      h += '<div class="pot"><b class="confl ' + cls + '">Confluence : ' + c.score + "/100 (" + c.class + ")</b>" +
        "<small>Technique " + c.parts.technique[0] + "/40 · Sentiment " + (c.parts.sentiment[0] === null ? "n/d" : c.parts.sentiment[0]) + "/25 · Fondamental : calcule par le bot (actualites)</small>" +
        (c.partial ? "<small>Score partiel (normalise) : " + c.missing.join(", ") + " non inclus dans le scanner live.</small>" : "") +
        (c.blocks.length ? '<small class="down">BLOCAGE : ' + c.blocks.join(" ; ") + "</small>" : "") + "</div>";
    }
    var s = r.sentiment;
    if (s) {
      h += '<div class="pot"><b>Sentiment du marche</b>' + (s.available ? "" : "<small>DONNEES INDISPONIBLES</small>") +
        s.reasons.map(function (x) { return "<small>" + x + "</small>"; }).join("") +
        (s.labels && s.labels.length ? '<div>' + s.labels.map(function (x) { return '<span class="chip">' + x + "</span>"; }).join("") + "</div>" : "") + "</div>";
    }
    $("confl").innerHTML = h;
  }
  var orderDirty = false, lastScanAt = 0, scanTimer = null, lastBarTime = null;
  function setOrder(vals, auto) {
    ["entry", "sl", "tp"].forEach(function (k) { var el = $("o-" + k); el.value = vals[k] === undefined || vals[k] === null ? "" : vals[k]; el.classList.toggle("auto", !!auto && vals[k] !== undefined && vals[k] !== null); });
    if (vals.dir) $("o-dir").value = vals.dir;
  }
  function orderCalc() {
    var e = parseFloat($("o-entry").value), sl = parseFloat($("o-sl").value), tp = parseFloat($("o-tp").value);
    var lev = Math.max(1, parseFloat($("in-lev").value) || 1), cap = Math.max(1, parseFloat($("in-cap").value) || 1), sign = $("o-dir").value === "LONG" ? 1 : -1;
    if (!(e > 0 && sl > 0 && tp > 0)) { $("o-calc").textContent = ""; return; }
    var g = sign * (tp - e) / e * 100, l = sign * (sl - e) / e * 100, risk = Math.abs(e - sl);
    var ok = (sign === 1 ? sl < e && tp > e : sl > e && tp < e);
    $("o-calc").innerHTML = ok ? 'Gain <b class="up">' + pct(g * lev) + " marge (≈ " + usdt(cap * g * lev / 100) + ')</b> · Perte <b class="down">' + pct(l * lev) + " (≈ " + usdt(cap * l * lev / 100) + ")</b> · R " + (Math.abs(tp - e) / risk).toFixed(2)
      : '<span class="down">SL / TP du mauvais cote de l\'entree.</span>';
  }
  function renderPrep(r, live) {
    var tpi = parseInt($("o-tpsel").value, 10);
    if (r.entry === undefined) {
      if (!orderDirty) { setOrder({ entry: null, sl: null, tp: null }, false); }
      $("order-src").textContent = "Aucun niveau : " + (r.message || "ATTENTE") + " (rien a pre-remplir)"; orderCalc(); return;
    }
    if (!orderDirty) {
      setOrder({ dir: r.direction, entry: r.entry, sl: r.stop_loss, tp: r.take_profits[tpi] }, true);
      $("order-src").textContent = "Rempli automatiquement depuis l'analyse " + r.timeframe.toUpperCase() + (r.entry_mode === "attente" ? " (entree LIMITE)" : "") + " — modifiable";
    } else { $("order-src").textContent = "Modifie manuellement (l'analyse continue en direct) — « Resynchroniser » pour reprendre ses niveaux"; }
    orderCalc();
  }
  ["o-dir", "o-entry", "o-sl", "o-tp"].forEach(function (id) { $(id).oninput = function () { orderDirty = true; orderCalc(); }; });
  $("o-tpsel").onchange = function () { if (lastScan && lastScan.take_profits) { $("o-tp").value = lastScan.take_profits[parseInt($("o-tpsel").value, 10)]; orderCalc(); } };
  $("btn-resync").onclick = function () { orderDirty = false; if (lastScan) renderPrep(lastScan); };
  $("btn-prep").onclick = function () {
    if (!($("o-entry").value && $("o-sl").value && $("o-tp").value)) { alert("Entree, Stop Loss et Take Profit sont necessaires."); return; }
    var form = document.createElement("form"); form.method = "post"; form.action = URLS.create.replace("ZZZ", state.symbol);
    var fields = { csrfmiddlewaretoken: csrf, direction: $("o-dir").value, entry: $("o-entry").value, stop_loss: $("o-sl").value, take_profit: $("o-tp").value,
      capital_usdt: $("in-cap").value, leverage: $("in-lev").value };
    Object.keys(fields).forEach(function (k) { var i = document.createElement("input"); i.type = "hidden"; i.name = k; i.value = fields[k]; form.appendChild(i); });
    document.body.appendChild(form); form.submit();
  };
  function qs() { return "?symbol=" + state.symbol + "&tf=" + state.tf + "&lev=" + encodeURIComponent($("in-lev").value) + "&cap=" + encodeURIComponent($("in-cap").value); }
  function refreshPhoto() {
    var im = $("aimg"); im.style.display = "block"; im.src = URLS.image + qs() + "&t=" + Date.now();
    $("aimg-open").href = URLS.image + qs(); $("aimg-open").setAttribute("download", "analyse_" + state.symbol + "_" + state.tf + ".png");
    $("photos-link").href = URLS.photos + "?symbol=" + state.symbol;
  }
  $("aimg-send").onclick = function () {
    var b = $("aimg-send"); b.disabled = true;
    fetch(URLS.imagesend + qs(), { method: "POST", headers: { "X-CSRFToken": csrf } }).then(function (r) { return r.json().then(function (j) { alert(r.ok ? "Photo envoyee sur Telegram" : (j.error || "Erreur")); }); }).finally(function () { b.disabled = false; });
  };
  function drawIct(r) {
    var z = r.ict; if (!z) return;
    var long = z.direction === "LONG";
    addLine(z.zone[1], "#a78bfa", long ? "OTE 62%" : "OTE 79%", 2); addLine(z.zone[0], "#a78bfa", long ? "OTE 79%" : "OTE 62%", 2);
    addLine(z.equilibrium, "#64748b", "50% (equilibre)", 2); addLine(z.invalidation, "#fb923c", "Invalidation", 2);
  }
  function scan(silent) {
    if (!silent) { $("signal").className = "signal wait"; $("signal").innerHTML = "<b>Analyse...</b>"; $("bt").innerHTML = ""; }
    var q = "&lev=" + encodeURIComponent($("in-lev").value) + "&cap=" + encodeURIComponent($("in-cap").value);
    api(URLS.scan + "?symbol=" + state.symbol + "&tf=" + state.tf + q).then(function (r) {
      clearScan(); lastScan = r;
      var cls = r.direction === "LONG" ? "long" : r.direction === "SHORT" ? "short" : "wait";
      var sc = r.score !== undefined ? " · Score : " + r.score + "/" + r.max_score + " (" + Math.round(100 * r.score / r.max_score) + " %)" : "";
      var lim = r.status === "signal_limite" ? " (ordre limite)" : "";
      $("signal").className = "signal " + cls;
      $("signal").innerHTML = "<b>" + (r.direction === "ATTENTE" ? ic("circle-x") + " ATTENTE" : ic("circle-check") + " Signal : " + r.direction + lim) + "</b><small>" + (r.message || "") + sc + "</small>";
      var arrow = r.trend && r.trend.indexOf("Haussi") === 0 ? " ↗" : r.trend && r.trend.indexOf("Baissi") === 0 ? " ↘" : "";
      $("trend").textContent = "Tendance : " + (r.trend || "—") + arrow + (r.htf ? " · " + r.htf.toUpperCase() + " : " + ({ UP: "haussiere", DOWN: "baissiere", RANGE: "range" }[r.htf_trend] || "indeterminee") : "");
      var h = row("coins", "Crypto", r.symbol.replace("_", "/")) + row("clock", "Timeframe", r.timeframe);
      if (r.entry !== undefined) {
        h += row("target", r.entry_mode === "attente" ? "Entree LIMITE (zone OTE)" : "Point d'Entree", f(r.entry) + " USDT", "up") +
          row("circle-check", "Take Profit 1", f(r.take_profits[0]) + " USDT", "up") + row("circle-check", "Take Profit 2", f(r.take_profits[1]) + " USDT", "up") +
          row("circle-check", "Take Profit 3", f(r.take_profits[2]) + " USDT", "up") + row("octagon-x", "Stop Loss", f(r.stop_loss) + " USDT", "down");
        if (r.aligned_strategies !== undefined) h += row("chart-candlestick", "Strategies alignees", r.aligned_strategies + " / 10");
        addLine(r.entry, "#22c55e", "Entree : " + f(r.entry)); addLine(r.stop_loss, "#ef4444", "SL : " + f(r.stop_loss));
        r.take_profits.forEach(function (p, i) { addLine(p, "#4ade80", "TP" + (i + 1) + " : " + f(p)); });
        drawIct(r);
        api(URLS.candles + "?symbol=" + state.symbol + "&tf=" + state.tf).then(function (d) {
          var c = d.candles[d.candles.length - 2] || d.candles[d.candles.length - 1], long = r.direction === "LONG";
          markerScan = [{ time: c.time, position: long ? "belowBar" : "aboveBar", color: long ? "#22c55e" : "#ef4444", shape: long ? "arrowUp" : "arrowDown", text: r.direction }]; setMarkers();
        });
      }
      $("levels").innerHTML = h;
      var z = r.ict;
      $("ict").innerHTML = z ? '<div class="ictbox"><b>Setup ICT · grade ' + z.grade + " (" + z.score + "/" + z.max + ")</b><div>" +
        z.confluences.map(function (x) { return '<span class="chip">' + x + "</span>"; }).join("") + "</div><small>" + z.reasons.slice(0, 4).join("<br>") + "</small></div>" : "";
      renderPotential(); renderConfluence(r); renderPrep(r); refreshPhoto(); lastScanAt = Date.now();
      $("confirms").innerHTML = (r.confirmations || []).map(function (c) {
        return '<div class="conf"><span>' + c.name + " : " + (c.value === null ? "—" : c.value) + "</span><span>" + c.verdict + "</span></div>";
      }).join("");
      icons();
      $("scan-time").textContent = "Calcule le " + r.timestamp.replace("T", " ").replace("+00:00", " UTC") + " · bougies cloturees · " + r.market;
    }).catch(function (e) { if (!silent) { $("signal").className = "signal wait"; $("signal").innerHTML = "<b>Indisponible</b><small>" + e.message + "</small>"; } else { $("live-badge").textContent = "Mise a jour impossible : " + e.message; } });
  }
  $("btn-backtest").onclick = function () {
    $("bt").innerHTML = "<small>Calcul sur l'historique reel... (quelques secondes)</small>";
    api(URLS.backtest + "?symbol=" + state.symbol + "&tf=" + state.tf).then(function (b) {
      if (!b.trades) { $("bt").innerHTML = '<div class="pot"><small>Aucun trade conclu sur ' + b.candles + " bougies : pas de statistique. " + b.warning + "</small></div>"; return; }
      $("bt").innerHTML = '<div class="pot"><b>Historique reel de cette strategie</b><small> (' + b.candles + " bougies " + b.timeframe + ")</small>" +
        '<div class="lv"><span>Trades conclus</span><b>' + b.trades + "</b></div>" +
        '<div class="lv"><span>TP1 atteint avant le SL (reussite)</span><b class="up">' + b.rate_tp1 + " %</b></div>" +
        '<div class="lv"><span>SL touche avant TP1 (echec)</span><b class="down">' + b.fail_rate + " %</b></div>" +
        '<div class="lv"><span>TP2 atteint avant le SL</span><b>' + b.rate_tp2 + " %</b></div>" +
        '<div class="lv"><span>Gain moyen (sortie TP1 / TP2)</span><b>' + b.avg_r_tp1 + " R / " + b.avg_r_tp2 + " R</b></div>" +
        "<small" + (b.reliable ? "" : ' class="down"') + ">" + b.warning + "</small></div>";
    }).catch(function (e) { $("bt").innerHTML = "<small class='down'>" + e.message + "</small>"; });
  };
  var autoTimer = null;
  $("auto").onchange = function () { if (autoTimer) { clearInterval(autoTimer); autoTimer = null; } if ($("auto").checked) { scan(false); autoTimer = setInterval(function () { scan(true); }, 60000); } };

  // ---- outils de dessin (ligne horizontale, ligne de tendance, annuler / retablir) ----
  var tool = null, pending = null, drawings = [], redo = [];
  function toolUI() { $("tool-h").classList.toggle("on", tool === "h"); $("tool-trend").classList.toggle("on", tool === "t"); }
  function addH(price) { return candle.createPriceLine({ price: price, color: "#facc15", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "H" }); }
  function addT(a, b) {
    var s = chart.addLineSeries({ color: "#facc15", lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
    s.setData([a, b].sort(function (x, y) { return x.time - y.time; }).map(function (p) { return { time: p.time, value: p.price }; })); return s;
  }
  function place(d) { d.ref = d.type === "h" ? addH(d.price) : addT(d.a, d.b); drawings.push(d); }
  function removeDraw(d) { if (d.type === "h") candle.removePriceLine(d.ref); else chart.removeSeries(d.ref); }
  function clearDrawings() { drawings.forEach(removeDraw); drawings = []; redo = []; pending = null; tool = null; toolUI(); }
  chart.subscribeClick(function (p) {
    if (!tool || !p.point || !p.time) return;
    var price = candle.coordinateToPrice(p.point.y); if (price === null) return;
    if (tool === "h") { place({ type: "h", price: price }); redo = []; tool = null; toolUI(); }
    else if (!pending) { pending = { time: p.time, price: price }; msg("Clique le 2e point de la ligne de tendance"); }
    else if (p.time !== pending.time) { place({ type: "t", a: pending, b: { time: p.time, price: price } }); redo = []; pending = null; tool = null; msg(""); toolUI(); }
  });
  $("tool-h").onclick = function () { tool = tool === "h" ? null : "h"; pending = null; toolUI(); msg(tool ? "Clique sur le graphique pour placer la ligne" : ""); };
  $("tool-trend").onclick = function () { tool = tool === "t" ? null : "t"; pending = null; toolUI(); msg(tool ? "Clique le 1er point de la ligne de tendance" : ""); };
  $("btn-undo").onclick = function () { var d = drawings.pop(); if (d) { removeDraw(d); redo.push(d); } };
  $("btn-redo").onclick = function () { var d = redo.pop(); if (d) place(d); };

  // ---- logos des cryptos (CDN, avec repli puis pastille de lettres) ----
  var LOGO_URL = cfg.dataset.logo;
  var LOGO_SRC = [
    function (b) { return LOGO_URL.replace("ZZZ", b.toUpperCase()); },
    function (b) { return "https://cdn.jsdelivr.net/gh/spothq/cryptocurrency-icons@master/128/color/" + b + ".png"; },
    function (b) { return "https://assets.coincap.io/assets/icons/" + b + "@2x.png"; }
  ];
  function logoBase(sym) { return sym.split("_")[0].toLowerCase().replace(/^(1000000|100000|10000|1000|1m)/, ""); }
  function hue(b) { var h = 0; for (var i = 0; i < b.length; i++) h = (h * 31 + b.charCodeAt(i)) % 360; return "hsl(" + h + ",55%,40%)"; }
  window.kpsLogoErr = function (img) {
    var i = (+img.dataset.i || 0) + 1;
    if (i < LOGO_SRC.length) { img.dataset.i = i; img.src = LOGO_SRC[i](img.dataset.b); return; }
    var gold = /^xau/.test(img.dataset.b), s = document.createElement("i"); s.className = "coin" + (gold ? " gold" : "");
    if (!gold) s.style.background = hue(img.dataset.b);
    s.textContent = gold ? "Au" : img.dataset.b.slice(0, 3).toUpperCase(); img.replaceWith(s);
  };
  function logoHTML(sym) {
    var b = logoBase(sym);
    return '<img class="coinimg" loading="lazy" alt="" data-b="' + b + '" data-i="0" src="' + LOGO_SRC[0](b) + '" onerror="kpsLogoErr(this)">';
  }

  // ---- liste de TOUTES les paires / prix / positions ----
  var favs = []; try { favs = JSON.parse(localStorage.getItem("kps_favs") || "[]"); } catch (e) {}
  var allPairs = [], extras = [], tab = "crypto";
  function isGold(sym) { return extras.indexOf(sym) >= 0 || /^xau/.test(logoBase(sym)); }
  function pairRow(sym) {
    return '<div class="pair" data-sym="' + sym + '">' + logoHTML(sym) + "<span>" + sym.replace("_USDT", "") + '/USDT</span><b class="px">—</b><em class="chg">—</em><u class="star">☆</u></div>';
  }
  function renderPairs() {
    var q = $("search").value.toUpperCase().trim(), list;
    if (!allPairs.length) { return; }
    if (tab === "fav") list = favs.slice();
    else if (tab === "gold") list = allPairs.map(function (p) { return p.symbol; }).filter(isGold);
    else list = allPairs.map(function (p) { return p.symbol; }).filter(function (s) { return !isGold(s); });
    if (q) list = list.filter(function (s) { return s.indexOf(q) >= 0; });
    var shown = list.slice(0, 80);
    if (shown.indexOf(state.symbol) < 0 && !q && tab === "crypto") shown.unshift(state.symbol);
    $("pairlist").innerHTML = shown.length ? shown.map(pairRow).join("") : "<small>Aucune paire.</small>";
    ALL = shown.slice(); paintPairs(); subscribeTickers();
  }
  function paintPairs() {
    document.querySelectorAll(".pair").forEach(function (el) {
      var s = el.dataset.sym, p = prices[s];
      el.classList.toggle("sel", s === state.symbol);
      el.querySelector(".star").textContent = favs.indexOf(s) >= 0 ? "★" : "☆";
      if (p) { el.querySelector(".px").textContent = f(p.price); var c = el.querySelector(".chg"); c.textContent = (p.change >= 0 ? "+" : "") + p.change.toFixed(2) + "%"; c.className = "chg " + (p.change >= 0 ? "up" : "down"); }
    });
    document.querySelectorAll("#openpos tr[data-sym]").forEach(function (tr) {
      var p = prices[tr.dataset.sym]; if (!p) return;
      var e = parseFloat(tr.dataset.entry), lev = parseFloat(tr.dataset.lev), sign = tr.dataset.dir === "LONG" ? 1 : -1;
      var pl = sign * (p.price - e) / e * lev * 100;
      tr.querySelector(".cur").textContent = f(p.price); var c = tr.querySelector(".pl"); c.textContent = (pl >= 0 ? "+" : "") + pl.toFixed(2) + "%"; c.className = "pl " + (pl >= 0 ? "up" : "down");
    });
  }
  function loadPrices() { api(URLS.prices).then(function (d) { for (var k in d) prices[k] = d[k]; paintPairs(); headInfo(); }).catch(function () {}); }
  function loadContracts() {
    api(URLS.contracts).then(function (d) {
      allPairs = d.pairs; extras = d.extras || [];
      d.pairs.forEach(function (p) { prices[p.symbol] = { price: p.price, change: p.change }; });
      renderPairs(); headInfo();
    }).catch(function (e) { msg(e.message); });
  }
  document.querySelectorAll(".tab").forEach(function (b) { b.onclick = function () {
    document.querySelectorAll(".tab").forEach(function (x) { x.classList.remove("on"); }); b.classList.add("on"); tab = b.dataset.tab; renderPairs(); }; });
  $("search").oninput = renderPairs;
  $("pairlist").onclick = function (ev) {
    var el = ev.target.closest(".pair"); if (!el) return;
    if (ev.target.classList.contains("star")) {
      var i = favs.indexOf(el.dataset.sym); if (i >= 0) favs.splice(i, 1); else favs.push(el.dataset.sym);
      try { localStorage.setItem("kps_favs", JSON.stringify(favs)); } catch (e) {} paintPairs(); if (tab === "fav") renderPairs(); return;
    }
    state.symbol = el.dataset.sym; paintPairs(); load();
  };
  document.querySelectorAll("#tfs button").forEach(function (b) { b.onclick = function () {
    document.querySelectorAll("#tfs button").forEach(function (x) { x.classList.remove("on"); }); b.classList.add("on"); state.tf = b.dataset.tf; load(); }; });

  // ---- indicateurs affichables ----
  document.querySelectorAll("[data-ind]").forEach(function (cb) { cb.onchange = function () {
    var on = cb.checked, k = cb.dataset.ind;
    if (k === "ema") Object.keys(ema).forEach(function (x) { ema[x].applyOptions({ visible: on }); });
    if (k === "bb") Object.keys(bb).forEach(function (x) { bb[x].applyOptions({ visible: on }); });
    if (k === "vwap") vwap.applyOptions({ visible: on });
    if (k === "vol") vol.applyOptions({ visible: on });
    if (k === "fib") { fibOn = on; drawFib(); }
    if (k === "smc") { smcOn = on; smcMarkers(); drawSmc(); }
    if (k === "ma") { maOn = on; Object.keys(ma).forEach(function (x) { ma[x].applyOptions({ visible: on }); }); paintLegend(L); }
    ["rsi", "macd", "stoch"].forEach(function (s) { if (k === s) { $(s).style.display = on ? "" : "none"; $("lbl-" + s).style.display = on ? "" : "none"; resizeAll(); } });
  }; });

  // ---- barre d'outils ----
  $("btn-scan").onclick = function () { scan(false); };
  $("fab-scan").onclick = function () { scan(false); $("scanpanel").scrollIntoView({ behavior: "smooth", block: "start" }); };
  $("btn-refresh").onclick = function () { fetchAndPaint(); loadPrices(); loadPerf(); loadAccount(); scan(false); };
  $("btn-shot").onclick = function () { var c = chart.takeScreenshot(), a = document.createElement("a"); a.href = c.toDataURL("image/png"); a.download = state.symbol + "_" + state.tf + ".png"; a.click(); };
  function zoom(factor) {
    var r = chart.timeScale().getVisibleLogicalRange(); if (!r) return;
    var w = (r.to - r.from) * factor; if (w < 8) w = 8;
    chart.timeScale().setVisibleLogicalRange({ from: r.to - w, to: r.to });
  }
  $("btn-zin").onclick = function () { zoom(0.6); };
  $("btn-zout").onclick = function () { zoom(1 / 0.6); };
  $("btn-fit").onclick = function () { chart.timeScale().fitContent(); };
  $("btn-live").onclick = function () { chart.timeScale().scrollToRealTime(); };
  function maximize(on) {
    document.querySelector(".chartbox").classList.toggle("maxi", on); document.body.classList.toggle("nomaxscroll", on);
    $("btn-full").innerHTML = ic(on ? "minimize" : "maximize"); icons(); setTimeout(resizeAll, 120);
  }
  $("btn-full").onclick = function () { maximize(!document.querySelector(".chartbox").classList.contains("maxi")); };
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") maximize(false); });

  // ---- telephone : reprise du direct au retour au premier plan, ecran allume ----
  var wake = null;
  function keepAwake() { try { if (navigator.wakeLock) navigator.wakeLock.request("screen").then(function (w) { wake = w; }).catch(function () {}); } catch (e) {} }
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") { keepAwake(); fetchAndPaint().then(connectLive); loadPrices(); }
  });
  keepAwake();

  // ---- compte, urgence, fermeture, performance ----
  function paintEmergency(on) { var b = $("btn-emergency"); b.classList.toggle("active", on); b.textContent = on ? "URGENCE ACTIVE (desactiver)" : "ARRET D'URGENCE"; }
  paintEmergency(cfg.dataset.emergency === "1");
  $("btn-emergency").onclick = function () {
    if (!confirm("Basculer l'arret d'urgence ? Il bloque toute NOUVELLE position (les positions existantes sont conservees).")) return;
    api(URLS.emergency, { method: "POST", headers: { "X-CSRFToken": csrf } }).then(function (d) { paintEmergency(d.emergency); }).catch(function (e) { msg(e.message); });
  };
  document.querySelectorAll(".btn-close").forEach(function (b) { b.onclick = function () {
    if (!confirm("Fermer cette position au marche ?")) return;
    var body = new URLSearchParams();
    if (MODE === "REAL") { var t = prompt("ARGENT REEL : tape REAL pour confirmer"); if (t === null) return; body.append("real_confirm", t); }
    api(CLOSE_URL.replace("/0/", "/" + b.dataset.id + "/"), { method: "POST", headers: { "X-CSRFToken": csrf }, body: body })
      .then(function (r) { alert("Fermeture envoyee a Gate. Statut : " + r.status + (r.net_pnl !== null ? " | PNL " + r.net_pnl.toFixed(2) + " USDT" : "")); location.reload(); })
      .catch(function (e) { alert(e.message); });
  }; });
  function loadAccount() {
    api(URLS.account).then(function (a) {
      $("acc-balance").textContent = a.balance ? a.balance.total.toFixed(2) + " USDT" : "indisponible";
      var p = $("acc-pnl"); p.textContent = (a.pnl_24h >= 0 ? "+" : "") + a.pnl_24h.toFixed(2) + " USDT"; p.className = a.pnl_24h >= 0 ? "up" : "down";
      var base = a.balance ? a.balance.total - a.pnl_24h : 0;
      $("acc-pnl-sub").textContent = base > 0 ? (a.pnl_24h >= 0 ? "+" : "") + (100 * a.pnl_24h / base).toFixed(2) + " %" : "";
      $("acc-open").textContent = a.open_positions; paintEmergency(a.emergency);
    }).catch(function () {});
  }
  var perfChart = LightweightCharts.createChart($("perfchart"), { height: 90, layout: { background: { color: "#0a1530" }, textColor: "#cbd5e1" },
    grid: { vertLines: { visible: false }, horzLines: { visible: false } }, rightPriceScale: { visible: false }, timeScale: { visible: false },
    handleScroll: false, handleScale: false, crosshair: { mode: 0 } });
  var perfSeries = perfChart.addAreaSeries({ lineColor: "#22c55e", topColor: "#22c55e66", bottomColor: "#22c55e00" });
  function loadPerf() {
    api(URLS.performance + "?days=" + $("perf-days").value).then(function (r) {
      var e = $("perf-pnl"); e.textContent = (r.pnl >= 0 ? "+" : "") + r.pnl.toFixed(2) + " USDT"; e.className = "big " + (r.pnl >= 0 ? "up" : "down");
      $("perf-rate").textContent = r.rate === null ? "donnees insuffisantes" : r.rate + " %";
      $("perf-wins").textContent = r.n ? r.wins + " / " + r.n : "—";
      perfSeries.setData(r.points); perfChart.timeScale().fitContent();
    }).catch(function () {});
  }
  $("perf-days").onchange = loadPerf;

  icons(); paintLegend({});
  setInterval(function () {   // analyse en direct : toutes les 30 s tant que la page est visible
    if (document.visibilityState === "visible" && Date.now() - lastScanAt > 29000) scan(true);
    var sec = lastScanAt ? Math.round((Date.now() - lastScanAt) / 1000) : null;
    $("live-badge").textContent = sec === null ? "Analyse en cours..." : "● Analyse reelle en direct · mise a jour il y a " + sec + " s (bougies cloturees, Gate Futures USDT)";
  }, 5000);
  load(); loadContracts(); loadPrices(); loadAccount(); loadPerf(); resizeAll();
  setInterval(loadPrices, 10000); setInterval(loadContracts, 300000); setInterval(loadAccount, 30000); setInterval(loadPerf, 60000);
})();
