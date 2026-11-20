"""Bouton SCANNER : analyse les VRAIES bougies cloturees du graphique choisi.
Resultat horodate ; ATTENTE si aucune configuration assez confirmee. Aucune donnee inventee."""
from datetime import datetime, timezone

from apps.smart_money import ict
from apps.smart_money.setup import find_setup
from apps.technical_analysis import bollinger, engine, indicators as ind

DEFAULT = {"min_score": 24, "r_multiples": (1.0, 2.0, 3.0), "leverage": 5, "capital_usdt": 20.0}


def _v(label, value, verdict):
    return {"name": label, "value": value, "verdict": verdict}


def potential(direction, entry, sl, tps, leverage, capital):
    """Gain / perte potentiels (hors frais et funding) : en % du prix, en % de la marge (x levier) et en USDT."""
    sign = 1 if direction == "LONG" else -1
    risk = abs(entry - sl)
    rows = []
    for tp in tps:
        gp = sign * (tp - entry) / entry * 100
        rows.append({"price": tp, "gain_price_pct": gp, "gain_margin_pct": gp * leverage,
                     "gain_usdt": capital * gp * leverage / 100, "reward_risk": abs(tp - entry) / risk if risk else None})
    lp = sign * (sl - entry) / entry * 100
    liq = entry * (1 - 1 / leverage) if direction == "LONG" else entry * (1 + 1 / leverage)
    return {"leverage": leverage, "capital_usdt": capital, "targets": rows, "stop_price": sl,
            "loss_price_pct": lp, "loss_margin_pct": lp * leverage, "loss_usdt": capital * lp * leverage / 100,
            "liquidation_approx": liq, "stop_beyond_liquidation": abs(entry - sl) / entry >= 0.8 / leverage}


