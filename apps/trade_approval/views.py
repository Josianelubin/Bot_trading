from datetime import timedelta

from django.conf import settings
from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.notifications import messages as tg_text, telegram
from apps.risk_management.discipline import check_plan
from apps.trading.executor import execute
from apps.trading.factory import trader_from_settings
from apps.trading.gate_private import GateTradeError
from apps.trading.sync import sync_open_trades

from apps.audit.models import emergency_active

from .models import TradeProposal


def risk_state():
    """Etat reel pour la discipline : calcule sur les trades CLOTURES enregistres."""
    now = timezone.now()
    closed = list(TradeProposal.objects.filter(exec_status="closed", net_pnl__isnull=False).order_by("-closed_at")[:20])
    today = sum(t.net_pnl for t in closed if t.closed_at and t.closed_at.date() == now.date())
    consecutive = 0
    for t in closed:
        if t.net_pnl < 0:
            consecutive += 1
        else:
            break
    minutes = None
    if closed and closed[0].net_pnl < 0 and closed[0].closed_at:
        minutes = int((now - closed[0].closed_at).total_seconds() // 60)
    return {"daily_loss_usdt": max(0.0, -today), "consecutive_losses": consecutive, "minutes_since_last_loss": minutes}


def _limits():
    return {"max_risk_pct": settings.KPS_RISK_PER_TRADE_PCT, "max_daily_loss_pct": settings.KPS_MAX_DAILY_LOSS_PCT}


@login_required
def proposals(request):
    return render(request, "proposals.html", {"items": TradeProposal.objects.all()[:50]})


@login_required
def detail(request, pk):
    obj = get_object_or_404(TradeProposal, pk=pk)
    now = timezone.now()
    editable = obj.exec_status == "none" and obj.status in ("pending", "accepted") and obj.expires_at > now
    if request.method == "POST":
        if not editable:
            flash.error(request, "Cette proposition n'est plus modifiable ni executable (expiree, rejetee ou deja traitee).")
            return redirect("trade_approval:detail", pk=pk)
        if request.POST.get("action") == "reject":
            obj.status, obj.decided_at = "rejected", now
            obj.save(update_fields=["status", "decided_at"])
            flash.success(request, "Proposition rejetee. Aucun ordre envoye.")
            return redirect("trade_approval:detail", pk=pk)
        try:
            vals = {"entry": float(request.POST["entry"]), "stop_loss": float(request.POST["stop_loss"]),
                    "take_profit": float(request.POST["take_profit"]),
                    "capital_usdt": float(request.POST["capital_usdt"]), "leverage": int(request.POST["leverage"])}
            if min(vals.values()) <= 0:
                raise ValueError
        except (KeyError, ValueError):
            flash.error(request, "Valeurs invalides : entree, SL, TP, capital et levier doivent etre des nombres positifs.")
            return redirect("trade_approval:detail", pk=pk)
        action = request.POST.get("action")
        if action == "save":
            for k, v in vals.items():
                setattr(obj, k, v)
            obj.save()
            flash.success(request, "Parametres enregistres. Aucun ordre envoye.")
            return redirect("trade_approval:detail", pk=pk)
        if action == "execute":
            if emergency_active():
                flash.error(request, "ARRET D'URGENCE actif : aucune nouvelle position n'est autorisee.")
                return redirect("trade_approval:detail", pk=pk)
            if request.POST.get("confirm") != "on":
                flash.error(request, "Coche la case de confirmation pour executer.")
                return redirect("trade_approval:detail", pk=pk)
            if settings.TRADING_MODE == "REAL" and request.POST.get("real_confirm", "").strip() != "REAL":
                flash.error(request, "Mode REEL : tape REAL pour confirmer l'utilisation d'argent reel.")
                return redirect("trade_approval:detail", pk=pk)
            with transaction.atomic():
                obj = TradeProposal.objects.select_for_update().get(pk=pk)
                if obj.exec_status != "none":
                    flash.error(request, "Deja execute : une proposition n'est jamais executee deux fois.")
                    return redirect("trade_approval:detail", pk=pk)
                for k, v in vals.items():
                    setattr(obj, k, v)
                obj.status, obj.exec_status = "accepted", "executing"
                obj.decided_at = now
                obj.save()
            _run_execution(request, obj)
            return redirect("trade_approval:detail", pk=pk)
    d = obj.direction
    gain = tg_text.pnl_percent(obj.entry, obj.take_profit, obj.leverage, d)
    loss = tg_text.pnl_percent(obj.entry, obj.stop_loss, obj.leverage, d)
    st = {"equity_usdt": settings.KPS_DEMO_EQUITY_USDT, "daily_loss_pct": 0.0, **{k: v for k, v in risk_state().items() if k != "daily_loss_usdt"}}
    chk = check_plan({"direction": d, "entry": obj.entry, "stop_loss": obj.stop_loss, "take_profit": obj.take_profit,
                      "capital_usdt": obj.capital_usdt, "leverage": obj.leverage}, st, _limits())
    return render(request, "trade_approval.html", {
        "p": obj, "editable": editable, "gain": gain, "loss": loss,
        "gain_usdt": obj.capital_usdt * gain / 100, "loss_usdt": obj.capital_usdt * loss / 100,
        "violations": chk["violations"], "payload": obj.payload, "real": settings.TRADING_MODE == "REAL"})


def _run_execution(request, obj):
    p = {"id": obj.pk, "symbol": obj.symbol, "direction": obj.direction, "entry": obj.entry,
         "stop_loss": obj.stop_loss, "take_profit": obj.take_profit, "leverage": obj.leverage,
         "capital_usdt": obj.capital_usdt}
    try:
        trader = trader_from_settings()
        res = execute(trader, p, {"max_slippage_pct": settings.KPS_MAX_SLIPPAGE_PCT, "limits": _limits()}, risk_state())
    except GateTradeError as e:
        res = {"ok": False, "error": str(e), "log": [f"ECHEC : {e}"]}
    obj.exec_log = res.get("log", [])
    obj.gate_order_id = res.get("gate_order_id", "")
    obj.sl_order_id, obj.tp_order_id = res.get("sl_order_id", ""), res.get("tp_order_id", "")
    if res["ok"]:
        obj.exec_status, obj.fill_price, obj.size_contracts = "open", res["fill_price"], res["size"]
        obj.executed_at = timezone.now()
        txt = (f"POSITION OUVERTE #{obj.pk} - {obj.symbol} {obj.direction} ({obj.mode}, marge ISOLATED)\n"
               f"Execute a {res['fill_price']:g} | {abs(res['size'])} contrat(s) | levier x{obj.leverage}\n"
               f"Stop Loss {obj.stop_loss:g} | Take Profit {obj.take_profit:g}\nOrdre Gate : {res['gate_order_id']} (confirme)")
        if res.get("warning"):
            txt += "\nATTENTION : " + res["warning"]
        flash.success(request, "Gate a confirme l'ouverture de la position.")
    else:
        obj.exec_status = "error"
        txt = f"EXECUTION ECHOUEE #{obj.pk} {obj.symbol} : {res['error']}"
        flash.error(request, res["error"])
    obj.save()
    telegram.send_message(txt)


@login_required
def positions(request):
    if request.method == "POST":
        try:
            n = sync_open_trades(trader_from_settings(), TradeProposal)
            flash.success(request, f"Synchronisation terminee : {n} position(s) fermee(s) detectee(s).")
        except GateTradeError as e:
            flash.error(request, f"Synchronisation impossible : {e}")
        return redirect("trade_approval:positions")
    items = TradeProposal.objects.exclude(exec_status="none").exclude(exec_status="executing").order_by("-executed_at", "-created_at")
    closed = [t for t in items if t.exec_status == "closed" and t.net_pnl is not None]
    stats = {"wins": sum(1 for t in closed if t.net_pnl > 0), "losses": sum(1 for t in closed if t.net_pnl <= 0),
             "pnl": sum(t.net_pnl for t in closed), "n": len(closed)}
    stats["rate"] = round(100 * stats["wins"] / stats["n"], 1) if stats["n"] else None
    return render(request, "positions.html", {"items": items, "stats": stats})
