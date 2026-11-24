"""Moteur du bot : scan -> analyse (technique + fondamentale + sentiment) -> confluence -> site + Telegram (ENVOI SEUL).
Les trades se prennent UNIQUEMENT sur le site (EXECUTE TRADE). Rien n'est execute ici.
Utilise par la commande `run_bot` ET par l'analyse automatique du site (apps/trading/autorun.py)."""
import time
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.fundamental_analysis import news as news_lib
from apps.fundamental_analysis.models import NewsItem
from apps.market_data.gate_client import GateAPIError, GateClient
from apps.market_scanner.models import SymbolAnalysis
from apps.market_scanner.scanner import select_top
from apps.notifications import messages, telegram
from apps.sentiment_analysis.sources import SentimentError, fetch_fear_greed
from apps.technical_analysis.indicators import normalize_candles
from apps.trade_approval.models import TradeProposal
from apps.trade_history.chart import CHART_LEGEND, render_png
from apps.trading.factory import trader_from_settings
from apps.trading.gate_private import GateTradeError
from apps.trading.pipeline import build_proposal
from apps.trading.sync import sync_open_trades


class RunnerError(Exception):
    pass


def load_cfg():
    return {
        "min_score": settings.KPS_MIN_TECH_SCORE, "reward_risk": settings.KPS_REWARD_RISK,
        "leverage": settings.KPS_DEFAULT_LEVERAGE, "max_leverage": settings.KPS_MAX_LEVERAGE,
        "capital_usdt": settings.KPS_DEFAULT_CAPITAL_USDT, "equity_usdt": settings.KPS_DEMO_EQUITY_USDT,
        "ttl_minutes": settings.KPS_PROPOSAL_TTL_MINUTES, "mode": settings.TRADING_MODE,
        "require_news": settings.KPS_REQUIRE_NEWS, "min_confluence": settings.KPS_MIN_CONFLUENCE,
        "require_sentiment": settings.KPS_REQUIRE_SENTIMENT,
        "limits": {"max_risk_pct": settings.KPS_RISK_PER_TRADE_PCT,
                   "max_daily_loss_pct": settings.KPS_MAX_DAILY_LOSS_PCT},
    }


def jsonable(a, f, sent=None, conf=None):
    items = [{**{k: v for k, v in i.items() if k != "published_at"}, "published_at": i["published_at"].isoformat()}
             for i in (f or {}).get("items", [])]
    return {"strategies": a.get("strategies", []), "tally": a.get("tally"),
            "mtf": ({"h4": a["mtf"]["4h"], "h1": a["mtf"]["1h"], "m15": a["mtf"]["15m"]} if a.get("mtf") else None),
            "reasons": a.get("reasons", []), "tools": a.get("tools", []),
            "fundamental": {k: v for k, v in (f or {}).items() if k != "items"} | {"items": items},
            "sentiment": sent, "confluence": conf}


