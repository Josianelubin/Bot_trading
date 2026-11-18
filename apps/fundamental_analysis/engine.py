"""Analyse fondamentale (35 points) a partir des actualites verifiables (aucune donnee inventee).
news=None signifie SOURCES INDISPONIBLES ; news=[] signifie aucune actualite recente."""
from datetime import datetime, timezone

MAX_SCORE = 35
REL = {"haute": 1.0, "moyenne": 0.6, "faible": 0.3}
IMP = {1: 1.0, 2: 1.5, 3: 2.0}


def _age_h(it, now):
    return (now - it["published_at"]).total_seconds() / 3600


def assess(news, direction, now=None, require=True):
    now = now or datetime.now(timezone.utc)
    if news is None:
        return {"available": False, "score": None, "bias": 0.0, "items": [], "block":
                "DONNEES INDISPONIBLES : actualites introuvables (blocage applique)" if require else None,
                "reasons": ["DONNEES INDISPONIBLES : actualites introuvables"]}
    if not news:
        return {"available": True, "score": 0, "bias": 0.0, "items": [], "block": None,
                "reasons": ["Fondamental : aucune actualite recente (48 h) pour cet actif"]}
    num = den = 0.0
    for it in news:
        a = _age_h(it, now)
        w = REL[it["reliability"]] * IMP[it["importance"]] * (1.0 if a < 12 else 0.7 if a < 24 else 0.4)
        sign = {"positif": 1, "negatif": -1}.get(it["sentiment"], 0)
        num, den = num + sign * w, den + w
    bias = num / den if den else 0.0
    signed = bias if direction == "LONG" else -bias if direction == "SHORT" else 0.0
    score = round(MAX_SCORE * max(0.0, signed) * min(1.0, len(news) / 3)) if direction else None
    pos = sum(1 for i in news if i["sentiment"] == "positif")
    neg = sum(1 for i in news if i["sentiment"] == "negatif")
    reasons = [f"Fondamental : {len(news)} actualite(s) ({pos} positive(s), {neg} negative(s)), biais {bias:+.2f}"]
    block = None
    if direction:
        opposite = "negatif" if direction == "LONG" else "positif"
        for it in news:
            if (_age_h(it, now) < 12 and it["importance"] == 3 and it["sentiment"] == opposite
                    and it["reliability"] != "faible"):
                block = f"Actualite majeure defavorable : {it['title'][:120]} ({it['source']})"
                break
    if signed < -0.3:
        reasons.append("Actualites globalement CONTRAIRES a la direction technique")
    return {"available": True, "score": score, "bias": round(bias, 2), "items": news, "block": block, "reasons": reasons}
