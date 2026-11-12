"""Vagues d'Elliott (R. N. Elliott) validees par les regles STRICTES uniquement :
- la vague 2 ne retrace jamais plus de 100 % de la vague 1 ;
- la vague 3 n'est jamais la plus courte des vagues 1, 3 et 5 ;
- la vague 4 ne chevauche pas le territoire de la vague 1.
Le comptage reste subjectif : le bot ne signale qu'un comptage qui respecte ces regles."""
from . import indicators as ind
from .strategies import swings

MAX_SCORE = 6


def pivots(c, w=3):
    pts = [(i, "H", c[i]["h"]) for i in swings([x["h"] for x in c], "high", w)]
    pts += [(i, "L", c[i]["l"]) for i in swings([x["l"] for x in c], "low", w)]
    pts.sort(key=lambda p: (p[0], p[1]))
    out = []
    for p in pts:
        if out and out[-1][1] == p[1]:
            if (p[1] == "H" and p[2] > out[-1][2]) or (p[1] == "L" and p[2] < out[-1][2]):
                out[-1] = p
        else:
            out.append(p)
    return out


def _w5(q, cur, prev):
    w1, w3 = q[1] - q[0], q[3] - q[2]
    if q[2] > q[0] and q[4] > q[1] and w3 > w1 and q[4] < cur < q[3] and cur > prev:
        return {"wave": 5, "target": q[4] + w1, "invalid": q[4], "pts": 4}


def _w3(q, cur, prev):
    if q[1] <= q[0] or q[2] <= q[0]:
        return None
    retr = (q[1] - q[2]) / (q[1] - q[0])
    if 0.382 <= retr <= 0.786 and q[2] < cur <= q[1] and cur > prev:
        return {"wave": 3, "target": q[2] + 1.618 * (q[1] - q[0]), "invalid": q[0], "pts": 6}


def analyze(c):
    res = {"name": "elliott", "direction": "NEUTRE", "score": 0, "max": MAX_SCORE, "reasons": []}
    if len(c) < 40:
        res["reasons"] = ["DONNEES INDISPONIBLES : historique insuffisant (Elliott)"]
        return res
    pv = pivots(c)
    a = ind.atr(c, 14)[-1] or 0
    cur, prev = c[-1]["c"], c[-2]["c"]
    for direction, sign, first in (("LONG", 1, "L"), ("SHORT", -1, "H")):
        for k, fn in ((5, _w5), (3, _w3)):
            if len(pv) < k or pv[-k][1] != first:
                continue
            seg = pv[-k:]
            q = [sign * p[2] for p in seg]
            if any(abs(q[i + 1] - q[i]) < a for i in range(k - 1)):
                continue
            r = fn(q, sign * cur, sign * prev)
            if r:
                res.update(direction=direction, score=r["pts"])
                res["target"], res["invalidation"] = sign * r["target"], sign * r["invalid"]
                res["reasons"] = [
                    f"Elliott : comptage valide, debut/poursuite de la vague {r['wave']} "
                    f"{'haussiere' if direction == 'LONG' else 'baissiere'} (regles strictes respectees)",
                    f"Objectif indicatif {res['target']:g} ; invalidation {res['invalidation']:g}",
                    "Comptage subjectif : a confirmer par les autres outils"]
                return res
    res["reasons"] = ["Elliott : aucun comptage valide selon les regles strictes"]
    return res
