"""Construit une proposition de trade a partir des bougies reelles (4H, 1H, 15M).
Analyse TECHNIQUE seule pour l'instant : fondamental et sentiment ne sont pas encore actifs.
La derniere bougie (en cours) est ignoree : on n'analyse que des bougies cloturees."""
from datetime import datetime, timezone

from apps.fundamental_analysis import engine as fundamental
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
    "require_news": True,
}


def _r(x):
    return float(f"{x:.6g}")


def build_proposal(symbol, c4h, c1h, c15, cfg=None, news=None):
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    a = engine.analyze_mtf(c4h[:-1], c1h[:-1], c15[:-1])
    d = a["direction"]
    f = fundamental.assess(news, None if d == "NEUTRE" else d, datetime.now(timezone.utc), cfg["require_news"])
    base = {"analysis": a, "fundamental": f}
    if d == "NEUTRE":
        return {"status": "none", "reason": "NEUTRE", **base}
    if a["score"] < cfg["min_score"]:
        return {"status": "none", "reason": f"score {a['score']} < {cfg['min_score']}", **base}
    if f["block"]:
        return {"status": "blocked", "violations": [f["block"]], **base}
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
    fs = f["score"]
    partial = (f"Score partiel : technique {a['score']}/40 + fondamental {fs}/35 = {a['score'] + fs}/75 "
               "(sentiment pas encore actif)") if fs is not None else None
    proposal = {
        **plan, "symbol": symbol, "mode": cfg["mode"], "score_technical": a["score"],
        "score_fundamental": fs, "score_sentiment": None, "score_global": None,
        "tools": [r["name"] for r in used],
        "reasons": ([x for r in used for x in r["reasons"]] + f["reasons"] + ([partial] if partial else []))[:16],
        "news": [{"title": i["title"], "source": i["source"], "url": i["url"], "sentiment": i["sentiment"]}
                 for i in f["items"][:5]],
        "risks": ["Sentiment du marche pas encore actif (analyse technique + actualites seulement)",
                  f"Liquidation approx. vers {_r(liq)} (marge isolee x{lev}, hors frais)",
                  "Le stop (2 x ATR) et le gain (ratio %.1f) sont des suggestions modifiables" % cfg["reward_risk"]],
        "mtf": a.get("mtf"), "ttl_minutes": cfg["ttl_minutes"],
        "zones": a.get("zones"),
    }
    if not chk["allowed"]:
        return {"status": "blocked", "violations": chk["violations"], "proposal": proposal, **base}
    return {"status": "proposal", "proposal": proposal, **base}
