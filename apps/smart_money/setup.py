"""Setup ICT complet (Smart Money) : decalage de structure (CHoCH/MSS) -> deplacement (imbalance) ->
retracement en zone OTE (62 % - 79 % de la jambe, entree ideale 70,5 %) en DISCOUNT (LONG) ou PREMIUM (SHORT),
avec confluences : balayage de liquidite, FVG, Order Block, tendance de l'unite de temps superieure.
Stop Loss au-dela de l'origine de la jambe (invalidation) ; objectifs : sommet de la jambe (liquidite),
puis extensions -27 % et -62 %. Le SHORT est calcule par symetrie (prix inverses).
Aucune garantie : c'est un ensemble de regles, a valider par backtest."""
from apps.technical_analysis import indicators as ind
from apps.technical_analysis.strategies import swings

MAX_SCORE = 15
MIN_SCORE = 8
OTE_LO, OTE_HI, SWEET = 0.62, 0.79, 0.705


def _invert(c):
    out = []
    for x in c:
        y = {"o": -x["o"], "h": -x["l"], "l": -x["h"], "c": -x["c"], "v": x["v"]}
        if "t" in x:
            y["t"] = x["t"]
        out.append(y)
    return out


def _long(c, atr_val, htf_trend=None, lookback=60):
    n = len(c)
    if n < 40 or not atr_val:
        return None
    start = max(0, n - lookback)
    hs = swings([x["h"] for x in c], "high", 2)
    ls = swings([x["l"] for x in c], "low", 2)
    for iL in reversed([i for i in ls if i >= start]):
        L = c[iL]["l"]
        prev_h = [i for i in hs if i < iL]
        if not prev_h:
            continue
        PH = c[prev_h[-1]]["h"]
        iB = next((i for i in range(iL + 1, n) if c[i]["c"] > PH), None)  # CHoCH / MSS : cloture au-dessus du dernier sommet
        if iB is None:
            continue
        disp = [i for i in range(iL + 1, iB + 1) if c[i]["c"] > c[i]["o"] and c[i]["c"] - c[i]["o"] >= atr_val]
        if not disp:
            continue
        iH = max(range(iL, n), key=lambda i: c[i]["h"])
        H = c[iH]["h"]
        leg = H - L
        if iH <= iL or leg < 2 * atr_val:
            continue
        if any(c[i]["c"] < L for i in range(iL + 1, n)):
            continue  # origine cassee : setup invalide
        z_lo, z_hi = H - OTE_HI * leg, H - OTE_LO * leg
        eq = H - 0.5 * leg
        last = c[-1]
        reasons, conf, score = [], [], 0
        score += 3
        conf.append("CHoCH / MSS")
        reasons.append(f"Decalage de structure (CHoCH/MSS) : cloture au-dessus du dernier sommet {PH:g}")
        score += 3
        conf.append("Zone OTE")
        reasons.append(f"Zone OTE (62-79 % de la jambe {L:g} -> {H:g}) : {z_lo:g} - {z_hi:g}")
        score += 1
        conf.append("Discount")
        reasons.append(f"Entree en DISCOUNT (sous l'equilibre 50 % = {eq:g})")
        prior_lows = [c[i]["l"] for i in ls if max(0, iL - 40) <= i < iL]
        tie = 0.1 * atr_val  # les creux quasi egaux comptent comme le meme creux
        if any(x > L + tie for x in prior_lows) and not any(x < L - tie for x in prior_lows):
            score += 2
            conf.append("Liquidity sweep")
            reasons.append("Balayage de liquidite (Sell Side Liquidity) sous les creux precedents puis retournement")
        # FVG haussier dans la jambe, recoupant la zone OTE
        entry_lo, entry_hi = z_lo, z_hi
        fvg = None
        for k in range(iL + 2, min(iH + 2, n)):
            g_lo, g_hi = c[k - 2]["h"], c[k]["l"]
            if g_hi - g_lo >= 0.3 * atr_val and g_lo <= z_hi and g_hi >= z_lo:
                fvg = (max(g_lo, z_lo), min(g_hi, z_hi))
        if fvg:
            score += 2
            conf.append("FVG")
            reasons.append(f"FVG haussier dans la zone OTE : {fvg[0]:g} - {fvg[1]:g}")
            entry_lo, entry_hi = fvg
        # Order Block : derniere bougie baissiere avant le deplacement
        ob = None
        for j in range(disp[0] - 1, max(disp[0] - 7, iL - 1), -1):
            if c[j]["c"] < c[j]["o"]:
                ob = (c[j]["l"], c[j]["h"])
                break
        tol = 0.25 * atr_val
        if ob and ob[0] <= z_hi + tol and ob[1] >= z_lo - tol:
            score += 2
            conf.append("Order Block")
            reasons.append(f"Order Block haussier proche de la zone OTE : {ob[0]:g} - {ob[1]:g}")
            lo, hi = max(ob[0], z_lo), min(ob[1], z_hi)
            if lo <= hi and not fvg:
                entry_lo, entry_hi = lo, hi
        prev_highs = [c[i]["h"] for i in hs if max(0, iL - 40) <= i < iL]
        if prev_highs and H > max(prev_highs):
            score += 1
            conf.append("BOS")
            reasons.append(f"BOS : nouveau sommet {H:g} au-dessus de la structure precedente {max(prev_highs):g}")
        conf.append("Imbalance")
        reasons.append("Deplacement haussier (imbalance acheteur) a l'origine de la jambe")
        if htf_trend == "UP":
            score += 2
            conf.append("Tendance HTF")
            reasons.append("Alignee avec la tendance de l'unite de temps superieure (haussiere)")
        elif htf_trend == "DOWN":
            score -= 3
            reasons.append("ATTENTION : contre la tendance de l'unite de temps superieure (baissiere)")
        score = min(score, MAX_SCORE)
        entry = (entry_lo + entry_hi) / 2 if (fvg or ob) and entry_lo <= entry_hi else H - SWEET * leg
        entry = min(max(entry, z_lo), z_hi)
        sl = L - 0.25 * atr_val
        dist = entry - sl
        if dist < 0.5 * atr_val:
            continue
        tps = [H, H + 0.27 * leg, H + 0.62 * leg]
        if (tps[0] - entry) / dist < 1.0:
            continue
        status = "zone" if (last["l"] <= z_hi and last["c"] >= z_lo - 0.0) else "attente" if last["c"] > z_hi else "profond"
        return {"direction": "LONG", "status": status, "entry": entry, "zone": [z_lo, z_hi], "equilibrium": eq,
                "stop_loss": sl, "take_profits": tps, "invalidation": L, "score": score, "max": MAX_SCORE,
                "grade": "A" if score >= 11 else "B" if score >= MIN_SCORE else "C", "confluences": conf, "reasons": reasons,
                "leg": {"low": L, "high": H, "low_index": iL, "high_index": iH}, "htf_trend": htf_trend}
    return None


