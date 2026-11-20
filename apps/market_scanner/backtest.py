"""Backtest de la strategie du scanner sur des bougies HISTORIQUES REELLES (aucune donnee inventee).
Regles prudentes : a chaque pas, on lance le scanner sur les bougies cloturees ; un signal est un ordre LIMITE
a l'entree (rempli seulement si le prix la touche dans les `max_wait` bougies, annule si le SL est touche avant) ;
si SL et TP sont touches dans la meme bougie, le SL est compte en premier. Frais, funding et slippage NON inclus."""
from .scan import scan

TF_SEC = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400, "8h": 28800, "1d": 86400, "1w": 604800}


def _resolve(candles, j, d, sl, tps, max_hold):
    """Retourne (premier TP atteint 0..3 ou -1 si SL d'abord, bougie de sortie)."""
    reached, alive = 0, True
    last = j
    for k in range(j, min(len(candles), j + max_hold)):
        c = candles[k]
        hit_sl = c["l"] <= sl if d == "LONG" else c["h"] >= sl
        if hit_sl:
            return (reached if reached else -1), k
        while reached < 3 and (c["h"] >= tps[reached] if d == "LONG" else c["l"] <= tps[reached]):
            reached += 1
        last = k
        if reached == 3:
            break
    return (reached if reached else 0), last  # 0 = ni SL ni TP dans le delai (non concluant)


def run(candles, symbol, tf, cfg=None, htf=None, warmup=120, step=2, max_wait=12, max_hold=80):
    from apps.smart_money import ict  # noqa: F401  (import tardif : evite les cycles)
    n, i = len(candles), warmup
    htf_sec, tf_sec = TF_SEC.get(htf["tf"]) if htf else None, TF_SEC[tf]
    trades, unfilled = [], 0
    while i < n - 2:
        closed = candles[:i + 1]
        hc = None
        if htf and htf_sec and "t" in candles[i]:
            limit = candles[i]["t"] + tf_sec
            hc = [h for h in htf["candles"] if h["t"] + htf_sec <= limit]
        r = scan(closed, symbol, tf, cfg, htf_closed=hc)
        if r.get("status") not in ("signal", "signal_limite"):
            i += step
            continue
        d, entry, sl, tps = r["direction"], r["entry"], r["stop_loss"], r["take_profits"]
        fill = None
        for j in range(i + 1, min(n, i + 1 + max_wait)):
            c = candles[j]
            if (c["l"] <= sl) if d == "LONG" else (c["h"] >= sl):
                break  # invalide avant remplissage
            if (c["l"] <= entry) if d == "LONG" else (c["h"] >= entry):
                fill = j
                break
        if fill is None:
            unfilled += 1
            i += step
            continue
        reached, end = _resolve(candles, fill, d, sl, tps, max_hold)
        risk = abs(entry - sl)
        rr = [abs(t - entry) / risk for t in tps]
        trades.append({"index": i, "direction": d, "reached": reached, "rr": rr})
        i = max(end + 1, i + step)
    concl = [t for t in trades if t["reached"] != 0]
    wins1 = sum(1 for t in concl if t["reached"] >= 1)
    wins2 = sum(1 for t in concl if t["reached"] >= 2)
    m = len(concl)

    def avg(level):
        return (sum((t["rr"][level - 1] if t["reached"] >= level else -1.0) for t in concl) / m) if m else None

    return {"symbol": symbol, "timeframe": tf, "candles": n, "from": candles[0].get("t"), "to": candles[-1].get("t"),
            "signals": len(trades) + unfilled, "unfilled": unfilled, "trades": m,
            "wins_tp1": wins1, "losses": m - wins1, "wins_tp2": wins2,
            "rate_tp1": round(100 * wins1 / m, 1) if m else None, "fail_rate": round(100 * (m - wins1) / m, 1) if m else None,
            "rate_tp2": round(100 * wins2 / m, 1) if m else None,
            "avg_r_tp1": round(avg(1), 2) if m else None, "avg_r_tp2": round(avg(2), 2) if m else None,
            "reliable": m >= 30,
            "warning": "Echantillon insuffisant (moins de 30 trades) : resultat peu fiable." if m < 30 else
                       "Hors frais, funding et slippage. Les performances passees ne garantissent pas les performances futures."}
