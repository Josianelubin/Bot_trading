"""Selection des contrats USDT Futures les plus interessants.

Criteres (Phase 3, version initiale) : volume 24h, variation de prix, funding rate.
Exclusions : contrats en delisting, volume sous le minimum, donnees manquantes.
Le spread et l'Open Interest seront ajoutes avec les donnees du carnet d'ordres.
"""


def _f(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def select_top(contracts, tickers, n=20, min_quote_volume=5_000_000):
    delisting = {c.get("name") for c in contracts if c.get("in_delisting")}
    known = {c.get("name") for c in contracts}
    rows = []
    for t in tickers:
        name = t.get("contract")
        if not name or name not in known or name in delisting:
            continue
        if not name.endswith("_USDT"):
            continue
        volume = _f(t.get("volume_24h_quote"))
        if volume is None:
            volume = _f(t.get("volume_24h_settle"))
        change = _f(t.get("change_percentage"))
        last = _f(t.get("last"))
        if volume is None or change is None or last is None or last <= 0:
            continue  # donnees manquantes : on exclut, on n'invente pas
        if volume < min_quote_volume:
            continue
        funding = _f(t.get("funding_rate")) or 0.0
        rows.append({"contract": name, "last": last, "change_pct": change,
                     "quote_volume": volume, "funding_rate": funding})
    if not rows:
        return []
    max_vol = max(r["quote_volume"] for r in rows)
    max_chg = max(abs(r["change_pct"]) for r in rows) or 1.0
    for r in rows:
        r["score"] = round(
            100 * (0.6 * r["quote_volume"] / max_vol
                   + 0.3 * abs(r["change_pct"]) / max_chg
                   + 0.1 * min(abs(r["funding_rate"]) * 1000, 1.0)), 2)
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:n]
