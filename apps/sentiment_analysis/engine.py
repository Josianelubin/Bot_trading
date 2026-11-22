"""Analyse du SENTIMENT (25 points) : Fear & Greed, funding rate, ratio long/short, liquidations, open interest.
Fonctions pures, a partir de donnees REELLES. Une source absente est ignoree (jamais inventee) ; si tout manque :
DONNEES INDISPONIBLES. Un sentiment neutre vaut la moitie des points ; aligne = 100 %, contraire = 0 %."""

MAX_SCORE = 25
W = {"fear_greed": 0.15, "funding": 0.25, "long_short": 0.20, "liquidations": 0.15, "open_interest": 0.25}


def _fng(v):
    return 0.7 if v <= 20 else 0.3 if v <= 35 else -0.7 if v >= 80 else -0.3 if v >= 65 else 0.0


def _funding(f):
    return -0.7 if f >= 0.0005 else -0.3 if f >= 0.0002 else 0.7 if f <= -0.0005 else 0.3 if f <= -0.0002 else 0.0


def _lsr(r):
    return -0.5 if r > 1.8 else -0.2 if r > 1.3 else 0.5 if r < 0.6 else 0.2 if r < 0.85 else 0.0


def assess(data, direction, liq_hours=6):
    """data : {fear_greed:{value,label}|None, funding_rate:float|None, stats:[points contract_stats]|None}."""
    comps, labels, reasons = [], [], []
    d = data or {}
    fg = d.get("fear_greed")
    if fg and fg.get("value") is not None:
        b = _fng(fg["value"])
        comps.append(("fear_greed", b))
        reasons.append(f"Fear & Greed : {fg['value']} ({fg.get('label', '')})")
    fr = d.get("funding_rate")
    if fr is not None:
        comps.append(("funding", _funding(fr)))
        reasons.append(f"Funding rate : {fr * 100:+.4f} %")
    stats = [p for p in (d.get("stats") or []) if p.get("open_interest_usd") is not None]
    lsr = oi_up = price_up = None
    if stats:
        last = stats[-1]
        if last.get("lsr_account"):
            lsr = float(last["lsr_account"])
            comps.append(("long_short", _lsr(lsr)))
            reasons.append(f"Ratio long/short (comptes) : {lsr:.2f}")
        win = stats[-liq_hours:]
        ll = sum(float(p.get("long_liq_usd") or 0) for p in win)
        sl = sum(float(p.get("short_liq_usd") or 0) for p in win)
        oi_now = float(last["open_interest_usd"])
        if oi_now and (ll + sl) / oi_now >= 0.002:
            b = 0.4 if ll > 2 * sl else -0.4 if sl > 2 * ll else 0.0
            comps.append(("liquidations", b))
            reasons.append(f"Liquidations {liq_hours} h : longs {ll:,.0f} USD / shorts {sl:,.0f} USD")
        first = stats[0]
        if first.get("open_interest_usd") and first.get("mark_price") and last.get("mark_price"):
            oi_up = oi_now > float(first["open_interest_usd"]) * 1.01
            oi_dn = oi_now < float(first["open_interest_usd"]) * 0.99
            price_up = float(last["mark_price"]) > float(first["mark_price"])
            b = (0.4 if price_up else -0.4) if oi_up else (-0.1 if price_up else 0.1) if oi_dn else 0.0
            comps.append(("open_interest", b))
            if oi_up:
                labels.append("Accumulation (nouveaux longs)" if price_up else "Distribution (nouveaux shorts)")
            reasons.append("Open Interest " + ("en hausse" if oi_up else "en baisse" if oi_dn else "stable") + ", prix " + ("en hausse" if price_up else "en baisse"))
    if not comps:
        return {"available": False, "score": None, "bias": 0.0, "components": [], "labels": [],
                "reasons": ["DONNEES INDISPONIBLES : sentiment (Fear & Greed, funding, open interest introuvables)"]}
    tw = sum(W[n] for n, _ in comps)
    bias = sum(W[n] * b for n, b in comps) / tw
    if fr is not None and fg:
        if fr >= 0.0005 and fg["value"] >= 75:
            labels.append("Surchauffe haussiere")
        if fr <= -0.0005 and fg["value"] <= 25:
            labels.append("Surchauffe baissiere")
    if lsr is not None and (lsr > 2.5 or lsr < 0.5):
        labels.append("Desequilibre extreme des positions")
    if any("Surchauffe" in x or "Desequilibre" in x for x in labels):
        labels.append("Risque de retournement")
    signed = bias if direction == "LONG" else -bias if direction == "SHORT" else 0.0
    cov = min(1.0, len(comps) / 3)
    score = int(MAX_SCORE * (0.5 + 0.5 * signed * cov) + 0.5) if direction else None  # arrondi 0,5 vers le haut
    return {"available": True, "score": score, "bias": round(bias, 2), "components": [{"name": n, "bias": b} for n, b in comps],
            "labels": labels, "reasons": reasons}
