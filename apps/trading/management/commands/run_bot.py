"""Boucle du bot : scan -> analyse (technique + fondamentale) -> site + Telegram (ENVOI SEUL).
Les trades se prennent UNIQUEMENT sur le site (EXECUTE TRADE). Rien n'est execute ici."""
import time
from datetime import datetime, timedelta, timezone as dt_tz

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.fundamental_analysis import news as news_lib
from apps.fundamental_analysis.models import NewsItem
from apps.market_data.gate_client import GateAPIError, GateClient
from apps.market_scanner.models import SymbolAnalysis
from apps.market_scanner.scanner import select_top
from apps.notifications import messages, telegram
from apps.technical_analysis.indicators import normalize_candles
from apps.trade_approval.models import TradeProposal
from apps.trade_history.chart import CHART_LEGEND, render_png
from apps.trading.factory import trader_from_settings
from apps.trading.gate_private import GateTradeError
from apps.trading.pipeline import build_proposal
from apps.trading.sync import sync_open_trades


def load_cfg():
    return {
        "min_score": settings.KPS_MIN_TECH_SCORE, "reward_risk": settings.KPS_REWARD_RISK,
        "leverage": settings.KPS_DEFAULT_LEVERAGE, "max_leverage": settings.KPS_MAX_LEVERAGE,
        "capital_usdt": settings.KPS_DEFAULT_CAPITAL_USDT, "equity_usdt": settings.KPS_DEMO_EQUITY_USDT,
        "ttl_minutes": settings.KPS_PROPOSAL_TTL_MINUTES, "mode": settings.TRADING_MODE,
        "require_news": settings.KPS_REQUIRE_NEWS,
        "limits": {"max_risk_pct": settings.KPS_RISK_PER_TRADE_PCT,
                   "max_daily_loss_pct": settings.KPS_MAX_DAILY_LOSS_PCT},
    }


def jsonable(a, f):
    items = [{**{k: v for k, v in i.items() if k != "published_at"}, "published_at": i["published_at"].isoformat()}
             for i in (f or {}).get("items", [])]
    return {"strategies": a.get("strategies", []), "tally": a.get("tally"),
            "mtf": ({"h4": a["mtf"]["4h"], "h1": a["mtf"]["1h"], "m15": a["mtf"]["15m"]} if a.get("mtf") else None),
            "reasons": a.get("reasons", []), "tools": a.get("tools", []),
            "fundamental": {k: v for k, v in (f or {}).items() if k != "items"} | {"items": items}}


