"""Strategies de trading, implementees a partir de leurs REGLES publiques et documentees.
Chaque fonction retourne {name, direction (LONG/SHORT/NEUTRE), score, max, reasons}.
Aucune ne garantit un resultat : le score mesure la conformite aux regles, pas une probabilite."""
from . import indicators as ind


def _res(name, direction, score, mx, reasons):
    return {"name": name, "direction": direction, "score": score if direction != "NEUTRE" else 0,
            "max": mx, "reasons": reasons}


def swings(values, kind, w=3):
    fn = max if kind == "high" else min
    return [i for i in range(w, len(values) - w) if values[i] == fn(values[i - w:i + w + 1])]


# --- Richard Dennis / Turtle Trading : cassure Donchian + stop 2N ---
def turtle(c, entry_len=20, long_len=55):
    mx = 10
    if len(c) < long_len + 2:
        return _res("turtle", "NEUTRE", 0, mx, ["DONNEES INDISPONIBLES : historique insuffisant (Turtle)"])
    n = ind.atr(c, 20)[-1]
    close = c[-1]["c"]
    for length, pts in ((long_len, 10), (entry_len, 7)):
        prev = c[-length - 1:-1]
        hi, lo = max(x["h"] for x in prev), min(x["l"] for x in prev)
        if close > hi:
            return _res("turtle", "LONG", pts, mx, [f"Turtle : cassure du plus haut {length} bougies ({hi:g}) ; stop initial 2N = {close - 2 * n:g}"])
        if close < lo:
            return _res("turtle", "SHORT", pts, mx, [f"Turtle : cassure du plus bas {length} bougies ({lo:g}) ; stop initial 2N = {close + 2 * n:g}"])
    return _res("turtle", "NEUTRE", 0, mx, ["Turtle : pas de cassure Donchian"])


# --- Charles Dow : tendance primaire (HH+HL / LH+LL) confirmee par le volume ---
def dow(c):
    mx = 8
    hs = swings([x["h"] for x in c], "high")
    ls = swings([x["l"] for x in c], "low")
    if len(hs) < 2 or len(ls) < 2:
        return _res("dow", "NEUTRE", 0, mx, ["Dow : pas assez de points pivots"])
    h1, h2 = c[hs[-2]]["h"], c[hs[-1]]["h"]
    l1, l2 = c[ls[-2]]["l"], c[ls[-1]]["l"]
    last = c[-20:]
    up_v = sum(x["v"] for x in last if x["c"] > x["o"])
    dn_v = sum(x["v"] for x in last if x["c"] < x["o"])
    if h2 > h1 and l2 > l1:
        ok = up_v > dn_v
        return _res("dow", "LONG", 8 if ok else 5, mx, ["Dow : sommets et creux de plus en plus hauts (tendance haussiere)",
                    "Volume confirme la tendance" if ok else "Volume ne confirme pas la tendance (score reduit)"])
    if h2 < h1 and l2 < l1:
        ok = dn_v > up_v
        return _res("dow", "SHORT", 8 if ok else 5, mx, ["Dow : sommets et creux de plus en plus bas (tendance baissiere)",
                    "Volume confirme la tendance" if ok else "Volume ne confirme pas la tendance (score reduit)"])
    return _res("dow", "NEUTRE", 0, mx, ["Dow : tendance non confirmee (sommets/creux mixtes)"])


# --- Jesse Livermore : point pivot (cassure apres consolidation, avec volume) ---
def livermore(c, look=20):
    mx = 7
    if len(c) < look + 4:
        return _res("livermore", "NEUTRE", 0, mx, ["DONNEES INDISPONIBLES : historique insuffisant (Livermore)"])
    base = c[-(look + 3):-3]
    res_, sup = max(x["h"] for x in base), min(x["l"] for x in base)
    if (res_ - sup) / res_ > 0.10:
        return _res("livermore", "NEUTRE", 0, mx, ["Livermore : pas de consolidation serree (>10 %), pas de point pivot"])
    avg_v = sum(x["v"] for x in base) / len(base)
    vol_ok = max(x["v"] for x in c[-3:]) >= 1.5 * avg_v
    close = c[-1]["c"]
    if close > res_:
        return _res("livermore", "LONG", 7 if vol_ok else 3, mx, [f"Livermore : cassure du point pivot {res_:g} (ligne de moindre resistance haussiere)",
                    "Volume fort sur la cassure" if vol_ok else "Cassure sans volume : suspecte (score reduit)"])
    if close < sup:
        return _res("livermore", "SHORT", 7 if vol_ok else 3, mx, [f"Livermore : cassure du support pivot {sup:g} (ligne de moindre resistance baissiere)",
                    "Volume fort sur la cassure" if vol_ok else "Cassure sans volume : suspecte (score reduit)"])
    return _res("livermore", "NEUTRE", 0, mx, ["Livermore : prix dans la consolidation, attendre le point pivot"])


