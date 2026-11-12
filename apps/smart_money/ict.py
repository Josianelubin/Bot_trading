"""Smart Money Concepts (ICT, Michael J. Huddleston) : structure BOS/CHoCH, Fair Value Gaps,
Imbalances, Order Blocks, liquidite (equal highs/lows, sweeps).
Regles documentees ; chaque FVG ou OB n'est PAS une opportunite : il faut un decalage de
structure recent ET un prix dans une zone valide (non invalidee)."""
from apps.technical_analysis import indicators as ind
from apps.technical_analysis.strategies import swings

MAX_SCORE = 12


def structure(c, w=2):
    n = len(c)
    hs = [i for i in swings([x["h"] for x in c], "high", w) if i < n - 3]
    ls = [i for i in swings([x["l"] for x in c], "low", w) if i < n - 3]
    if len(hs) < 2 or len(ls) < 2:
        return {"trend": "INDETERMINE", "event": None, "labels": []}
    h1, h2 = c[hs[-2]]["h"], c[hs[-1]]["h"]
    l1, l2 = c[ls[-2]]["l"], c[ls[-1]]["l"]
    trend = "UP" if h2 > h1 and l2 > l1 else "DOWN" if h2 < h1 and l2 < l1 else "RANGE"
    labels = ["HH" if h2 > h1 else "LH", "HL" if l2 > l1 else "LL"]
    last_high, last_low = h2, l2
    closes = [x["c"] for x in c[-3:]]
    event = None
    if max(closes) > last_high:
        kind = "BOS" if trend == "UP" else "CHoCH" if trend == "DOWN" else "MSS"
        event = {"type": kind, "dir": "LONG", "level": last_high}
    elif min(closes) < last_low:
        kind = "BOS" if trend == "DOWN" else "CHoCH" if trend == "UP" else "MSS"
        event = {"type": kind, "dir": "SHORT", "level": last_low}
    return {"trend": trend, "event": event, "labels": labels}


def fvgs(c, atr_val, min_size=0.5, recent=60):
    out, n = [], len(c)
    for i in range(max(2, n - recent), n):
        a, k = c[i - 2], c[i]
        if a["h"] < k["l"] and (k["l"] - a["h"]) >= min_size * atr_val:
            lo, hi, status = a["h"], k["l"], "ouvert"
            for j in range(i + 1, n):
                if c[j]["c"] < lo:
                    status = "invalide"; break
                if c[j]["l"] <= lo:
                    status = "comble"; break
                if c[j]["l"] < hi:
                    status = "partiel"
            out.append({"type": "bullish", "lo": lo, "hi": hi, "index": i, "status": status})
        elif a["l"] > k["h"] and (a["l"] - k["h"]) >= min_size * atr_val:
            lo, hi, status = k["h"], a["l"], "ouvert"
            for j in range(i + 1, n):
                if c[j]["c"] > hi:
                    status = "invalide"; break
                if c[j]["h"] >= hi:
                    status = "comble"; break
                if c[j]["h"] > lo:
                    status = "partiel"
            out.append({"type": "bearish", "lo": lo, "hi": hi, "index": i, "status": status})
    return out


def imbalances(c, atr_val, recent=30):
    out = []
    for i in range(max(0, len(c) - recent), len(c)):
        x = c[i]
        body, rng = abs(x["c"] - x["o"]), x["h"] - x["l"]
        if rng > 0 and body >= 1.5 * atr_val and body / rng >= 0.7:
            out.append({"type": "acheteur" if x["c"] > x["o"] else "vendeur",
                        "lo": min(x["o"], x["c"]), "hi": max(x["o"], x["c"]), "index": i})
    return out


def order_blocks(c, atr_val, recent=60):
    out, n = [], len(c)
    for i in range(max(10, n - recent), n):
        x = c[i]
        body = abs(x["c"] - x["o"])
        if body < 1.5 * atr_val:
            continue
        prior = c[i - 10:i]
        if x["c"] > x["o"] and x["c"] > max(p["h"] for p in prior):
            cand = [j for j in range(i - 1, max(i - 6, -1), -1) if c[j]["c"] < c[j]["o"]]
            if cand:
                j = cand[0]
                lo, hi = c[j]["l"], c[j]["h"]
                invalid = any(c[m]["c"] < lo for m in range(i + 1, n))
                out.append({"type": "bullish", "lo": lo, "hi": hi, "index": j, "valid": not invalid})
        elif x["c"] < x["o"] and x["c"] < min(p["l"] for p in prior):
            cand = [j for j in range(i - 1, max(i - 6, -1), -1) if c[j]["c"] > c[j]["o"]]
            if cand:
                j = cand[0]
                lo, hi = c[j]["l"], c[j]["h"]
                invalid = any(c[m]["c"] > hi for m in range(i + 1, n))
                out.append({"type": "bearish", "lo": lo, "hi": hi, "index": j, "valid": not invalid})
    return out


