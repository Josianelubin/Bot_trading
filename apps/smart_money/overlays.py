"""Donnees Smart Money a DESSINER sur le graphique (a partir des vraies bougies) :
etiquettes de structure HH/HL/LH/LL, CHoCH / BOS / MSS, liquidite (Buy-Side / Sell-Side, Equal Highs / Lows),
balayages de liquidite (sweeps), bougies de deplacement, FVG et Order Blocks encore valides.
Les bougies doivent contenir le temps 't'."""
import bisect

from apps.smart_money import ict
from apps.technical_analysis import indicators as ind
from apps.technical_analysis.strategies import swings

EMPTY = {"labels": [], "events": [], "liquidity": [], "sweeps": [], "displacement": [], "fvg": [], "ob": [],
         "range24": None, "prev_day": None}


def compute_levels(h1):
    """Extremes des 24 dernieres heures et du jour UTC precedent, calcules sur des bougies 1H REELLES.
    Valable pour n'importe quel timeframe affiche (1m comme 1W) et n'importe quelle paire."""
    if not h1 or "t" not in h1[0] or len(h1) < 24:
        return None
    now = h1[-1]["t"] + 3600
    win = [x for x in h1 if x["t"] >= now - 86400]
    if len(win) < 20:
        return None
    hi, lo = max(win, key=lambda x: x["h"]), min(win, key=lambda x: x["l"])
    out = {"r24": {"high": {"price": hi["h"], "time": hi["t"]}, "low": {"price": lo["l"], "time": lo["t"]}}, "pd": None}
    day = h1[-1]["t"] // 86400 - 1
    prev = [x for x in h1 if x["t"] // 86400 == day]
    if len(prev) >= 22:
        phi, plo = max(prev, key=lambda x: x["h"]), min(prev, key=lambda x: x["l"])
        out["pd"] = {"high": {"price": phi["h"], "time": phi["t"]}, "low": {"price": plo["l"], "time": plo["t"]}}
    return out


def _snap(t, times):
    """Ouverture de la bougie DU GRAPHIQUE qui contient t (avant la 1re bougie : la 1re)."""
    return times[max(bisect.bisect_right(times, t) - 1, 0)]


def extremes(c, tf_sec, atr_val, levels=None):
    """Plus haut / plus bas des 24 dernieres heures et du JOUR UTC PRECEDENT (PDH / PDL) : la liquidite
    des extremes, comme les etiquettes de prix haut/bas du graphique Gate."""
    if levels and "t" in c[0]:
        times = [x["t"] for x in c]

        def conv(d):
            return {"high": {"price": d["high"]["price"], "time": _snap(d["high"]["time"], times)},
                    "low": {"price": d["low"]["price"], "time": _snap(d["low"]["time"], times)}}
        r24 = {**conv(levels["r24"]), "atr": atr_val}
        return r24, (conv(levels["pd"]) if levels.get("pd") else None)
    if not tf_sec or tf_sec >= 86400 or "t" not in c[0]:
        return None, None
    last_t = c[-1]["t"]
    win = [x for x in c if x["t"] >= last_t - 86400 + tf_sec]
    r24 = None
    if len(win) >= 0.9 * (86400 / tf_sec):
        hi = max(win, key=lambda x: x["h"])
        lo = min(win, key=lambda x: x["l"])
        r24 = {"high": {"price": hi["h"], "time": hi["t"]}, "low": {"price": lo["l"], "time": lo["t"]}, "atr": atr_val}
    day = last_t // 86400 - 1
    prev = [x for x in c if x["t"] // 86400 == day]
    pd = None
    if len(prev) >= 0.9 * (86400 / tf_sec):
        hi = max(prev, key=lambda x: x["h"])
        lo = min(prev, key=lambda x: x["l"])
        pd = {"high": {"price": hi["h"], "time": hi["t"]}, "low": {"price": lo["l"], "time": lo["t"]}}
    return r24, pd


def build(c, w=3, max_levels=3, tol=0.001, tf_sec=None, levels=None):
    n = len(c)
    if n < 30 or "t" not in c[0]:
        return dict(EMPTY)
    atr_val = ind.atr(c, 14)[-1] or 0.0
    hs = swings([x["h"] for x in c], "high", w)
    ls = swings([x["l"] for x in c], "low", w)
    pts = sorted([(i, "H", c[i]["h"]) for i in hs] + [(i, "L", c[i]["l"]) for i in ls])

    labels, last_h, last_l = [], None, None
    for i, k, p in pts:
        if k == "H":
            if last_h is not None:
                labels.append({"time": c[i]["t"], "price": p, "label": "HH" if p > last_h else "LH", "pos": "above"})
            last_h = p
        else:
            if last_l is not None:
                labels.append({"time": c[i]["t"], "price": p, "label": "HL" if p > last_l else "LL", "pos": "below"})
            last_l = p

    # cassures de structure, dans l'ordre chronologique (un swing n'est connu que w bougies apres)
    known = {}
    for i, k, p in pts:
        known.setdefault(i + w, []).append((i, k, p))
    events, trend, cur_h, cur_l = [], None, None, None
    for i in range(n):
        for si, k, p in known.get(i, []):
            if k == "H":
                cur_h = [si, p, False]
            else:
                cur_l = [si, p, False]
        close = c[i]["c"]
        if cur_h and not cur_h[2] and close > cur_h[1]:
            typ = "BOS" if trend == "UP" else "CHoCH" if trend == "DOWN" else "MSS"
            events.append({"type": typ, "dir": "LONG", "level": cur_h[1], "from": c[cur_h[0]]["t"], "to": c[i]["t"]})
            trend, cur_h[2] = "UP", True
        if cur_l and not cur_l[2] and close < cur_l[1]:
            typ = "BOS" if trend == "DOWN" else "CHoCH" if trend == "UP" else "MSS"
            events.append({"type": typ, "dir": "SHORT", "level": cur_l[1], "from": c[cur_l[0]]["t"], "to": c[i]["t"]})
            trend, cur_l[2] = "DOWN", True

    # liquidite : sommets / creux pas encore pris (stops au-dela), et balayages recents (meche puis retour)
    last = c[-1]["c"]
    active, sweeps = [], []
    for i, k, p in pts:
        j = next((j for j in range(i + 1, n) if (c[j]["h"] > p if k == "H" else c[j]["l"] < p)), None)
        if j is None:
            active.append({"side": "BSL" if k == "H" else "SSL", "price": p, "time": c[i]["t"]})
        elif j >= n - 40 and (c[j]["c"] < p if k == "H" else c[j]["c"] > p):
            sweeps.append({"side": "BSL" if k == "H" else "SSL", "price": p, "time": c[j]["t"]})
    for lv in active:
        lv["equal"] = sum(1 for o in active if o["side"] == lv["side"] and abs(o["price"] - lv["price"]) / lv["price"] <= tol) >= 2
    above = sorted([l for l in active if l["side"] == "BSL" and l["price"] > last], key=lambda l: l["price"])[:max_levels]
    below = sorted([l for l in active if l["side"] == "SSL" and l["price"] < last], key=lambda l: -l["price"])[:max_levels]

    disp = []
    for i in range(max(0, n - 60), n):
        x = c[i]
        body, rng = abs(x["c"] - x["o"]), x["h"] - x["l"]
        if atr_val and rng > 0 and body >= 1.5 * atr_val and body / rng >= 0.6:
            disp.append({"time": x["t"], "dir": "LONG" if x["c"] > x["o"] else "SHORT"})

    fvg = [{"time": c[max(g["index"] - 1, 0)]["t"], "lo": g["lo"], "hi": g["hi"], "type": g["type"]}
           for g in ict.fvgs(c, atr_val) if g["status"] in ("ouvert", "partiel")] if atr_val else []
    ob = [{"time": c[o["index"]]["t"], "lo": o["lo"], "hi": o["hi"], "type": o["type"]}
          for o in ict.order_blocks(c, atr_val) if o["valid"]] if atr_val else []
    r24, prev_day = extremes(c, tf_sec, atr_val, levels)
    return {"labels": labels[-14:], "events": events[-6:], "liquidity": above + below, "sweeps": sweeps[-4:],
            "displacement": disp[-8:], "fvg": fvg[-6:], "ob": ob[-4:], "range24": r24, "prev_day": prev_day}
