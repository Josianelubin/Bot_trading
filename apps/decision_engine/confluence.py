"""Moteur de CONFLUENCE : technique 40 + fondamental 35 + sentiment 25 = 100.
80-100 signal fort ; 65-79 modere ; 50-64 surveillance ; < 50 aucun trade.
Les BLOCAGES sont prioritaires : le score ne les annule jamais. Les contradictions plafonnent ou annulent le signal."""

LEVELS = ((80, "fort"), (65, "modere"), (50, "surveillance"))


def classify(score):
    for lo, name in LEVELS:
        if score >= lo:
            return name
    return "aucun"


def _signed(part, direction):
    if not part or part.get("score") is None:
        return None
    return part["bias"] if direction == "LONG" else -part["bias"]


def confluence(direction, tech_score, fund=None, sent=None, blocks=()):
    blocking = list(blocks)
    for part in (fund, sent):
        if part and part.get("block"):
            blocking.append(part["block"])
    has_f = bool(fund) and fund.get("score") is not None
    has_s = bool(sent) and sent.get("score") is not None
    total = tech_score + (fund["score"] if has_f else 0) + (sent["score"] if has_s else 0)
    avail = 40 + (35 if has_f else 0) + (25 if has_s else 0)
    score = round(100 * total / avail)
    missing = [n for n, ok in (("fondamental", has_f), ("sentiment", has_s)) if not ok]
    contras = []
    for name, part in (("fondamental", fund), ("sentiment", sent)):
        sg = _signed(part, direction)
        if sg is not None and sg < -0.4:
            contras.append(f"{name} contraire a la direction {direction}")
    reasons = []
    if len(contras) >= 2:
        score = 0
        reasons.append("Contradictions multiples : aucun trade")
    elif contras:
        score = min(score, 64)
        reasons.append("Une contradiction : signal plafonne a la surveillance")
    cls = "aucun" if blocking else classify(score)
    return {"score": score, "class": cls, "blocked": bool(blocking), "blocks": blocking, "partial": bool(missing),
            "missing": missing, "contradictions": contras, "reasons": reasons, "max_available": avail,
            "parts": {"technique": [tech_score, 40], "fondamental": [fund["score"] if has_f else None, 35],
                      "sentiment": [sent["score"] if has_s else None, 25]}}