def scan(closed, symbol, timeframe, cfg=None, htf_closed=None):
    cfg = {**DEFAULT, **(cfg or {})}
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    base = {"symbol": symbol, "timeframe": timeframe, "market": "Gate Futures USDT", "timestamp": stamp}
    if len(closed) < engine.MIN_CANDLES:
        return {**base, "status": "indisponible", "direction": "ATTENTE",
                "message": f"DONNEES INDISPONIBLES : au moins {engine.MIN_CANDLES} bougies cloturees requises"}
    a = engine.analyze_all(closed)
    closes = [x["c"] for x in closed]
    last = closes[-1]
    rsi = ind.rsi(closes)[-1]
    m = ind.macd(closes)
    adx = ind.adx(closed)["adx"][-1]
    atr = ind.atr(closed, 14)[-1]
    vw = ind.vwap(closed)[-1]
    e = {p: ind.ema(closes, p)[-1] for p in (9, 21, 50, 200)}
    bands = [b for b in bollinger.compute_bands(closes) if b]
    bw_now, bw_before = bands[-1]["bandwidth"], bands[-21]["bandwidth"] if len(bands) > 21 else None
    vols = [x["v"] for x in closed]
    vol_up = sum(vols[-5:]) / 5 > sum(vols[-25:-5]) / 20
    fib = ind.fib_levels(closed)
    near = min(fib["levels"].items(), key=lambda kv: abs(kv[1] - last))

    if e[9] > e[21] > e[50]:
        trend = "Haussiere"
    elif e[9] < e[21] < e[50]:
        trend = "Baissiere"
    else:
        trend = "Mixte / neutre"
    macd_pos = m["hist"][-1] is not None and m["hist"][-1] > 0
    confirmations = [
        _v("RSI (14)", round(rsi, 2), "haussier" if rsi >= 55 else "baissier" if rsi <= 45 else "neutre"),
        _v("MACD (12,26,9)", round(m["hist"][-1], 6) if m["hist"][-1] is not None else None,
           "positif" if macd_pos else "negatif"),
        _v("EMA 9/21/50", f"{e[9]:g} / {e[21]:g} / {e[50]:g}", trend.lower()),
        _v("EMA 200", round(e[200], 6) if e[200] else None,
           "au-dessus" if e[200] and last > e[200] else "en dessous" if e[200] else "indisponible"),
        _v("Bollinger", f"largeur {bw_now:.4f}",
           "expansion" if bw_before and bw_now > bw_before else "contraction"),
        _v("ADX (14)", round(adx, 1) if adx is not None else None,
           "tendance forte" if adx and adx >= 25 else "tendance faible"),
        _v("ATR (14)", round(atr, 6) if atr else None, "risque"),
        _v("VWAP (jour)", round(vw, 6), "prix au-dessus" if last > vw else "prix en dessous"),
        _v("Volume", f"{vols[-1]:g}", "en hausse" if vol_up else "en baisse"),
        _v("Fibonacci", f"{near[0]} -> {near[1]:g}", f"niveau proche ({fib['trend']})"),
    ]
    htf_trend = ict.structure(htf_closed)["trend"] if htf_closed and len(htf_closed) >= 30 else None
    setup = find_setup(closed, htf_trend=htf_trend if htf_trend in ("UP", "DOWN") else None)
    out = {**base, "trend": trend, "htf_trend": htf_trend, "ict": setup, "score": a["score"], "max_score": 40, "direction_raw": a["direction"],
           "tools": a["tools"], "reasons": a["reasons"], "confirmations": confirmations,
           "indicators": {"rsi": rsi, "macd_hist": m["hist"][-1], "adx": adx, "atr": atr, "vwap": vw},
           "mtf": None}
    lev, cap = cfg["leverage"], cfg["capital_usdt"]
    if setup:
        d = setup["direction"]
        if a["direction"] not in ("NEUTRE", d):
            return {**out, "status": "ATTENTE", "direction": "ATTENTE",
                    "message": f"ATTENTE : setup ICT {d} mais les autres strategies indiquent {a['direction']} (contradiction)"}
        aligned = sum(1 for r in a["strategies"] if r["direction"] == d)
        status = "signal" if setup["status"] in ("zone", "profond") else "signal_limite"
        note = {"zone": "prix dans la zone OTE : entree possible",
                "profond": "prix sous la zone OTE (retracement profond) : respecter l'invalidation",
                "attente": "ordre LIMITE : attendre le retracement dans la zone OTE"}[setup["status"]]
        tps = setup["take_profits"]
        return {**out, "status": status, "direction": d, "entry": setup["entry"], "stop_loss": setup["stop_loss"],
                "take_profits": tps, "entry_mode": setup["status"], "aligned_strategies": aligned,
                "message": f"Setup ICT {d} (grade {setup['grade']}, {setup['score']}/{setup['max']}) sur {timeframe} : {note}",
                "potential": potential(d, setup["entry"], setup["stop_loss"], tps, lev, cap)}
    if a["direction"] == "NEUTRE" or a["score"] < cfg["min_score"] or not a.get("suggested"):
        why = ("Strategies contradictoires, signal isole ou aucun setup ICT" if a["direction"] == "NEUTRE"
               else f"Score {a['score']}/40 inferieur au minimum {cfg['min_score']}")
        return {**out, "status": "ATTENTE", "direction": "ATTENTE", "message": "ATTENTE : " + why}
    d, entry, sl = a["direction"], last, a["suggested"]["stop_loss"]
    dist = abs(entry - sl)
    sign = 1 if d == "LONG" else -1
    tps = [entry + sign * r * dist for r in cfg["r_multiples"]]
    return {**out, "status": "signal", "direction": d, "entry": entry, "stop_loss": sl, "entry_mode": "marche",
            "take_profits": tps, "r_multiples": list(cfg["r_multiples"]), "aligned_strategies": sum(1 for r in a["strategies"] if r["direction"] == d),
            "message": f"Signal {d} sur {timeframe} (strategies multiples, score {a['score']}/40)",
            "potential": potential(d, entry, sl, tps, lev, cap)}
