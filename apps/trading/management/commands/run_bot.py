"""Boucle principale : scan -> analyse 4H/1H/15M -> proposition -> Telegram -> boutons.
Aucun ordre n'est envoye a Gate.io (Phase 11). Les decisions sont seulement enregistrees."""
import time
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.market_data.gate_client import GateAPIError, GateClient
from apps.market_scanner.scanner import select_top
from apps.notifications import messages, telegram
from apps.technical_analysis.indicators import normalize_candles
from apps.trade_approval.decisions import decide, parse_callback
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
        "limits": {"max_risk_pct": settings.KPS_RISK_PER_TRADE_PCT,
                   "max_daily_loss_pct": settings.KPS_MAX_DAILY_LOSS_PCT},
    }


class Command(BaseCommand):
    help = "Lance le bot (scan + propositions Telegram). Utiliser --once pour un seul cycle."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--symbols", default="", help="ex: BTC_USDT,ETH_USDT (sinon top 20 du scanner)")
        parser.add_argument("--dry-run", action="store_true", help="n'envoie rien sur Telegram, n'ecrit pas en base")

    def handle(self, *args, **o):
        self.offset = None
        self.dry = o["dry_run"]
        cfg = load_cfg()
        symbols = [s.strip() for s in o["symbols"].split(",") if s.strip()]
        self.stdout.write(f"KPS demarre | mode {settings.TRADING_MODE} | marge {settings.MARGIN_MODE} | "
                          f"scan toutes les {settings.KPS_SCAN_INTERVAL_SECONDS}s | aucun ordre envoye")
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
                    pass  # cles absentes : pas de suivi
            if o["once"]:
                break
            until = time.time() + settings.KPS_SCAN_INTERVAL_SECONDS
            while time.time() < until:
                self.poll_buttons()
                time.sleep(2)

    # ---- scan ----
    def scan(self, cfg, symbols):
        client = GateClient()
        if not symbols:
            top = select_top(client.contracts(), client.tickers())
            if not top:
                raise CommandError("Scanner : aucun contrat ne respecte les criteres.")
            symbols = [r["contract"] for r in top]
        sent = 0
        for sym in symbols:
            try:
                tf = {k: normalize_candles(client.candlesticks(sym, k, 200)) for k in ("4h", "1h", "15m")}
            except (GateAPIError, ValueError, KeyError) as e:
                self.stderr.write(f"{sym} : donnees indisponibles ({e})")
                continue
            time.sleep(0.2)
            res = build_proposal(sym, tf["4h"], tf["1h"], tf["15m"], cfg)
            if res["status"] == "none":
                self.stdout.write(f"{sym} : pas de signal ({res['reason']})")
                continue
            if res["status"] == "blocked":
                self.stdout.write(f"{sym} : BLOQUE par la gestion du risque : {'; '.join(res['violations'])}")
                continue
            p = res["proposal"]
            if not self.dry and TradeProposal.objects.filter(
                    symbol=sym, direction=p["direction"],
                    created_at__gt=timezone.now() - timedelta(hours=4)).exists():
                self.stdout.write(f"{sym} : proposition deja envoyee recemment, ignoree")
                continue
            self.send(p, tf["15m"])
            sent += 1
        self.stdout.write(f"Cycle termine : {sent} proposition(s)")

    def send(self, p, c15):
        expires = timezone.now() + timedelta(minutes=p["ttl_minutes"])
        p["expires_at"] = expires.strftime("%H:%M UTC")
        png = render_png(c15[:-1], entry=p["entry"], stop_loss=p["stop_loss"],
                         take_profit=p["take_profit"], zones=p.get("zones"))
        if self.dry:
            p["id"] = 0
            self.stdout.write(messages.format_proposal(p))
            return
        obj = TradeProposal.objects.create(
            symbol=p["symbol"], direction=p["direction"], mode=p["mode"], entry=p["entry"],
            stop_loss=p["stop_loss"], take_profit=p["take_profit"], leverage=p["leverage"],
            capital_usdt=p["capital_usdt"], score_technical=p["score_technical"],
            payload={k: v for k, v in p.items() if k != "zones"}, expires_at=expires)
        p["id"] = obj.pk
        telegram.send_photo(png, f"{p['symbol']} {p['direction']} - {CHART_LEGEND}")
        link = f"\n\nOuvrir pour executer : {settings.KPS_PUBLIC_URL}/trades/{obj.pk}/" if settings.KPS_PUBLIC_URL else ""
        ok = telegram.send_message(messages.format_proposal(p) + link, reply_markup=telegram.approval_keyboard(obj.pk))
        self.stdout.write(f"{p['symbol']} {p['direction']} : proposition #{obj.pk} " + ("envoyee" if ok else "ECHEC Telegram"))

    # ---- boutons Telegram ----
    def poll_buttons(self):
        for u in telegram.get_updates(self.offset, timeout=0):
            self.offset = u["update_id"] + 1
            cb = u.get("callback_query")
            if not cb:
                continue
            chat = str(cb.get("message", {}).get("chat", {}).get("id", ""))
            if chat != str(settings.TELEGRAM_CHAT_ID):
                continue  # ignore tout autre utilisateur
            action, pid = parse_callback(cb.get("data"))
            if not action:
                continue
            try:
                obj = TradeProposal.objects.get(pk=pid)
            except TradeProposal.DoesNotExist:
                telegram.answer_callback(cb["id"], "Proposition introuvable")
                continue
            new, msg = decide(obj.status, obj.expires_at < timezone.now(), action)
            if new:
                obj.status, obj.decided_at = new, timezone.now()
                obj.save(update_fields=["status", "decided_at"])
            telegram.answer_callback(cb["id"], msg[:150])
            telegram.send_message(f"#{pid} {obj.symbol} : {msg}")
