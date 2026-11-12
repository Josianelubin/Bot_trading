"""Logique pure de decision (testable sans Django). Aucun ordre n'est envoye ici."""


def parse_callback(data):
    try:
        action, pid = data.split(":", 1)
        if action in ("accept", "reject", "edit"):
            return action, int(pid)
    except (ValueError, AttributeError):
        pass
    return None, None


def decide(status, expired, action):
    """Retourne (nouveau_statut_ou_None, message). Ne jamais traiter deux fois une proposition."""
    if status != "pending":
        return None, f"Proposition deja traitee (statut : {status}). Rien n'a ete fait."
    if expired:
        return "expired", "Proposition EXPIREE : le marche a pu changer, aucune action. Attends la prochaine analyse."
    if action == "accept":
        return "accepted", ("ACCEPTEE. AUCUN ordre envoye pour l'instant : ouvre le dashboard, verifie entree, "
                            "Stop Loss et Take Profit, puis clique EXECUTE TRADE.")
    if action == "reject":
        return "rejected", "REJETEE : enregistree, aucun ordre envoye."
    return None, "MODIFIER : l'edition des parametres arrive avec le dashboard (Phase 10). Rien n'a ete change."
