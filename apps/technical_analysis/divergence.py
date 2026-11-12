"""Divergences RSI (J. Welles Wilder) : le prix fait un nouvel extreme mais pas le RSI.
- Haussiere : creux de prix plus bas, creux de RSI plus haut (RSI < 45 au 1er creux).
- Baissiere : sommet de prix plus haut, sommet de RSI plus bas (RSI > 55 au 1er sommet).
Le 2e extreme doit etre recent (20 dernieres bougies). Signal de retournement, a confirmer."""
from . import indicators as ind
from .strategies import swings

MAX_SCORE = 6


def analyze(c, w=3, recent=60):
    res = {"name": "rsi_divergence", "direction": "NEUTRE", "score": 0, "max": MAX_SCORE, "reasons": []}
    n = len(c)
    if n < 40:
        res["reasons"] = ["DONNEES INDISPONIBLES : historique insuffisant (divergence RSI)"]
        return res
    r = ind.rsi([x["c"] for x in c])
    lows = [i for i in swings([x["l"] for x in c], "low", w) if i >= n - recent and r[i] is not None]
    highs = [i for i in swings([x["h"] for x in c], "high", w) if i >= n - recent and r[i] is not None]
    bull = bear = None
    if len(lows) >= 2:
        a, b = lows[-2], lows[-1]
        if b >= n - 20 and c[b]["l"] < c[a]["l"] and r[b] > r[a] and r[a] < 45:
            bull = (a, b)
    if len(highs) >= 2:
        a, b = highs[-2], highs[-1]
        if b >= n - 20 and c[b]["h"] > c[a]["h"] and r[b] < r[a] and r[a] > 55:
            bear = (a, b)
    if bull and not bear:
        a, b = bull
        res.update(direction="LONG", score=MAX_SCORE if r[a] < 30 else 5, reasons=[
            f"Divergence haussiere RSI : creux de prix plus bas ({c[a]['l']:g} -> {c[b]['l']:g}) "
            f"mais RSI plus haut ({r[a]:.0f} -> {r[b]:.0f})"])
    elif bear and not bull:
        a, b = bear
        res.update(direction="SHORT", score=MAX_SCORE if r[a] > 70 else 5, reasons=[
            f"Divergence baissiere RSI : sommet de prix plus haut ({c[a]['h']:g} -> {c[b]['h']:g}) "
            f"mais RSI plus bas ({r[a]:.0f} -> {r[b]:.0f})"])
    else:
        res["reasons"] = ["Pas de divergence RSI recente"]
    return res