class BotRunner:
    def __init__(self, dry=False, log=print, err=print, heartbeat=lambda: None):
        self.dry, self.log, self.err, self.heartbeat = dry, log, err, heartbeat
        self.cfg = load_cfg()
        self.news_cache, self.fng = {}, (0.0, None)
        self.provider_cache = {"newsapi": {}, "newsdata": {}, "cryptopanic": {}}
        self.budgets = {"newsapi": news_lib.Budget(settings.KPS_NEWSAPI_DAILY_LIMIT),
                        "newsdata": news_lib.Budget(settings.KPS_NEWSDATA_DAILY_LIMIT),
                        "cryptopanic": news_lib.Budget(500)}

    def cycle(self, symbols=None):
        """Un cycle complet : analyse de toutes les paires puis suivi des positions ouvertes."""
        self.cfg = load_cfg()  # reprend les reglages a chaque cycle
        try:
            summary = self.scan(symbols)
        except GateAPIError as e:
            self.err(f"DONNEES INDISPONIBLES : {e}")
            summary = {"symbols": 0, "proposals": 0, "news": 0, "error": f"DONNEES INDISPONIBLES : {e}"}
        if not self.dry:
            try:
                n = sync_open_trades(trader_from_settings(), TradeProposal)
                if n:
                    self.log(f"{n} position(s) fermee(s) detectee(s)")
            except GateTradeError:
                pass
        return summary

    # ---- actualites : GDELT (sans cle) + fournisseurs a cle facultatifs (cache et budget quotidien) ----
    def limited(self, name, sym, key, fetch, refresh_min):
        """Fournisseur a cle : reponse mise en cache, et jamais plus que la limite quotidienne."""
        if not key:
            return [], 0
        hit = self.provider_cache[name].get(sym)
        if hit and time.time() - hit[0] < refresh_min * 60:
            return hit[1], 0
        if not self.budgets[name].allow():
            return (hit[1] if hit else []), 0  # limite atteinte : derniere reponse reutilisee
        self.budgets[name].used()
        try:
            got = fetch()
            self.provider_cache[name][sym] = (time.time(), got)
            return got, 0
        except news_lib.NewsError as e:
            self.err(f"{sym} : {e}")
            return [], 1

    def get_news(self, sym):
        hit = self.news_cache.get(sym)
        if hit and time.time() - hit[0] < 1800:
            return hit[1]
        items, errors = [], 0
        try:
            items += news_lib.fetch_gdelt(sym)
        except news_lib.NewsError as e:
            errors += 1
            self.err(f"{sym} : {e}")
        time.sleep(5.5)  # GDELT : ne pas depasser ~1 requete / 5 s
        providers = (
            ("newsapi", settings.NEWSAPI_KEY, lambda: news_lib.fetch_newsapi(sym, settings.NEWSAPI_KEY, max_age_hours=settings.KPS_NEWS_MAX_AGE_HOURS), settings.KPS_NEWSAPI_REFRESH_MINUTES),
            ("newsdata", settings.NEWSDATA_API_KEY, lambda: news_lib.fetch_newsdata(sym, settings.NEWSDATA_API_KEY), settings.KPS_NEWSDATA_REFRESH_MINUTES),
            ("cryptopanic", settings.CRYPTOPANIC_API_KEY, lambda: news_lib.fetch_cryptopanic(sym, settings.CRYPTOPANIC_API_KEY, settings.CRYPTOPANIC_PLAN), 30),
        )
        for name, key, fetch, refresh in providers:
            got, err = self.limited(name, sym, key, fetch, refresh)
            items += got
            errors += err
        res = None if (errors and not items) else news_lib.prepare(items, max_age_hours=settings.KPS_NEWS_MAX_AGE_HOURS)
        self.news_cache[sym] = (time.time(), res)
        return res

    def photo(self, c15, res, p, a):
        """Photo d'analyse annotee (Pillow) ; image simple de secours si Pillow est absent."""
        try:
            from apps.smart_money import overlays
            from apps.trade_history.analysis_image import render_analysis
            if p:
                r = {"direction": p["direction"], "entry": p["entry"], "stop_loss": p["stop_loss"], "take_profits": p.get("take_profits"),
                     "confluence": p.get("confluence"), "score": a["score"], "max_score": 40, "message": f"Proposition {p['direction']}"}
            else:
                reason = res.get("reason") or "; ".join(res.get("violations", [])) or "aucun signal"
                r = {"direction": "ATTENTE", "message": f"ATTENTE : {reason}", "score": a["score"], "max_score": 40,
                     "confluence": res.get("confluence")}
            r["timestamp"] = timezone.now().strftime("%Y-%m-%dT%H:%M:%S")
            return render_analysis(c15, r, overlays.build(c15, tf_sec=900), p["symbol"] if p else res.get("symbol", ""), "15m")
        except (ImportError, ValueError):
            return render_png(c15[:-1], entry=p and p["entry"], stop_loss=p and p["stop_loss"],
                              take_profit=p and p["take_profit"], zones=a.get("zones"))

    # ---- sentiment : Fear & Greed (cache 1 h) + funding + statistiques futures Gate ----
    def get_sentiment(self, client, sym, ticker):
        if time.time() - self.fng[0] > 3600:
            try:
                self.fng = (time.time(), fetch_fear_greed())
            except SentimentError as e:
                self.err(f"Fear & Greed : {e}")
                self.fng = (time.time() - 3000, self.fng[1])  # on re-essaie dans 10 min
        data = {"fear_greed": self.fng[1], "funding_rate": None, "stats": None}
        try:
            if ticker.get("funding_rate") not in (None, ""):
                data["funding_rate"] = float(ticker["funding_rate"])
        except ValueError:
            pass
        try:
            data["stats"] = client.contract_stats(sym, "1h", 24)
        except GateAPIError as e:
            self.err(f"{sym} : statistiques futures indisponibles ({e})")
        return data

    # ---- cycle ----
    def scan(self, symbols=None):
        cfg, symbols = self.cfg, list(symbols or [])
        client = GateClient()
        contracts, tickers = client.contracts(), client.tickers()
        by_ticker = {t.get("contract"): t for t in tickers}
        known = {c.get("name") for c in contracts}
        if not symbols:
            top = select_top(contracts, tickers)
            if not top:
                raise RunnerError("Scanner : aucun contrat ne respecte les criteres.")
            symbols = [r["contract"] for r in top]
            for x in settings.KPS_EXTRA_SYMBOLS:
                if x not in symbols:
                    if x in known:
                        symbols.append(x)
                    else:
                        self.err(f"{x} : contrat introuvable sur Gate futures (verifie le nom)")
        rows, new_news, sent = [], [], 0
        for sym in symbols:
            self.heartbeat()
            try:
                tf = {k: normalize_candles(client.candlesticks(sym, k, 200)) for k in ("4h", "1h", "15m")}
            except (GateAPIError, ValueError, KeyError) as e:
                self.err(f"{sym} : donnees indisponibles ({e})")
                continue
            time.sleep(0.2)
            news = self.get_news(sym)
            tk = by_ticker.get(sym, {})
            res = build_proposal(sym, tf["4h"], tf["1h"], tf["15m"], cfg, news=news, sentiment=self.get_sentiment(client, sym, tk))
            a, f = res["analysis"], res["fundamental"]
            res.setdefault("symbol", sym)
            price = float(tk["last"]) if tk.get("last") else tf["15m"][-2]["c"]
            chg = float(tk["change_percentage"]) if tk.get("change_percentage") else None
            rows.append({"symbol": sym, "price": price, "change_pct": chg, "direction": a["direction"], "score": a["score"]})
            p = res.get("proposal") if res["status"] == "proposal" else None
            png = self.photo(tf["15m"], res, p, a)
            if res["status"] == "blocked":
                self.log(f"{sym} : BLOQUE : {'; '.join(res['violations'])}")
            elif res["status"] == "none":
                self.log(f"{sym} : pas de signal ({res['reason']})")
            if self.dry:
                if p:
                    p["id"], p["expires_at"] = 0, "-"
                    self.log(messages.format_proposal(p))
                continue
            SymbolAnalysis.objects.update_or_create(symbol=sym, defaults={
                "price": price, "change_pct": chg, "direction": a["direction"], "score": a["score"],
                "payload": jsonable(a, f, res.get("sentiment"), res.get("confluence")), "chart_png": png})
            for i in (f["items"] if f else []):
                obj, created = NewsItem.objects.get_or_create(url=i["url"][:500], defaults={
                    "title": i["title"][:500], "source": i["source"][:120], "published_at": i["published_at"],
                    "symbols": [sym.split("_")[0]], "sentiment": i["sentiment"], "importance": i["importance"],
                    "reliability": i["reliability"]})
                if created:
                    new_news.append({**i, "symbol": sym.split("_")[0]})
            if p and not TradeProposal.objects.filter(
                    symbol=sym, direction=p["direction"], created_at__gt=timezone.now() - timedelta(hours=4)).exists():
                p['sentiment_full'] = res.get('sentiment')
                self.send_proposal(p, png, a, f)
                sent += 1
            elif settings.KPS_REPORT_ALL_CHARTS:
                telegram.send_photo(png, f"{sym} - {CHART_LEGEND}")
                telegram.send_message(messages.format_analysis(sym, a, f, res.get("sentiment"), res.get("confluence")))
        if rows and not self.dry:
            telegram.send_message(messages.format_market_summary(sorted(rows, key=lambda r: -r["score"]), settings.TRADING_MODE))
        digest = sorted(new_news, key=lambda i: (-i["importance"], i["published_at"]), reverse=False)[:settings.KPS_NEWS_PER_CYCLE]
        digest.sort(key=lambda i: -i["importance"])
        if digest:
            text = messages.format_news_digest(digest)
            self.log(text) if self.dry else telegram.send_message(text)
        summary = {"symbols": len(rows), "proposals": sent, "news": len(new_news)}
        self.log(f"Cycle termine : {summary['symbols']} symbole(s), {sent} proposition(s), {len(new_news)} nouvelle(s) actualite(s)")
        return summary

    def send_proposal(self, p, png, a, f):
        expires = timezone.now() + timedelta(minutes=p["ttl_minutes"])
        p["expires_at"] = expires.strftime("%H:%M UTC")
        obj = TradeProposal.objects.create(
            symbol=p["symbol"], direction=p["direction"], mode=p["mode"], entry=p["entry"],
            stop_loss=p["stop_loss"], take_profit=p["take_profit"], leverage=p["leverage"],
            capital_usdt=p["capital_usdt"], score_technical=p["score_technical"],
            payload={k: v for k, v in p.items() if k not in ("zones", "sentiment_full")}, expires_at=expires)
        p["id"] = obj.pk
        link = (f"\n\nPour prendre ce trade : ouvre ton site -> {settings.KPS_PUBLIC_URL}/trades/{obj.pk}/"
                if settings.KPS_PUBLIC_URL else "\n\nPour prendre ce trade : ouvre ton site (page Propositions).")
        telegram.send_photo(png, f"{p['symbol']} {p['direction']} - {CHART_LEGEND}")
        telegram.send_message(messages.format_analysis(p["symbol"], a, f, p.get("sentiment_full"), p.get("confluence")))
        ok = telegram.send_message(messages.format_proposal(p) + link)
        self.log(f"{p['symbol']} {p['direction']} : proposition #{obj.pk} " + ("envoyee" if ok else "ECHEC Telegram"))
