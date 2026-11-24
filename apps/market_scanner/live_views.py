import re
import time
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.audit.models import SystemFlag, emergency_active
from apps.market_data import logo_store
from apps.market_data.gate_client import GateAPIError, GateClient
from apps.notifications import telegram
from apps.decision_engine.confluence import confluence
from apps.sentiment_analysis import engine as sentiment_engine
from apps.sentiment_analysis.sources import SentimentError, fetch_fear_greed
from apps.smart_money import overlays
from apps.technical_analysis import bollinger, indicators as ind
from apps.trade_approval.models import TradeProposal
from apps.trade_history.chart import render_png
from apps.trading import autorun
from apps.trading.factory import trader_from_settings
from apps.trading.gate_private import GateTradeError

from apps.trading.sync import sync_open_trades

from .perf import performance
from .backtest import TF_SEC, run as run_backtest

try:
    from apps.trade_history.analysis_image import render_analysis
except ImportError:  # Pillow absent
    def render_analysis(*a, **k):
        raise ImportError("Pillow requis pour la photo d'analyse")
from .scan import scan as run_scan

TF_MAP = {"1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "4h": "4h", "8h": "8h", "1d": "1d", "1w": "7d"}
SYMBOL_RE = re.compile(r"^[A-Z0-9]{2,20}_USDT$")
HTF_MAP = {"1m": "15m", "5m": "1h", "15m": "4h", "30m": "4h", "1h": "4h", "4h": "1d", "8h": "1d", "1d": "1w", "1w": None}
_bt_cache, _contracts_cache, _lv_cache = {}, {"t": 0, "data": []}, {}
_fng_cache = {"t": 0.0, "v": None}
_an_cache = {}


def _pairs():
    crypto = [f"{b}_USDT" for b in settings_watchlist()]
    return crypto, list(settings.KPS_EXTRA_SYMBOLS)


def settings_watchlist():
    return settings.DEFAULT_WATCHLIST


def _params(request):
    sym, tf = request.GET.get("symbol", "BTC_USDT"), request.GET.get("tf", "1h")
    if not SYMBOL_RE.match(sym) or tf not in TF_MAP:
        return None, None
    return sym, tf


def _err(msg, status=502):
    return JsonResponse({"error": msg}, status=status)


def _series(times, values):
    return [{"time": t, "value": v} for t, v in zip(times, values) if v is not None]


@login_required
def live(request):
    crypto, extra = _pairs()
    M = settings.TRADING_MODE
    open_pos = TradeProposal.objects.filter(exec_status="open", mode=M)
    closed = list(TradeProposal.objects.filter(exec_status="closed", mode=M, net_pnl__isnull=False).order_by("-closed_at")[:200])
    wins = sum(1 for t in closed if t.net_pnl > 0)
    stats = {"n": len(closed), "wins": wins, "pnl": sum(t.net_pnl for t in closed),
             "rate": round(100 * wins / len(closed), 1) if closed else None}
    return render(request, "live.html", {
        "symbol": request.GET.get("symbol", "BTC_USDT"), "crypto": crypto, "gold": extra,
        "open_positions": open_pos, "recent_closed": closed[:5], "stats": stats,
        "default_capital": settings.KPS_DEFAULT_CAPITAL_USDT, "default_leverage": settings.KPS_DEFAULT_LEVERAGE,
        "mode": settings.TRADING_MODE, "emergency": emergency_active(), "ws_url": "wss://fx-ws.gateio.ws/v4/ws/usdt"})


def _levels(sym):
    """Extremes 24 h et jour precedent (bougies 1H reelles), en cache 5 min : meme niveaux pour tous les timeframes."""
    hit = _lv_cache.get(sym)
    if hit and time.time() - hit[0] < 300:
        return hit[1]
    try:
        lv = overlays.compute_levels(ind.normalize_candles(GateClient().candlesticks(sym, "1h", 120)))
    except (GateAPIError, ValueError, KeyError):
        lv = None
    _lv_cache[sym] = (time.time(), lv)
    return lv


@login_required
def candles_api(request):
    sym, tf = _params(request)
    if not sym:
        return _err("Parametres invalides", 400)
    try:
        c = ind.normalize_candles(GateClient().candlesticks(sym, TF_MAP[tf], 300))
    except (GateAPIError, ValueError, KeyError) as e:
        return _err(f"DONNEES INDISPONIBLES : {e}")
    t = [x["t"] for x in c]
    closes = [x["c"] for x in c]
    bands = bollinger.compute_bands(closes)
    m = ind.macd(closes)
    out = {
        "symbol": sym, "timeframe": tf, "market": "Gate Futures USDT",
        "candles": [{"time": x["t"], "open": x["o"], "high": x["h"], "low": x["l"], "close": x["c"], "volume": x["v"]} for x in c],
        "ema9": _series(t, ind.ema(closes, 9)), "ema21": _series(t, ind.ema(closes, 21)),
        "ema50": _series(t, ind.ema(closes, 50)), "ema200": _series(t, ind.ema(closes, 200)),
        "bb_upper": _series(t, [b and b["upper"] for b in bands]), "bb_lower": _series(t, [b and b["lower"] for b in bands]),
        "bb_middle": _series(t, [b and b["middle"] for b in bands]),
        "rsi": _series(t, ind.rsi(closes)), "macd": _series(t, m["macd"]), "signal": _series(t, m["signal"]),
        "hist": _series(t, m["hist"]),
        "vwap": _series(t, ind.vwap(c)),
        "ma5": _series(t, ind.sma(closes, 5)), "ma10": _series(t, ind.sma(closes, 10)), "ma30": _series(t, ind.sma(closes, 30)),
    }
    st = ind.stoch_rsi(closes)
    out["stoch_k"], out["stoch_d"] = _series(t, st["k"]), _series(t, st["d"])
    fb = ind.fib_levels(c)
    ratios = (0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0)
    out["fib"] = {"trend": fb["trend"], "levels": [
        {"ratio": r, "price": (fb["high"] - r * (fb["high"] - fb["low"])) if fb["trend"] == "up"
         else (fb["low"] + r * (fb["high"] - fb["low"]))} for r in ratios]}
    try:
        out["smc"] = overlays.build(c, tf_sec=TF_SEC[tf], levels=_levels(sym))
    except Exception:  # ne jamais casser le graphique pour une decoration
        out["smc"] = None
    return JsonResponse(out)


def _sentiment_data(sym):
    """Donnees REELLES de sentiment : Fear & Greed (cache 1 h), funding et statistiques futures Gate."""
    if time.time() - _fng_cache["t"] > 3600:
        try:
            _fng_cache.update(t=time.time(), v=fetch_fear_greed())
        except SentimentError:
            _fng_cache["t"] = time.time() - 3000
    data = {"fear_greed": _fng_cache["v"], "funding_rate": None, "stats": None}
    client = GateClient()
    try:
        fr = client.ticker(sym).get("funding_rate")
        data["funding_rate"] = float(fr) if fr not in (None, "") else None
    except (GateAPIError, ValueError):
        pass
    try:
        data["stats"] = client.contract_stats(sym, "1h", 24)
    except GateAPIError:
        pass
    return data


def _lev_cap(request):
    try:
        lev = max(1, min(125, int(request.GET.get("lev", settings.KPS_DEFAULT_LEVERAGE))))
        cap = max(1.0, float(request.GET.get("cap", settings.KPS_DEFAULT_CAPITAL_USDT)))
    except ValueError:
        lev, cap = settings.KPS_DEFAULT_LEVERAGE, settings.KPS_DEFAULT_CAPITAL_USDT
    return lev, cap


def _analysis_bundle(sym, tf, lev, cap):
    """Analyse REELLE et EN DIRECT d'une paire sur un timeframe (bougies Gate, jamais simulees). Mise en cache 15 s :
    le scanner, la photo d'analyse et l'ordre pre-rempli partagent exactement le meme resultat."""
    key = (sym, tf, lev, cap)
    hit = _an_cache.get(key)
    if hit and time.time() - hit[0] < 15:
        return hit[1]
    client = GateClient()
    c = ind.normalize_candles(client.candlesticks(sym, TF_MAP[tf], 300))
    htf = None
    if HTF_MAP.get(tf):
        try:
            htf = ind.normalize_candles(client.candlesticks(sym, TF_MAP[HTF_MAP[tf]], 200))[:-1]
        except (GateAPIError, ValueError, KeyError):
            htf = None  # unite superieure indisponible : le scan continue sans ce filtre
    res = run_scan(c[:-1], sym, tf, {"min_score": settings.KPS_MIN_TECH_SCORE, "leverage": lev, "capital_usdt": cap},
                   htf_closed=htf)  # bougies CLOTUREES seulement
    res["htf"] = HTF_MAP.get(tf)
    d = res.get("direction") if res.get("direction") in ("LONG", "SHORT") else None
    sent = sentiment_engine.assess(_sentiment_data(sym), d)
    res["sentiment"] = sent
    if d:
        res["confluence"] = confluence(d, res.get("score", 0), None, sent)  # fondamental : calcule par le bot (actualites)
    for k in ("entry", "stop_loss"):
        if k in res:
            res[k] = float(f"{res[k]:.8g}")
    if "take_profits" in res:
        res["take_profits"] = [float(f"{x:.8g}") for x in res["take_profits"]]
    try:
        smc = overlays.build(c, tf_sec=TF_SEC[tf], levels=_levels(sym))
    except Exception:
        smc = None
    bundle = {"candles": c, "result": res, "smc": smc}
    _an_cache[key] = (time.time(), bundle)
    return bundle


@login_required
def scan_api(request):
    sym, tf = _params(request)
    if not sym:
        return _err("Parametres invalides", 400)
    lev, cap = _lev_cap(request)
    try:
        bundle = _analysis_bundle(sym, tf, lev, cap)
    except (GateAPIError, ValueError, KeyError) as e:
        return _err(f"DONNEES INDISPONIBLES : {e}")
    return JsonResponse(bundle["result"], json_dumps_params={"default": str})


def _photo_bytes(sym, tf, lev, cap):
    bundle = _analysis_bundle(sym, tf, lev, cap)
    try:
        return render_analysis(bundle["candles"], bundle["result"], bundle["smc"], sym, tf)
    except ImportError:  # Pillow absent : rendu simple de secours
        r = bundle["result"]
        return render_png(bundle["candles"][:-1], entry=r.get("entry"), stop_loss=r.get("stop_loss"),
                          take_profit=(r.get("take_profits") or [None, None])[1] if r.get("take_profits") else None,
                          zones=None)


@login_required
def analysis_image_api(request):
    """PHOTO D'ANALYSE annotee, calculee en direct sur les bougies reelles du timeframe demande."""
    sym, tf = _params(request)
    if not sym:
        return _err("Parametres invalides", 400)
    lev, cap = _lev_cap(request)
    try:
        png = _photo_bytes(sym, tf, lev, cap)
    except (GateAPIError, ValueError, KeyError) as e:
        return _err(f"DONNEES INDISPONIBLES : {e}")
    resp = HttpResponse(png, content_type="image/png")
    resp["Cache-Control"] = "no-store"
    return resp


@login_required
@require_POST
def analysis_image_send_api(request):
    sym, tf = _params(request)
    if not sym:
        return _err("Parametres invalides", 400)
    lev, cap = _lev_cap(request)
    try:
        png = _photo_bytes(sym, tf, lev, cap)
        r = _analysis_bundle(sym, tf, lev, cap)["result"]
    except (GateAPIError, ValueError, KeyError) as e:
        return _err(f"DONNEES INDISPONIBLES : {e}")
    cap_txt = f"{sym.replace('_', '/')} {tf.upper()} : {r.get('direction')} - {r.get('message', '')}"
    ok = telegram.send_photo(png, cap_txt[:900])
    return JsonResponse({"sent": bool(ok)}) if ok else _err("Envoi Telegram impossible (token / chat id ?)")


@login_required
def photos_page(request):
    sym = request.GET.get("symbol", "BTC_USDT")
    if not SYMBOL_RE.match(sym):
        sym = "BTC_USDT"
    lev, cap = _lev_cap(request)
    return render(request, "photos.html", {"symbol": sym, "tfs": list(TF_MAP.keys()), "lev": lev, "cap": cap})


@login_required
def prices_api(request):
    """Prix et variation de TOUTES les paires USDT Futures (le navigateur choisit celles qu'il affiche)."""
    try:
        tk = GateClient().tickers()
    except GateAPIError as e:
        return _err(f"DONNEES INDISPONIBLES : {e}")
    out = {}
    for t in tk:
        name = t.get("contract", "")
        if name.endswith("_USDT") and t.get("last"):
            try:
                out[name] = {"price": float(t["last"]), "change": float(t.get("change_percentage") or 0)}
            except ValueError:
                continue
    return JsonResponse(out)


@login_required
def account_api(request):
    since = timezone.now() - timedelta(hours=24)
    pnl24 = sum(t.net_pnl for t in TradeProposal.objects.filter(exec_status="closed", mode=settings.TRADING_MODE, closed_at__gte=since, net_pnl__isnull=False))
    res = {"mode": settings.TRADING_MODE, "open_positions": TradeProposal.objects.filter(exec_status="open", mode=settings.TRADING_MODE).count(),
           "pnl_24h": pnl24, "balance": None, "emergency": emergency_active()}
    try:
        b = trader_from_settings().balance()
        res["balance"] = {"total": float(b["total"]), "available": float(b["available"])}
    except (GateTradeError, KeyError, ValueError):
        pass  # cles absentes ou Gate indisponible : on affiche "indisponible", rien d'invente
    return JsonResponse(res)


@login_required
@require_POST
def emergency_api(request):
    flag, _ = SystemFlag.objects.get_or_create(key="emergency_stop")
    flag.value = not flag.value
    flag.save()
    telegram.send_message("ARRET D'URGENCE " + ("ACTIVE : plus aucune nouvelle position. Les positions existantes sont conservees."
                                                 if flag.value else "DESACTIVE."))
    return JsonResponse({"emergency": flag.value})


@login_required
def performance_api(request):
    try:
        days = max(1, min(365, int(request.GET.get("days", "30"))))
    except ValueError:
        days = 30
    since = timezone.now() - timedelta(days=days)
    qs = TradeProposal.objects.filter(exec_status="closed", mode=settings.TRADING_MODE, net_pnl__isnull=False, closed_at__gte=since).order_by("closed_at")
    res = performance([(int(t.closed_at.timestamp()), t.net_pnl) for t in qs])
    res["days"] = days
    return JsonResponse(res)


@login_required
@require_POST
def close_api(request, pk):
    """Ferme une position OUVERTE (ordre reduce-only 'close' sur Gate). Autorise meme en arret d'urgence."""
    t = get_object_or_404(TradeProposal, pk=pk, exec_status="open", mode=settings.TRADING_MODE)
    if settings.TRADING_MODE == "REAL" and request.POST.get("real_confirm", "").strip() != "REAL":
        return _err("Mode REEL : tape REAL pour confirmer la fermeture", 400)
    try:
        trader = trader_from_settings()
        trader.close_position(t.symbol)
        n = sync_open_trades(trader, TradeProposal)
    except GateTradeError as e:
        return _err(f"Fermeture non confirmee par Gate : {e}")
    t.refresh_from_db()
    telegram.send_message(f"Fermeture envoyee pour #{t.pk} {t.symbol} ({t.mode}). Statut : {t.exec_status}"
                          + (f" | PNL {t.net_pnl:+.2f} USDT" if t.net_pnl is not None else ""))
    return JsonResponse({"status": t.exec_status, "net_pnl": t.net_pnl, "closed_detected": n})


@login_required
def backtest_api(request):
    """Reussite HISTORIQUE reelle de la strategie sur ce marche (peut prendre quelques secondes)."""
    sym, tf = _params(request)
    if not sym:
        return _err("Parametres invalides", 400)
    key = (sym, tf)
    hit = _bt_cache.get(key)
    if hit and time.time() - hit[0] < 1800:
        return JsonResponse(hit[1])
    try:
        client = GateClient()
        c = ind.normalize_candles(client.candlesticks(sym, TF_MAP[tf], 1000))[:-1]
        htf = None
        if HTF_MAP.get(tf):
            h = ind.normalize_candles(client.candlesticks(sym, TF_MAP[HTF_MAP[tf]], 500))[:-1]
            htf = {"tf": HTF_MAP[tf], "candles": h}
    except (GateAPIError, ValueError, KeyError) as e:
        return _err(f"DONNEES INDISPONIBLES : {e}")
    res = run_backtest(c, sym, tf, {"min_score": settings.KPS_MIN_TECH_SCORE}, htf=htf)
    _bt_cache[key] = (time.time(), res)
    return JsonResponse(res)


@login_required
def contracts_api(request):
    """Toutes les paires USDT Futures negociables (triees par volume), pour la liste de gauche."""
    if time.time() - _contracts_cache["t"] > 60:
        try:
            client = GateClient()
            contracts = {c["name"]: c for c in client.contracts() if not c.get("in_delisting") and c.get("name", "").endswith("_USDT")}
            out = []
            for t in client.tickers():
                name = t.get("contract")
                if name in contracts and t.get("last"):
                    try:
                        out.append({"symbol": name, "price": float(t["last"]), "change": float(t.get("change_percentage") or 0),
                                    "volume": float(t.get("volume_24h_quote") or 0)})
                    except ValueError:
                        continue
            out.sort(key=lambda x: -x["volume"])
            _contracts_cache.update(t=time.time(), data=out)
        except GateAPIError as e:
            return _err(f"DONNEES INDISPONIBLES : {e}")
    logo_store.warm([p["symbol"] for p in _contracts_cache["data"][:80]] + list(settings.KPS_EXTRA_SYMBOLS))
    return JsonResponse({"pairs": _contracts_cache["data"], "extras": list(settings.KPS_EXTRA_SYMBOLS)})


@login_required
def logo_api(request, base):
    """Vrai logo de la crypto (stocke en base, telecharge a la demande depuis CoinGecko puis sources de secours)."""
    got = logo_store.get_logo(base)
    if not got:
        raise Http404("logo introuvable")
    resp = HttpResponse(got[0], content_type=got[1])
    resp["Cache-Control"] = "private, max-age=604800"
    return resp


@login_required
def bot_api(request):
    return JsonResponse(autorun.status_dict())


@login_required
@require_POST
def bot_control_api(request):
    """Actions du site sur le moteur d'analyse : demarrer / arreter l'analyse automatique, ou analyser maintenant."""
    action = request.POST.get("action")
    st = autorun.get_status()
    if action == "toggle":
        st.enabled = not st.enabled
        st.save(update_fields=["enabled"])
        telegram.send_message("Analyse automatique " + ("ACTIVEE." if st.enabled else "ARRETEE."))
    elif action == "run_now":
        if not settings.KPS_AUTORUN:
            return _err("Analyse automatique desactivee (KPS_AUTORUN=false) : lance `python manage.py run_bot`.", 400)
        if not st.enabled:
            return _err("L'analyse automatique est arretee : demarre-la d'abord.", 400)
        st.run_requested = True
        st.save(update_fields=["run_requested"])
    else:
        return _err("Action inconnue", 400)
    autorun.ensure_started()
    return JsonResponse(autorun.status_dict())
