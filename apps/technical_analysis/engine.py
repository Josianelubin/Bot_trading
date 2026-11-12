"""Moteur technique : execute toutes les strategies et fusionne leurs avis (sur 40 points)."""
from apps.smart_money import ict
from . import bollinger, divergence, elliott, indicators as ind, strategies as st, wyckoff

TOTAL_MAX = 10 + 10 + 8 + 7 + 8 + 5 + 7 + ict.MAX_SCORE + wyckoff.MAX_SCORE + elliott.MAX_SCORE + divergence.MAX_SCORE  # = 88
MIN_CANDLES = 60


def analyze_all(candles):
    if len(candles) < MIN_CANDLES:
        return {"direction": "NEUTRE", "score": 0, "tools": [], "strategies": [], "suggested": None,
                "reasons": ["DONNEES INDISPONIBLES : au moins 60 bougies requises"]}
    closes = [x["c"] for x in candles]
    rsi_last = ind.rsi(closes)[-1]
    boll = bollinger.analyze(closes, rsi=rsi_last)
    results = [
        {"name": "bollinger", "direction": boll["direction"], "score": boll["score"],
         "max": bollinger.MAX_SCORE, "reasons": boll["reasons"]},
        st.turtle(candles), st.dow(candles), st.livermore(candles),
        st.raschke_holy_grail(candles), st.raschke_momentum(candles), st.wilder(candles),
        ict.analyze(candles), wyckoff.analyze(candles), elliott.analyze(candles),
        divergence.analyze(candles),
    ]
    tally = {"LONG": 0, "SHORT": 0}
    for r in results:
        if r["direction"] in tally:
            tally[r["direction"]] += r["score"]
    dom = max(tally, key=tally.get)
    opp = "SHORT" if dom == "LONG" else "LONG"
    reasons = [x for r in results for x in r["reasons"]]
    agree = sum(1 for r in results if r["direction"] == dom)
    if tally[dom] == 0:
        direction, score = "NEUTRE", 0
    elif agree < 2:
        direction, score = "NEUTRE", 0
        reasons.append("Signal isole (une seule strategie) : confluence insuffisante, aucun signal")
    elif tally[opp] / tally[dom] > 0.5:
        direction, score = "NEUTRE", 0
        reasons.append(f"Strategies contradictoires (LONG {tally['LONG']} / SHORT {tally['SHORT']}) : aucun signal")
    else:
        direction = dom
        score = round((tally[dom] - tally[opp]) * 40 / TOTAL_MAX)
    atr_last = ind.atr(candles, 14)[-1]
    suggested = None
    if direction != "NEUTRE" and atr_last:
        e = closes[-1]
        suggested = {"entry": e, "atr": atr_last,
                     "stop_loss": e - 2 * atr_last if direction == "LONG" else e + 2 * atr_last}
    return {"direction": direction, "score": score, "max": 40, "tally": tally, "reasons": reasons,
            "tools": [r["name"] for r in results if r["direction"] != "NEUTRE"] or [r["name"] for r in results],
            "strategies": results, "suggested": suggested,
            "zones": next((r.get("zones") for r in results if r["name"] == "ict"), None)}


def analyze_mtf(c4h, c1h, c15):
    """4H = tendance principale, 1H = confirmation, 15M = entree. Un signal 15M contraire
    a la direction 4H ou 1H est annule (aucun trade)."""
    r15, r4, r1 = analyze_all(c15), analyze_all(c4h), analyze_all(c1h)
    out = dict(r15)
    out["mtf"] = {"4h": r4["direction"], "1h": r1["direction"], "15m": r15["direction"]}
    if r15["direction"] != "NEUTRE":
        for tf, r in (("4H", r4), ("1H", r1)):
            if r["direction"] not in ("NEUTRE", r15["direction"]):
                out.update(direction="NEUTRE", score=0)
                out["reasons"] = out["reasons"] + [f"Signal 15M contraire a la tendance {tf} : aucun trade"]
                break
        else:
            out["reasons"] = out["reasons"] + [f"Multi-timeframe : 4H {r4['direction']}, 1H {r1['direction']} (aucune contradiction)"]
    return out
