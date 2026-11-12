"""Methode de Wyckoff (regles simplifiees et verifiables) : range de trading, spring,
upthrust, Sign of Strength / Weakness, climax de volume, tendance precedente.
Le comptage des phases est une aide a la lecture, pas une certitude."""

MAX_SCORE = 9


def _r(direction, score, reasons, rng=None):
    return {"name": "wyckoff", "direction": direction, "score": score if direction != "NEUTRE" else 0,
            "max": MAX_SCORE, "reasons": reasons, "range": rng}


def _core(c, W=50):
    n = len(c)
    if n < W + 3:
        return _r("NEUTRE", 0, [f"DONNEES INDISPONIBLES : au moins {W + 3} bougies requises (Wyckoff)"])
    seg = c[-(W + 3):-3]
    rhi, rlo = max(x["h"] for x in seg), min(x["l"] for x in seg)
    rng = {"high": rhi, "low": rlo}
    if (rhi - rlo) / rlo > 0.15:
        return _r("NEUTRE", 0, ["Wyckoff : pas de range de trading (amplitude > 15 %)"], rng)
    avg_v = sum(x["v"] for x in seg) / len(seg)
    last3, close = c[-3:], c[-1]["c"]
    vol_hi = max(x["v"] for x in last3) >= 1.5 * avg_v
    prior = None
    if n >= W + 33:
        pr = c[-(W + 33):-(W + 3)]
        chg = (pr[-1]["c"] - pr[0]["c"]) / pr[0]["c"]
        prior = "baisse" if chg < -0.10 else "hausse" if chg > 0.10 else None
    info = []
    if any(x["v"] >= 2.5 * avg_v for x in seg):
        info.append("Climax de volume detecte dans le range (effort a surveiller)")
    spring = any(x["l"] < rlo for x in last3) and rlo < close < rhi
    ut = any(x["h"] > rhi for x in last3) and rlo < close < rhi
    if spring and not ut:
        return _r("LONG", 8 if prior == "baisse" else 6,
                  [f"Wyckoff : Spring sous le support {rlo:g} puis retour dans le range (phase C)"
                   + (" apres une baisse (accumulation)" if prior == "baisse" else "")] + info, rng)
    if ut and not spring:
        return _r("SHORT", 8 if prior == "hausse" else 6,
                  [f"Wyckoff : Upthrust au-dessus de la resistance {rhi:g} puis retour dans le range (phase C)"
                   + (" apres une hausse (distribution)" if prior == "hausse" else "")] + info, rng)
    if close > rhi and vol_hi:
        return _r("LONG", 9 if prior == "baisse" else 6,
                  ["Wyckoff : Sign of Strength, cassure de la resistance avec volume (phase D/E)"
                   + (" apres accumulation" if prior == "baisse" else "")] + info, rng)
    if close < rlo and vol_hi:
        return _r("SHORT", 9 if prior == "hausse" else 6,
                  ["Wyckoff : Sign of Weakness, cassure du support avec volume (phase D/E)"
                   + (" apres distribution" if prior == "hausse" else "")] + info, rng)
    return _r("NEUTRE", 0, ["Wyckoff : prix dans le range (phase B), attendre Spring, Upthrust ou SOS/SOW"] + info, rng)


def _backup(c, W=50):
    """LPS / test du breakout (phase D-E) : cassure du range avec volume, puis retour sur le niveau
    a faible volume sans le perdre. Symetrique pour le test du breakdown."""
    n = len(c)
    if n < W + 13:
        return None
    seg = c[-(W + 13):-13]
    rhi, rlo = max(x["h"] for x in seg), min(x["l"] for x in seg)
    if (rhi - rlo) / rlo > 0.15:
        return None
    avg_v = sum(x["v"] for x in seg) / len(seg)
    recent = c[-13:]
    for i, x in enumerate(recent[:10]):
        after = recent[i + 1:]
        if x["c"] > rhi and x["v"] >= 1.5 * avg_v and after:
            if (min(a["l"] for a in after) <= rhi * 1.01 and all(a["c"] >= rhi * 0.99 for a in after)
                    and sum(a["v"] for a in after) / len(after) <= 0.7 * x["v"] and recent[-1]["c"] > rhi):
                return _r("LONG", 7, [f"Wyckoff : LPS / test du breakout au niveau {rhi:g} a faible volume (phase D-E)"],
                          {"high": rhi, "low": rlo})
        if x["c"] < rlo and x["v"] >= 1.5 * avg_v and after:
            if (max(a["h"] for a in after) >= rlo * 0.99 and all(a["c"] <= rlo * 1.01 for a in after)
                    and sum(a["v"] for a in after) / len(after) <= 0.7 * x["v"] and recent[-1]["c"] < rlo):
                return _r("SHORT", 7, [f"Wyckoff : test du breakdown au niveau {rlo:g} a faible volume (phase D-E)"],
                          {"high": rhi, "low": rlo})
    return None


def analyze(c, W=50):
    res = _core(c, W)
    if res["direction"] == "NEUTRE":
        b = _backup(c, W)
        if b:
            return b
    return res
