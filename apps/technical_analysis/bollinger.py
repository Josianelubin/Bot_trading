"""Bandes de Bollinger selon les principes de John Bollinger.

Regles appliquees :
1. Bandes = SMA(20) +/- 2 ecarts-types (population). %b et BandWidth calcules.
2. Toucher une bande n'est PAS un signal en soi : il faut une confirmation
   par un indicateur independant (RSI, volume). Sans confirmation, le score est reduit.
3. Squeeze : BandWidth au plus bas (a 5 % pres) des `squeeze_lookback` dernieres periodes.
   Il annonce une forte volatilite a venir mais PAS sa direction -> NEUTRE.
4. "Marcher sur la bande" (walking the bands) : en tendance forte, le prix colle a la
   bande ; c'est une continuation, pas un signal de retournement.
5. Figures W (creux) et M (sommet) : second extreme avec un %b plus favorable que le
   premier (divergence prix / %b) => retournement.
6. Tete-epaules (sommet) et son inverse : trois extremes, le central le plus extreme,
   epaules proches, %b de la 2e epaule plus faible que celui de la tete, cassure de la
   ligne de cou.
7. Bulge : BandWidth au plus haut de la periode => tendance mature, risque d'essoufflement
   (reduit le score des signaux de continuation).
8. Head fake : squeeze, cassure d'une bande, puis retour rapide au-dela de la moyenne
   mediane => fausse cassure, signal inverse.
9. Pullback de tendance : apres avoir marche sur une bande, retour vers la moyenne
   mediane sans la perdre => continuation.
Si des formations se contredisent (LONG et SHORT), le resultat est NEUTRE.
Heuristiques documentees et testees ; ce n'est pas une garantie de resultat.
"""
from math import sqrt

MAX_SCORE = 10  # part de Bollinger dans les 40 points techniques


def compute_bands(closes, period=20, k=2.0):
    """Retourne une liste alignee sur closes (None tant que < period valeurs)."""
    out = []
    for i in range(len(closes)):
        if i + 1 < period:
            out.append(None)
            continue
        w = closes[i + 1 - period: i + 1]
        mid = sum(w) / period
        sd = sqrt(sum((x - mid) ** 2 for x in w) / period)
        upper, lower = mid + k * sd, mid - k * sd
        width = upper - lower
        out.append({
            "middle": mid, "upper": upper, "lower": lower,
            "pct_b": (closes[i] - lower) / width if width > 0 else 0.5,
            "bandwidth": width / mid if mid else 0.0,
        })
    return out


def _w_bottom(pb, closes):
    n = len(pb)
    if n < 30:
        return False
    win = range(n - 30, n)
    first = min((i for i in win if i < n - 6 and pb[i] is not None and pb[i] < 0.05),
                key=lambda i: pb[i], default=None)
    if first is None:
        return False
    later = [i for i in range(first + 3, n) if pb[i] is not None and pb[i] < 0.5]
    if not later:
        return False
    second = min(later, key=lambda i: closes[i])
    return pb[second] > pb[first] and pb[second] >= 0 and pb[n - 1] > pb[second]


def _m_top(pb, closes):
    n = len(pb)
    if n < 30:
        return False
    win = range(n - 30, n)
    first = max((i for i in win if i < n - 6 and pb[i] is not None and pb[i] > 0.95),
                key=lambda i: pb[i], default=None)
    if first is None:
        return False
    later = [i for i in range(first + 3, n) if pb[i] is not None and pb[i] > 0.5]
    if not later:
        return False
    second = max(later, key=lambda i: closes[i])
    return pb[second] < pb[first] and pb[second] <= 1 and pb[n - 1] < pb[second]


def _hs(closes, pb, inverse=False):
    n = len(closes)
    if n < 40:
        return False
    s = [-c for c in closes] if inverse else list(closes)
    p = [None if x is None else (1 - x if inverse else x) for x in pb]
    start = max(3, n - 50)
    sw = [i for i in range(start, n - 3) if s[i] == max(s[i - 3:i + 4])]
    if len(sw) < 3:
        return False
    a, b, c = sw[-3:]
    if not (s[b] > s[a] and s[b] > s[c]):
        return False
    ref = max(abs(s[b]), 1e-12)
    if abs(s[a] - s[c]) / ref > 0.03 or (s[b] - max(s[a], s[c])) < 0.01 * ref:
        return False
    if p[b] is None or p[c] is None or not p[c] < p[b]:
        return False
    neck = min(min(s[a:b + 1]), min(s[b:c + 1]))
    return s[-1] < neck


def _squeeze_at(bands, idx, lookback):
    ws = [b["bandwidth"] for b in bands[max(0, idx + 1 - lookback):idx + 1] if b]
    cur = bands[idx]
    return bool(cur) and len(ws) >= 20 and cur["bandwidth"] <= min(ws) * 1.05


def _head_fake(bands, pb, closes, lookback):
    n = len(closes)
    for t in range(n - 15, n - 3):
        if t < 0 or not _squeeze_at(bands, t, lookback):
            continue
        for b in range(t + 1, n - 1):
            if pb[b] is None:
                continue
            if pb[b] > 1 and closes[-1] < bands[-1]["middle"]:
                return "SHORT"
            if pb[b] < 0 and closes[-1] > bands[-1]["middle"]:
                return "LONG"
    return None