# --- Linda Raschke : Holy Grail (ADX + pullback sur EMA20) ---
def raschke_holy_grail(c):
    mx = 8
    if len(c) < 40:
        return _res("raschke_holy_grail", "NEUTRE", 0, mx, ["DONNEES INDISPONIBLES : historique insuffisant (Raschke)"])
    a = ind.adx(c)
    e20 = ind.ema([x["c"] for x in c], 20)
    if a["adx"][-1] is None or a["adx"][-3] is None:
        return _res("raschke_holy_grail", "NEUTRE", 0, mx, ["DONNEES INDISPONIBLES : ADX non calculable"])
    strong = a["adx"][-1] > 30 and a["adx"][-1] > a["adx"][-3]
    if not strong:
        return _res("raschke_holy_grail", "NEUTRE", 0, mx, [f"Holy Grail : ADX {a['adx'][-1]:.0f} (il faut > 30 et en hausse)"])
    touched_dn = any(x["l"] <= e20[-k] * 1.002 for k, x in ((1, c[-1]), (2, c[-2]), (3, c[-3])))
    touched_up = any(x["h"] >= e20[-k] * 0.998 for k, x in ((1, c[-1]), (2, c[-2]), (3, c[-3])))
    if a["plus_di"][-1] > a["minus_di"][-1] and touched_dn and c[-1]["c"] > e20[-1]:
        return _res("raschke_holy_grail", "LONG", 8, mx, [f"Holy Grail : ADX {a['adx'][-1]:.0f}, repli sur EMA20 puis reprise haussiere"])
    if a["minus_di"][-1] > a["plus_di"][-1] and touched_up and c[-1]["c"] < e20[-1]:
        return _res("raschke_holy_grail", "SHORT", 8, mx, [f"Holy Grail : ADX {a['adx'][-1]:.0f}, rebond sur EMA20 puis reprise baissiere"])
    return _res("raschke_holy_grail", "NEUTRE", 0, mx, ["Holy Grail : tendance forte mais pas de repli sur EMA20"])


# --- Linda Raschke : momentum 3-10 ---
def raschke_momentum(c):
    mx = 5
    closes = [x["c"] for x in c]
    if len(closes) < 30:
        return _res("raschke_momentum", "NEUTRE", 0, mx, ["DONNEES INDISPONIBLES : historique insuffisant (momentum 3-10)"])
    s3, s10 = ind.sma(closes, 3), ind.sma(closes, 10)
    osc = [None if a is None or b is None else a - b for a, b in zip(s3, s10)]
    vals = [o for o in osc if o is not None]
    sig = ind.sma(vals, 16)
    if sig[-1] is None or sig[-2] is None:
        return _res("raschke_momentum", "NEUTRE", 0, mx, ["DONNEES INDISPONIBLES : ligne de signal"])
    o1, o0, s1, s0 = vals[-2], vals[-1], sig[-2], sig[-1]
    if o0 > s0 and o1 <= s1:
        return _res("raschke_momentum", "LONG", 5, mx, ["Momentum 3-10 : croisement haussier de la ligne de signal"])
    if o0 < s0 and o1 >= s1:
        return _res("raschke_momentum", "SHORT", 5, mx, ["Momentum 3-10 : croisement baissier de la ligne de signal"])
    if o0 > s0 and o0 > 0:
        return _res("raschke_momentum", "LONG", 3, mx, ["Momentum 3-10 : momentum haussier etabli"])
    if o0 < s0 and o0 < 0:
        return _res("raschke_momentum", "SHORT", 3, mx, ["Momentum 3-10 : momentum baissier etabli"])
    return _res("raschke_momentum", "NEUTRE", 0, mx, ["Momentum 3-10 : pas de signal"])


# --- J. Welles Wilder : ADX (force de tendance) + RSI (surachat/survente) ---
def wilder(c):
    mx = 7
    if len(c) < 40:
        return _res("wilder", "NEUTRE", 0, mx, ["DONNEES INDISPONIBLES : historique insuffisant (Wilder)"])
    a = ind.adx(c)
    r = ind.rsi([x["c"] for x in c])[-1]
    ad, p, m = a["adx"][-1], a["plus_di"][-1], a["minus_di"][-1]
    if ad is None or r is None:
        return _res("wilder", "NEUTRE", 0, mx, ["DONNEES INDISPONIBLES : ADX/RSI"])
    if ad < 20:
        return _res("wilder", "NEUTRE", 0, mx, [f"Wilder : ADX {ad:.0f} < 20, marche sans tendance, ne pas suivre la tendance"])
    if p > m:
        ok = r < 70
        return _res("wilder", "LONG", 7 if ok else 3, mx, [f"Wilder : ADX {ad:.0f}, +DI > -DI (tendance haussiere)",
                    f"RSI {r:.0f}" + ("" if ok else " : surachat, score reduit")])
    ok = r > 30
    return _res("wilder", "SHORT", 7 if ok else 3, mx, [f"Wilder : ADX {ad:.0f}, -DI > +DI (tendance baissiere)",
                f"RSI {r:.0f}" + ("" if ok else " : survente, score reduit")])
