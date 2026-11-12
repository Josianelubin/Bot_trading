"""Construit une proposition de trade a partir des bougies reelles (4H, 1H, 15M).
Analyse TECHNIQUE seule pour l'instant : fondamental et sentiment ne sont pas encore actifs.
La derniere bougie (en cours) est ignoree : on n'analyse que des bougies cloturees."""
from apps.risk_management.discipline import check_plan
from apps.technical_analysis import engine

DEFAULT_CFG = {
    "min_score": 24,            # sur 40 (analyse technique)
    "reward_risk": 2.0,
    "leverage": 5,
    "max_leverage": 10,
    "capital_usdt": 20.0,
    "equity_usdt": 1000.0,
    "ttl_minutes": 30,
    "mode": "DEMO",
    "limits": {},
}


def _r(x):
    return float(f"{x:.6g}")


def build_proposal(symbol, c4h, c1h, c15, cfg=None):
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    a = engine.analyze_mtf(c4h[:-1], c1h[:-1], c15[:-1])
    if a["direction"] == "NEUTRE":
        return {"status": "none", "reason": "NEUTRE", "analysis": a}
    if a["score"] < cfg["min_score"]:
        return {"status": "none", "reason": f"score {a['score']} < {cfg['min_score']}", "analysis": a}
    d = a["direction"]
    entry = c15[-2]["c"]
    sl = a["suggested"]["stop_loss"]
    dist = abs(entry - sl)
    tp = entry + cfg["reward_risk"] * dist if d == "LONG" else entry - cfg["reward_risk"] * dist
    lev = min(int(cfg["leverage"]), int(cfg["max_leverage"]))
    liq = entry * (1 - 1 / lev) if d == "LONG" else entry * (1 + 1 / lev)
    plan = {"direction": d, "entry": _r(entry), "stop_loss": _r(sl), "take_profit": _r(tp),
            "capital_usdt": cfg["capital_usdt"], "leverage": lev}
    state = {"equity_usdt": cfg["equity_usdt"], "daily_loss_pct": 0.0, "consecutive_losses": 0,
             "minutes_since_last_loss": None}
    chk = check_plan(plan, state, cfg["limits"])
    used = [r for r in a["strategies"] if r["direction"] == d]
    proposal = {
        **plan, "symbol": symbol, "mode": cfg["mode"], "score_technical": a["score"],
        "score_fundamental": None, "score_sentiment": None, "score_global": None,
        "tools": [r["name"] for r in used],
        "reasons": [x for r in used for x in r["reasons"]][:14],
        "risks": ["Analyse technique SEULE : fondamental et sentiment pas encore actifs",
                  f"Liquidation approx. vers {_r(liq)} (marge isolee x{lev}, hors frais)",
                  "Le stop (2 x ATR) et le gain (ratio %.1f) sont des suggestions modifiables" % cfg["reward_risk"]],
        "mtf": a.get("mtf"), "ttl_minutes": cfg["ttl_minutes"],
        "zones": a.get("zones"),
    }
    if not chk["allowed"]:
        return {"status": "blocked", "violations": chk["violations"], "proposal": proposal}
    return {"status": "proposal", "proposal": proposal}
