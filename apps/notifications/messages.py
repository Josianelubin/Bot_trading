"""Mise en forme des messages Telegram. Fonctions pures : aucune donnee inventee.
Un champ absent est affiche 'indisponible' ; la probabilite n'est donnee que si elle
vient d'un backtest reel (sinon 'donnees insuffisantes')."""


def _v(d, key, fmt="{}"):
    val = d.get(key)
    return "indisponible" if val is None else fmt.format(val)


def pnl_percent(entry, target, leverage, direction):
    """Variation en % de la MARGE pour un prix cible (frais non inclus)."""
    move = (target - entry) / entry * 100
    if direction == "SHORT":
        move = -move
    return move * leverage


def format_proposal(p):
    entry, sl, tp = p["entry"], p["stop_loss"], p["take_profit"]
    lev, d = p["leverage"], p["direction"]
    gain = pnl_percent(entry, tp, lev, d)
    loss = pnl_percent(entry, sl, lev, d)
    capital = p.get("capital_usdt")
    lines = [
        f"PROPOSITION #{p['id']} - {p['symbol']} - {d}",
        f"Mode : {p['mode']} | Marge ISOLATED | Levier x{lev}",
        "",
        f"POINT D'ENTREE : {entry}",
        f"Stop Loss : {sl}",
        f"Take Profit : {tp}",
    ]
    if capital:
        lines += [f"Capital engage : {capital} USDT",
                  f"Gain potentiel : {gain:+.2f}% (~{capital * gain / 100:+.2f} USDT)",
                  f"Perte potentielle : {loss:+.2f}% (~{capital * loss / 100:+.2f} USDT)"]
    else:
        lines += [f"Gain potentiel : {gain:+.2f}% de la marge",
                  f"Perte potentielle : {loss:+.2f}% de la marge"]
    lines += ["(frais et funding non inclus)", ""]
    prob = p.get("win_probability_pct")
    n = p.get("backtest_trades")
    if prob is None or not n:
        lines.append("Probabilite de reussite : donnees insuffisantes")
    else:
        lines.append(f"Probabilite historique : {prob:.0f}% reussite / {100 - prob:.0f}% echec "
                     f"(backtest sur {n} trades, ne garantit rien)")
    lines += [
        "",
        f"Scores - technique {_v(p, 'score_technical')}/40, fondamental {_v(p, 'score_fundamental')}/35, "
        f"sentiment {_v(p, 'score_sentiment')}/25, global {_v(p, 'score_global')}/100",
        "Outils utilises : " + (", ".join(p.get("tools", [])) or "indisponible"),
        "",
        "Raisons :",
    ] + [f"- {r}" for r in p.get("reasons", [])] + ["", "Risques :"] + \
        [f"- {r}" for r in p.get("risks", [])]
    if p.get("expires_at"):
        lines += ["", f"Expire a : {p['expires_at']}"]
    return "\n".join(lines)


def format_result(t):
    won = t["net_pnl"] > 0
    return "\n".join([
        f"TRADE {'REUSSI' if won else 'ECHOUE'} - {t['symbol']} {t['direction']} ({t['mode']})",
        f"Entree : {t['entry']} | Sortie : {_v(t, 'exit')} ({_v(t, 'exit_reason')})",
        f"PNL net : {t['net_pnl']:+.2f} USDT (frais : {_v(t, 'fees', '{:.4f}')})",
        f"Duree : {_v(t, 'duration')}",
        "",
        "Explication : " + (t.get("explanation") or "indisponible"),
    ])


def format_news(n):
    return "\n".join([
        f"ACTUALITE [{n.get('sentiment', 'neutre').upper()}] - importance {_v(n, 'importance')}",
        n["title"],
        f"Source : {n['source']} | Publiee : {_v(n, 'published_at')}",
        f"Cryptos : {', '.join(n.get('symbols', [])) or 'general'}",
        f"Resume : {_v(n, 'summary')}",
        n["url"],
    ])
