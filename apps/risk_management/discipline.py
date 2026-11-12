"""Discipline de trading (principes de Mark Douglas) : regles fixees AVANT l'entree,
pas de revenge trading, risque constant, acceptation de la perte.
Ce module peut BLOQUER une proposition ; le score ne l'annule jamais."""

DEFAULT_LIMITS = {
    "max_risk_pct": 1.0,        # risque max par trade, % de l'equité
    "min_reward_risk": 1.5,
    "max_daily_loss_pct": 3.0,
    "max_consecutive_losses": 3,
    "cooldown_minutes": 30,     # delai minimal apres une perte (anti revenge trading)
    "liq_safety": 0.8,          # le stop doit etre a < 80 % de la distance de liquidation
}


def check_plan(plan, state, limits=None):
    """plan: direction, entry, stop_loss, take_profit, capital_usdt, leverage.
    state: equity_usdt, daily_loss_pct, consecutive_losses, minutes_since_last_loss (ou None)."""
    L = {**DEFAULT_LIMITS, **(limits or {})}
    v = []
    d, e, sl, tp = plan["direction"], plan["entry"], plan.get("stop_loss"), plan.get("take_profit")
    if not sl:
        v.append("Stop Loss obligatoire (regle fixee avant l'entree)")
    elif (d == "LONG" and sl >= e) or (d == "SHORT" and sl <= e):
        v.append("Stop Loss du mauvais cote du prix d'entree")
    if not tp:
        v.append("Take Profit obligatoire")
    elif (d == "LONG" and tp <= e) or (d == "SHORT" and tp >= e):
        v.append("Take Profit du mauvais cote du prix d'entree")
    if not v:
        dist = abs(e - sl) / e
        reward = abs(tp - e) / e
        risk_usdt = plan["capital_usdt"] * plan["leverage"] * dist
        risk_pct = risk_usdt / state["equity_usdt"] * 100
        if risk_pct > L["max_risk_pct"]:
            v.append(f"Risque {risk_pct:.2f}% de l'equite > limite {L['max_risk_pct']}%")
        if reward / dist < L["min_reward_risk"]:
            v.append(f"Ratio gain/risque {reward / dist:.2f} < {L['min_reward_risk']}")
        if dist >= L["liq_safety"] / plan["leverage"]:
            v.append("Stop Loss trop proche de la liquidation (marge isolee) : reduire le levier")
    if state["daily_loss_pct"] >= L["max_daily_loss_pct"]:
        v.append("Perte quotidienne maximale atteinte : plus de nouveau trade aujourd'hui")
    if state["consecutive_losses"] >= L["max_consecutive_losses"]:
        v.append(f"{state['consecutive_losses']} pertes consecutives : pause obligatoire")
    m = state.get("minutes_since_last_loss")
    if m is not None and m < L["cooldown_minutes"]:
        v.append(f"Delai anti revenge trading : attendre encore {L['cooldown_minutes'] - m} min")
    return {"allowed": not v, "violations": v}