def _flip(r):
    if not r:
        return None
    n = lambda v: -v
    return {**r, "direction": "SHORT", "entry": n(r["entry"]), "zone": [n(r["zone"][1]), n(r["zone"][0])],
            "equilibrium": n(r["equilibrium"]), "stop_loss": n(r["stop_loss"]),
            "take_profits": [n(x) for x in r["take_profits"]], "invalidation": n(r["invalidation"]),
            "leg": {**r["leg"], "low": n(r["leg"]["high"]), "high": n(r["leg"]["low"])},
            "confluences": [("Premium" if x == "Discount" else x) for x in r["confluences"]],
            "reasons": [x.replace("DISCOUNT", "PREMIUM").replace("haussier", "baissier").replace("acheteur", "vendeur")
                        .replace("Sell Side", "Buy Side").replace("au-dessus du dernier sommet", "sous le dernier creux")
                        .replace("sous les creux", "au-dessus des sommets").replace("sous l'equilibre", "au-dessus de l'equilibre")
                        .replace("haussiere", "baissiere") for x in r["reasons"]]}


def find_setup(c, htf_trend=None, min_score=MIN_SCORE):
    """Meilleur setup (LONG ou SHORT) sur des bougies CLOTUREES, ou None."""
    if len(c) < 40:
        return None
    a = ind.atr(c, 14)[-1]
    if not a:
        return None
    flip_htf = {"UP": "DOWN", "DOWN": "UP"}.get(htf_trend, htf_trend)
    cands = [r for r in (_long(c, a, htf_trend), _flip(_long(_invert(c), a, flip_htf))) if r and r["score"] >= min_score]
    return max(cands, key=lambda r: r["score"]) if cands else None