class Command(BaseCommand):
    help = "Lance le bot (analyse + envoi Telegram). --once = un seul cycle."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--symbols", default="", help="ex: BTC_USDT,XAUT_USDT (sinon top 20 + extras)")
        parser.add_argument("--dry-run", action="store_true", help="rien sur Telegram ni en base")

    def handle(self, *args, **o):
        self.dry, self.news_cache = o["dry_run"], {}
        cfg = load_cfg()
        symbols = [s.strip() for s in o["symbols"].split(",") if s.strip()]
        self.stdout.write(f"KPS demarre | mode {settings.TRADING_MODE} | marge {settings.MARGIN_MODE} | "
                          f"cycle {settings.KPS_SCAN_INTERVAL_SECONDS}s | Telegram = envoi seul | aucun trade ici")
        while True:
            try:
                self.scan(cfg, symbols)
            except GateAPIError as e:
                self.stderr.write(f"DONNEES INDISPONIBLES : {e}")
            if not self.dry:
                try:
                    n = sync_open_trades(trader_from_settings(), TradeProposal)
                    if n:
                        self.stdout.write(f"{n} position(s) fermee(s) detectee(s)")
                except GateTradeError:
                    pass
            if o["once"]:
                break
            time.sleep(settings.KPS_SCAN_INTERVAL_SECONDS)

    # ---- actualites (cache + limite de debit GDELT) ----
    def get_news(self, sym):
        hit = self.news_cache.get(sym)
        if hit and time.time() - hit[0] < 1800:
            return hit[1]
        items, errors = [], 0
        try:
            items += news_lib.fetch_gdelt(sym)
        except news_lib.NewsError as e:
            errors += 1
            self.stderr.write(f"{sym} : {e}")
        time.sleep(5.5)  # GDELT : ne pas depasser ~1 requete / 5 s
        if settings.CRYPTOPANIC_API_KEY:
            try:
                items += news_lib.fetch_cryptopanic(sym, settings.CRYPTOPANIC_API_KEY, settings.CRYPTOPANIC_PLAN)
            except news_lib.NewsError as e:
                errors += 1
                self.stderr.write(f"{sym} : {e}")
        res = None if (errors and not items) else news_lib.prepare(items, max_age_hours=settings.KPS_NEWS_MAX_AGE_HOURS)
        self.news_cache[sym] = (time.time(), res)
        return res

    # ---- cycle ----
    def scan(self, cfg, symbols):
        client = GateClient()
        contracts, tickers = client.contracts(), client.tickers()
        by_ticker = {t.get("contract"): t for t in tickers}
        known = {c.get("name") for c in contracts}
        if not symbols:
            top = select_top(contracts, tickers)
            if not top:
                raise CommandError("Scanner : aucun contrat ne respecte les criteres.")
            symbols = [r["contract"] for r in top]
            for x in settings.KPS_EXTRA_SYMBOLS:
                if x not in symbols:
                    if x in known:
                        symbols.append(x)
                    else:
                        self.stderr.write(f"{x} : contrat introuvable sur Gate futures (verifie le nom)")
        rows, new_news, sent = [], [], 0
        for sym in symbols:
            try:
                tf = {k: normalize_candles(client.candlesticks(sym, k, 200)) for k in ("4h", "1h", "15m")}
            except (GateAPIError, ValueError, KeyError) as e:
                self.stderr.write(f"{sym} : donnees indisponibles ({e})")
                continue
            time.sleep(0.2)
            news = self.get_news(sym)
            res = build_proposal(sym, tf["4h"], tf["1h"], tf["15m"], cfg, news=news)
            a, f = res["analysis"], res["fundamental"]
            tk = by_ticker.get(sym, {})
            price = float(tk["last"]) if tk.get("last") else tf["15m"][-2]["c"]
            chg = float(tk["change_percentage"]) if tk.get("change_percentage") else None
            rows.append({"symbol": sym, "price": price, "change_pct": chg, "direction": a["direction"], "score": a["score"]})
            p = res.get("proposal") if res["status"] == "proposal" else None
            png = render_png(tf["15m"][:-1], entry=p and p["entry"], stop_loss=p and p["stop_loss"],
                             take_profit=p and p["take_profit"], zones=a.get("zones"))
            if res["status"] == "blocked":
                self.stdout.write(f"{sym} : BLOQUE : {'; '.join(res['violations'])}")
            elif res["status"] == "none":
                self.stdout.write(f"{sym} : pas de signal ({res['reason']})")
            if self.dry:
                if p:
                    p["id"], p["expires_at"] = 0, "-"
                    self.stdout.write(messages.format_proposal(p))
                continue
            SymbolAnalysis.objects.update_or_create(symbol=sym, defaults={
                "price": price, "change_pct": chg, "direction": a["direction"], "score": a["score"],
                "payload": jsonable(a, f), "chart_png": png})
            for i in (f["items"] if f else []):
                obj, created = NewsItem.objects.get_or_create(url=i["url"][:500], defaults={
                    "title": i["title"][:500], "source": i["source"][:120], "published_at": i["published_at"],
                    "symbols": [sym.split("_")[0]], "sentiment": i["sentiment"], "importance": i["importance"],
                    "reliability": i["reliability"]})
                if created:
                    new_news.append({**i, "symbol": sym.split("_")[0]})
            if p and not TradeProposal.objects.filter(
                    symbol=sym, direction=p["direction"], created_at__gt=timezone.now() - timedelta(hours=4)).exists():
                self.send_proposal(p, png, a, f)
                sent += 1
            elif settings.KPS_REPORT_ALL_CHARTS:
                telegram.send_photo(png, f"{sym} - {CHART_LEGEND}")
                telegram.send_message(messages.format_analysis(sym, a, f))
        if rows and not self.dry:
            telegram.send_message(messages.format_market_summary(sorted(rows, key=lambda r: -r["score"]), settings.TRADING_MODE))
        digest = sorted(new_news, key=lambda i: (-i["importance"], i["published_at"]), reverse=False)[:settings.KPS_NEWS_PER_CYCLE]
        digest.sort(key=lambda i: -i["importance"])
        if digest:
            text = messages.format_news_digest(digest)
            self.stdout.write(text) if self.dry else telegram.send_message(text)
        self.stdout.write(f"Cycle termine : {len(rows)} symbole(s), {sent} proposition(s), {len(new_news)} nouvelle(s) actualite(s)")

    def send_proposal(self, p, png, a, f):
        expires = timezone.now() + timedelta(minutes=p["ttl_minutes"])
        p["expires_at"] = expires.strftime("%H:%M UTC")
        obj = TradeProposal.objects.create(
            symbol=p["symbol"], direction=p["direction"], mode=p["mode"], entry=p["entry"],
            stop_loss=p["stop_loss"], take_profit=p["take_profit"], leverage=p["leverage"],
            capital_usdt=p["capital_usdt"], score_technical=p["score_technical"],
            payload={k: v for k, v in p.items() if k != "zones"}, expires_at=expires)
        p["id"] = obj.pk
        link = (f"\n\nPour prendre ce trade : ouvre ton site -> {settings.KPS_PUBLIC_URL}/trades/{obj.pk}/"
                if settings.KPS_PUBLIC_URL else "\n\nPour prendre ce trade : ouvre ton site (page Propositions).")
        telegram.send_photo(png, f"{p['symbol']} {p['direction']} - {CHART_LEGEND}")
        telegram.send_message(messages.format_analysis(p["symbol"], a, f))
        ok = telegram.send_message(messages.format_proposal(p) + link)
        self.stdout.write(f"{p['symbol']} {p['direction']} : proposition #{obj.pk} " + ("envoyee" if ok else "ECHEC Telegram"))
