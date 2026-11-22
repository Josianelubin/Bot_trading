import re
from datetime import timedelta

from django.conf import settings
from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.trade_approval.models import TradeProposal

from .models import SymbolAnalysis


@login_required
def analysis_list(request):
    return render(request, "analysis_list.html", {"items": SymbolAnalysis.objects.all()})


@login_required
def analysis_detail(request, symbol):
    obj = get_object_or_404(SymbolAnalysis, symbol=symbol)
    return render(request, "analysis_detail.html", {"a": obj, "p": obj.payload, "f": obj.payload.get("fundamental", {}),
                                                    "mode": settings.TRADING_MODE})


@login_required
def chart_png(request, symbol):
    obj = get_object_or_404(SymbolAnalysis, symbol=symbol)
    if not obj.chart_png:
        raise Http404
    return HttpResponse(bytes(obj.chart_png), content_type="image/png")


@login_required
@require_POST
def create_trade(request, symbol):
    """Prepare un trade manuel : TU definis direction, entree, SL et TP ; rien n'est envoye a Gate ici."""
    obj = SymbolAnalysis.objects.filter(symbol=symbol).first()
    if not re.fullmatch(r"[A-Z0-9]{2,20}_USDT", symbol):
        flash.error(request, "Paire invalide.")
        return redirect("live:page")
    try:
        d = request.POST["direction"]
        vals = {k: float(request.POST[k]) for k in ("entry", "stop_loss", "take_profit", "capital_usdt")}
        lev = int(request.POST["leverage"])
        if d not in ("LONG", "SHORT") or min(vals.values()) <= 0 or lev <= 0:
            raise ValueError
    except (KeyError, ValueError):
        flash.error(request, "Valeurs invalides pour le trade.")
        return redirect("live:page")
    p = obj.payload if obj else {}
    t = TradeProposal.objects.create(
        symbol=symbol, direction=d, mode=settings.TRADING_MODE, leverage=lev, score_technical=obj.score if obj else 0,
        expires_at=timezone.now() + timedelta(minutes=settings.KPS_PROPOSAL_TTL_MINUTES * 2),
        payload={"source": "manuel", "tools": p.get("tools", []), "reasons": p.get("reasons", [])[:14],
                 "risks": ["Trade prepare manuellement depuis la page d'analyse"]}, **vals)
    return redirect("trade_approval:detail", pk=t.pk)
