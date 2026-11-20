"""Suivi des positions ouvertes : detecte la fermeture (SL/TP/manuelle) et enregistre le resultat."""
from django.conf import settings
from django.utils import timezone

from apps.notifications import messages, telegram

from .gate_private import GateTradeError


def sync_open_trades(trader, model):
    closed = 0
    for t in model.objects.filter(exec_status="open", mode=settings.TRADING_MODE):
        try:
            pos = trader.position(t.symbol)
            if int(float(pos.get("size", 0))) != 0:
                continue
            pnl = None
            try:
                ts = t.executed_at.timestamp() if t.executed_at else 0
                for rec in trader.position_close_history(t.symbol):
                    if float(rec.get("time", 0)) >= ts - 5:
                        pnl = float(rec["pnl"])
                        break
            except (GateTradeError, KeyError, ValueError):
                pass
            for oid in (t.sl_order_id, t.tp_order_id):  # annule la jambe restante
                if oid:
                    try:
                        trader.cancel_price_order(oid)
                    except GateTradeError:
                        pass
            t.exec_status, t.closed_at, t.net_pnl = "closed", timezone.now(), pnl
            t.save(update_fields=["exec_status", "closed_at", "net_pnl"])
            closed += 1
            if pnl is None:
                telegram.send_message(f"Position #{t.pk} {t.symbol} FERMEE. Resultat non lisible : verifie sur Gate.")
            else:
                telegram.send_message(messages.format_result({
                    "symbol": t.symbol, "direction": t.direction, "mode": t.mode, "entry": t.fill_price,
                    "exit": None, "net_pnl": pnl, "explanation": "Position fermee par SL, TP ou manuellement."}))
        except (GateTradeError, ValueError, TypeError):
            continue
    return closed
