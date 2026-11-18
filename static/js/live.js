(function () {
  "use strict";
  var cfg = document.getElementById("cfg");
  var URLS = JSON.parse(cfg.dataset.urls), WS_URL = cfg.dataset.ws, MODE = cfg.dataset.mode, CLOSE_URL = cfg.dataset.close;
  var TF_WS = { "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "4h": "4h", "8h": "8h", "1d": "1d", "1w": "7d" };
  var TF_SEC = { "1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "8h": 28800, "1d": 86400, "1w": 604800 };
  var state = { symbol: cfg.dataset.symbol || "BTC_USDT", tf: "1h", ws: null, wsOk: false, lines: [], fibLines: [], tick: 0 };
  var csrf = document.querySelector("input[name=csrfmiddlewaretoken]").value;
  var $ = function (id) { return document.getElementById(id); };
  var prices = {}, L = {}, fibData = null, fibOn = true;
  var ALL = Array.prototype.map.call(document.querySelectorAll(".pair"), function (e) { return e.dataset.sym; });

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
    rsi.setData(d.rsi); mLine.setData(d.macd); mSig.setData(d.signal);
    mHist.setData(d.hist.map(function (h) { return { time: h.time, value: h.value, color: h.value >= 0 ? "#26a69a" : "#ef5350" }; }));
    sK.setData(d.stoch_k); sD.setData(d.stoch_d);
    var c = last(d.candles);
    L = { ohlc: c, vol: c.volume, e9: (last(d.ema9) || {}).value, e21: (last(d.ema21) || {}).value, e50: (last(d.ema50) || {}).value, e200: (last(d.ema200) || {}).value,
      rsi: (last(d.rsi) || {}).value, macd: (last(d.macd) || {}).value, sig: (last(d.signal) || {}).value, hist: (last(d.hist) || {}).value,
      sk: (last(d.stoch_k) || {}).value, sd: (last(d.stoch_d) || {}).value };
    $("last").textContent = f(c.close); paintLegend(L);
    fibData = d.fib; drawFib();
  }
  function fetchAndPaint() {
    return api(URLS.candles + "?symbol=" + state.symbol + "&tf=" + state.tf).then(function (d) { paint(d); msg(""); }).catch(function (e) { msg(e.message); });
  }
  function headInfo() {
    $("title").textContent = state.symbol.replace("_", "/") + " · " + state.tf.toUpperCase();
    $("head-coin").textContent = state.symbol.slice(0, 1);
    var p = prices[state.symbol];
    if (p) { var e = $("head-chg"); e.textContent = (p.change >= 0 ? "+" : "") + p.change.toFixed(2) + "%"; e.className = p.change >= 0 ? "up" : "down"; }
  }
  function load() { msg("Chargement..."); headInfo(); clearScan(); clearDrawings(); fetchAndPaint().then(connectLive); }

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
    L.ohlc = c; L.vol = c.volume; $("last").textContent = f(c.close); paintLegend(L);
  }
  var paintQueued = false;
  function queuePaint() { if (paintQueued) return; paintQueued = true; requestAnimationFrame(function () { paintQueued = false; paintPairs(); headInfo(); }); }
  function connectLive() {
    stopLive();
    var sym = state.symbol, tf = state.tf, ws;
    try { ws = new WebSocket(WS_URL); } catch (e) { setLive(false, "actualisation 10 s"); return; }
    state.ws = ws;
    ws.onopen = function () {
      var now = Math.floor(Date.now() / 1000);
      ws.send(JSON.stringify({ time: now, channel: "futures.candlesticks", event: "subscribe", payload: [TF_WS[tf], sym] }));
      ws.send(JSON.stringify({ time: now, channel: "futures.tickers", event: "subscribe", payload: ALL }));
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
  function clearScan() { state.lines.forEach(function (l) { candle.removePriceLine(l); }); state.lines = []; candle.setMarkers([]); }
  function addLine(price, color, title) { state.lines.push(candle.createPriceLine({ price: price, color: color, lineWidth: 2, lineStyle: 0, axisLabelVisible: true, title: title })); }
  function row(ico, l, v, cls) { return '<div class="lv"><span>' + ic(ico) + " " + l + '</span><b class="' + (cls || "") + '">' + v + "</b></div>"; }
  function scan() {
    $("signal").className = "signal wait"; $("signal").innerHTML = "<b>Analyse...</b>";
    api(URLS.scan + "?symbol=" + state.symbol + "&tf=" + state.tf).then(function (r) {
      clearScan();
      var cls = r.direction === "LONG" ? "long" : r.direction === "SHORT" ? "short" : "wait";
      var sc = r.score !== undefined ? " · Score : " + r.score + "/" + r.max_score + " (" + Math.round(100 * r.score / r.max_score) + " %)" : "";
      $("signal").className = "signal " + cls;
      $("signal").innerHTML = "<b>" + (r.direction === "ATTENTE" ? ic("circle-x") + " ATTENTE" : ic("circle-check") + " Signal : " + r.direction) + "</b><small>" + (r.message || "") + sc + "</small>";
      var arrow = r.trend && r.trend.indexOf("Haussi") === 0 ? " ↗" : r.trend && r.trend.indexOf("Baissi") === 0 ? " ↘" : "";
      $("trend").textContent = "Tendance : " + (r.trend || "—") + arrow;
      var h = row("coins", "Crypto", r.symbol.replace("_", "/")) + row("clock", "Timeframe", r.timeframe);
      if (r.status === "signal") {
        h += row("target", "Point d'Entree", f(r.entry) + " USDT", "up") + row("circle-check", "Take Profit 1", f(r.take_profits[0]) + " USDT", "up") +
          row("circle-check", "Take Profit 2", f(r.take_profits[1]) + " USDT", "up") + row("circle-check", "Take Profit 3", f(r.take_profits[2]) + " USDT", "up") +
          row("octagon-x", "Stop Loss", f(r.stop_loss) + " USDT", "down");
        addLine(r.entry, "#22c55e", "Entree : " + f(r.entry)); addLine(r.stop_loss, "#ef4444", "SL : " + f(r.stop_loss));
        r.take_profits.forEach(function (p, i) { addLine(p, "#4ade80", "TP" + (i + 1) + " : " + f(p)); });
        api(URLS.candles + "?symbol=" + state.symbol + "&tf=" + state.tf).then(function (d) {
          var c = d.candles[d.candles.length - 2] || d.candles[d.candles.length - 1], long = r.direction === "LONG";
          candle.setMarkers([{ time: c.time, position: long ? "belowBar" : "aboveBar", color: long ? "#22c55e" : "#ef4444", shape: long ? "arrowUp" : "arrowDown", text: r.direction }]);
        });
      }
      $("levels").innerHTML = h;
      $("confirms").innerHTML = (r.confirmations || []).map(function (c) {
        return '<div class="conf"><span>' + c.name + " : " + (c.value === null ? "—" : c.value) + "</span><span>" + c.verdict + "</span></div>";
      }).join("");
      icons();
      $("scan-time").textContent = "Calcule le " + r.timestamp.replace("T", " ").replace("+00:00", " UTC") + " · bougies cloturees · " + r.market;
    }).catch(function (e) { $("signal").className = "signal wait"; $("signal").innerHTML = "<b>Indisponible</b><small>" + e.message + "</small>"; });
  }
  var autoTimer = null;
  $("auto").onchange = function () { if (autoTimer) { clearInterval(autoTimer); autoTimer = null; } if ($("auto").checked) { scan(); autoTimer = setInterval(scan, 60000); } };

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

  // ---- liste des paires / prix / positions ----
  var favs = []; try { favs = JSON.parse(localStorage.getItem("kps_favs") || "[]"); } catch (e) {}
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
  var tab = "crypto";
  function filterPairs() {
    var q = $("search").value.toUpperCase();
    document.querySelectorAll(".pair").forEach(function (el) {
      var ok = el.dataset.sym.indexOf(q) >= 0 && (tab === "fav" ? favs.indexOf(el.dataset.sym) >= 0 : el.dataset.group === tab);
      el.style.display = ok ? "" : "none";
    });
  }
  document.querySelectorAll(".tab").forEach(function (b) { b.onclick = function () {
    document.querySelectorAll(".tab").forEach(function (x) { x.classList.remove("on"); }); b.classList.add("on"); tab = b.dataset.tab; filterPairs(); }; });
  $("search").oninput = filterPairs;
  document.querySelectorAll(".pair").forEach(function (el) {
    el.onclick = function (ev) {
      if (ev.target.classList.contains("star")) {
        var i = favs.indexOf(el.dataset.sym); if (i >= 0) favs.splice(i, 1); else favs.push(el.dataset.sym);
        try { localStorage.setItem("kps_favs", JSON.stringify(favs)); } catch (e) {} paintPairs(); filterPairs(); return;
      }
      state.symbol = el.dataset.sym; paintPairs(); load();
    };
  });
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
    ["rsi", "macd", "stoch"].forEach(function (s) { if (k === s) { $(s).style.display = on ? "" : "none"; $("lbl-" + s).style.display = on ? "" : "none"; resizeAll(); } });
  }; });

  // ---- barre d'outils ----
  $("btn-scan").onclick = scan;
  $("fab-scan").onclick = function () { scan(); $("scanpanel").scrollIntoView({ behavior: "smooth", block: "start" }); };
  $("btn-refresh").onclick = function () { fetchAndPaint(); loadPrices(); loadPerf(); loadAccount(); scan(); };
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
  load(); loadPrices(); loadAccount(); loadPerf(); filterPairs(); resizeAll();
  setInterval(loadPrices, 10000); setInterval(loadAccount, 30000); setInterval(loadPerf, 60000);
})();