def _pullback(pb, closes, last):
    n = len(pb)
    prior = [p for p in pb[max(0, n - 12):n - 3] if p is not None]
    if len(prior) < 5:
        return None
    if max(prior) > 0.95 and sum(p > 0.8 for p in prior) >= 3 and 0.4 <= pb[-1] <= 0.7 \
            and closes[-1] > last["middle"]:
        return "LONG"
    if min(prior) < 0.05 and sum(p < 0.2 for p in prior) >= 3 and 0.3 <= pb[-1] <= 0.6 \
            and closes[-1] < last["middle"]:
        return "SHORT"
    return None


def analyze(closes, rsi=None, squeeze_lookback=120):
    """Retourne {direction, score (0..10), reasons, patterns, last}.

    rsi : valeur RSI(14) la plus recente (confirmation independante), optionnelle.
    """
    bands = compute_bands(closes)
    valid = [b for b in bands if b]
    if len(valid) < 5:
        return {"direction": "NEUTRE", "score": 0, "last": None, "patterns": [],
                "reasons": ["DONNEES INDISPONIBLES : historique insuffisant pour Bollinger"]}
    last = valid[-1]
    pb = [b["pct_b"] if b else None for b in bands]
    widths = [b["bandwidth"] for b in valid[-squeeze_lookback:]]
    squeeze = _squeeze_at(bands, len(bands) - 1, squeeze_lookback)
    bulge = len(widths) >= 20 and last["bandwidth"] >= max(widths) * 0.95
    recent = [p for p in pb[-5:] if p is not None]
    walking_up = len(recent) >= 5 and all(p > 0.8 for p in recent[-3:]) and sum(p >= 0.95 for p in recent) >= 2
    walking_dn = len(recent) >= 5 and all(p < 0.2 for p in recent[-3:]) and sum(p <= 0.05 for p in recent) >= 2

    found = []  # (nom, direction, score_base, texte, continuation?)
    fake = _head_fake(bands, pb, closes, squeeze_lookback)
    if fake == "SHORT":
        found.append(("head_fake", "SHORT", 7, "Head fake : cassure haussiere apres squeeze puis retour sous la moyenne (fausse cassure)", False))
    elif fake == "LONG":
        found.append(("head_fake", "LONG", 7, "Head fake : cassure baissiere apres squeeze puis retour au-dessus de la moyenne (fausse cassure)", False))
    if _w_bottom(pb, closes):
        found.append(("w_bottom", "LONG", 8, "Figure W : second creux avec %b plus eleve que le premier (retournement haussier)", False))
    if _m_top(pb, closes):
        found.append(("m_top", "SHORT", 8, "Figure M : second sommet avec %b plus bas que le premier (retournement baissier)", False))
    if _hs(closes, pb):
        found.append(("head_shoulders", "SHORT", 7, "Tete-epaules : cassure de la ligne de cou, 2e epaule avec %b plus faible", False))
    if _hs(closes, pb, inverse=True):
        found.append(("inverse_head_shoulders", "LONG", 7, "Tete-epaules inverse : cassure de la ligne de cou, 2e epaule avec %b plus favorable", False))
    pull = _pullback(pb, closes, last)
    if pull:
        found.append(("trend_pullback", pull, 5, "Pullback de tendance vers la moyenne mediane apres avoir marche sur la bande (continuation)", True))
    if walking_up:
        found.append(("walking_upper", "LONG", 6, "Prix colle a la bande haute : tendance haussiere forte (continuation, pas un signal de vente)", True))
    if walking_dn:
        found.append(("walking_lower", "SHORT", 6, "Prix colle a la bande basse : tendance baissiere forte (continuation, pas un signal d'achat)", True))

    patterns = [f[0] for f in found]
    if squeeze:
        patterns.append("squeeze")
    if bulge:
        patterns.append("bulge")
    reasons = []
    if squeeze:
        reasons.append("Squeeze : volatilite au plus bas, cassure probable mais direction inconnue -> attendre")
        return {"direction": "NEUTRE", "score": 0, "reasons": reasons, "patterns": patterns, "last": last}

    dirs = {f[1] for f in found}
    if not found:
        reasons.append(f"Pas de formation Bollinger (%b = {last['pct_b']:.2f}) : un contact de bande seul ne suffit pas")
        if bulge:
            reasons.append("Bulge : volatilite au plus haut, tendance mature, risque d'essoufflement")
        return {"direction": "NEUTRE", "score": 0, "reasons": reasons, "patterns": patterns, "last": last}
    if len(dirs) > 1:
        reasons = [f[3] for f in found] + ["Formations contradictoires (LONG et SHORT) : aucun signal"]
        return {"direction": "NEUTRE", "score": 0, "reasons": reasons, "patterns": patterns, "last": last}

    direction = dirs.pop()
    best = max(found, key=lambda f: f[2])
    base = best[2]
    reasons = [f[3] for f in sorted(found, key=lambda f: -f[2])]
    if bulge:
        reasons.append("Bulge : volatilite au plus haut, tendance mature, risque d'essoufflement")
        if best[4]:
            base //= 2
            reasons.append("Score de continuation reduit a cause du bulge")
    score = base
    if rsi is None:
        score = base // 2
        reasons.append("Non confirme : aucun indicateur independant (RSI/volume) fourni, score reduit")
    else:
        confirmed = (direction == "LONG" and rsi >= 50) or (direction == "SHORT" and rsi <= 50)
        if confirmed:
            score = min(MAX_SCORE, base + 2)
            reasons.append(f"Confirme par RSI {rsi:.0f}")
        else:
            score = base // 2
            reasons.append(f"Contredit par RSI {rsi:.0f}, score reduit")
    return {"direction": direction, "score": score, "reasons": reasons, "patterns": patterns, "last": last}