def liquidity(c, w=2, tol=0.001, recent=60):
    n = len(c)
    start = max(0, n - recent)
    hs = [c[i]["h"] for i in swings([x["h"] for x in c], "high", w) if i >= start]
    ls = [c[i]["l"] for i in swings([x["l"] for x in c], "low", w) if i >= start]
    res = {"equal_highs": None, "equal_lows": None, "sweep": None}
    for a in hs:
        if sum(abs(b - a) / a <= tol for b in hs) >= 2:
            res["equal_highs"] = max(res["equal_highs"] or 0, a)
    for a in ls:
        if sum(abs(b - a) / a <= tol for b in ls) >= 2:
            res["equal_lows"] = a if res["equal_lows"] is None else min(res["equal_lows"], a)
    close = c[-1]["c"]
    if res["equal_highs"] and max(x["h"] for x in c[-2:]) > res["equal_highs"] and close < res["equal_highs"]:
        res["sweep"] = {"side": "BSL", "dir": "SHORT", "level": res["equal_highs"]}
    elif res["equal_lows"] and min(x["l"] for x in c[-2:]) < res["equal_lows"] and close > res["equal_lows"]:
        res["sweep"] = {"side": "SSL", "dir": "LONG", "level": res["equal_lows"]}
    return res


def analyze(c):
    if len(c) < 50:
        return {"name": "ict", "direction": "NEUTRE", "score": 0, "max": MAX_SCORE, "zones": {},
                "reasons": ["DONNEES INDISPONIBLES : au moins 50 bougies requises (ICT)"]}
    a = ind.atr(c, 14)[-1]
    s, fv, obs, imb, liq = structure(c), fvgs(c, a), order_blocks(c, a), imbalances(c, a), liquidity(c)
    last = c[-1]
    best = {"LONG": (0, [], None), "SHORT": (0, [], None)}
    for d in ("LONG", "SHORT"):
        pts, why, inval = 0, [], None
        ev = s["event"]
        if ev and ev["dir"] == d:
            pts += 4 if ev["type"] in ("CHoCH", "MSS") else 3
            why.append(f"{ev['type']} {'haussier' if d == 'LONG' else 'baissier'} (cassure de {ev['level']:g})")
        elif (d == "LONG" and s["trend"] == "UP") or (d == "SHORT" and s["trend"] == "DOWN"):
            pts += 1
            why.append("Structure alignee avec la direction (" + "/".join(s["labels"]) + ")")
        else:
            continue
        zone_pts = 0
        typ = "bullish" if d == "LONG" else "bearish"
        for ob in reversed(obs):
            if ob["type"] == typ and ob["valid"] and last["l"] <= ob["hi"] and last["h"] >= ob["lo"]:
                zone_pts = 4
                inval = ob["lo"] if d == "LONG" else ob["hi"]
                why.append(f"Retest d'un Order Block {typ} [{ob['lo']:g} - {ob['hi']:g}] ; invalidation {inval:g}")
                break
        if not zone_pts:
            for g in reversed(fv):
                if g["type"] == typ and g["status"] in ("ouvert", "partiel") and last["l"] <= g["hi"] and last["h"] >= g["lo"]:
                    zone_pts = 3
                    inval = g["lo"] if d == "LONG" else g["hi"]
                    why.append(f"Prix dans un FVG {typ} {g['status']} [{g['lo']:g} - {g['hi']:g}]")
                    break
        if not zone_pts:
            continue  # pas de zone valide : pas de signal
        pts += zone_pts
        if liq["sweep"] and liq["sweep"]["dir"] == d:
            pts += 3
            why.append(f"Liquidity sweep {liq['sweep']['side']} au niveau {liq['sweep']['level']:g} puis retour (fake breakout)")
        best[d] = (min(pts, MAX_SCORE), why, inval)
    L, S = best["LONG"], best["SHORT"]
    if L[0] == 0 and S[0] == 0:
        direction, score, reasons, inval = "NEUTRE", 0, ["ICT : pas de decalage de structure avec prix dans une zone valide"], None
    elif L[0] and S[0] and min(L[0], S[0]) / max(L[0], S[0]) > 0.5:
        direction, score, reasons, inval = "NEUTRE", 0, ["ICT : signaux LONG et SHORT contradictoires"], None
    else:
        direction = "LONG" if L[0] > S[0] else "SHORT"
        score, reasons, inval = best[direction]
    return {"name": "ict", "direction": direction, "score": score, "max": MAX_SCORE,
            "reasons": reasons, "invalidation": inval,
            "zones": {"fvg": fv, "order_blocks": obs, "imbalances": imb, "liquidity": liq,
                      "structure": {"trend": s["trend"], "event": s["event"], "labels": s["labels"]}}}
