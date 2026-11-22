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
    if p.get("score_global") is not None:
        c = p.get("confluence") or {}
        lines.append(f"CONFLUENCE : {p['score_global']}/100 ({c.get('class', '')})" + (" - partielle : " + ", ".join(c["missing"]) + " indisponible" if c.get("partial") else ""))
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


def format_market_summary(rows, mode):
    """rows : {symbol, price, change_pct, direction, score}. Message de prix et signaux par monnaie."""
    lines = [f"MARCHE ({mode}) - prix et signaux", ""]
    for r in rows:
        price = "indisponible" if r.get("price") is None else f"{r['price']:g}"
        chg = "" if r.get("change_pct") is None else f" ({r['change_pct']:+.2f}%)"
        sig = r["direction"] if r["direction"] != "NEUTRE" else "neutre"
        lines.append(f"{r['symbol']:<12} {price}{chg} - {sig} {r['score']}/40")
    return "\n".join(lines)


def format_analysis(symbol, a, f, sent=None, conf=None):
    """Outils utilises, direction, score et explication de chacun, puis fondamental."""
    lines = [f"ANALYSE {symbol} - {a['direction']} - technique {a['score']}/40", ""]
    for s in a["strategies"]:
        lines.append(f"* {s['name']} : {s['direction']} {s['score']}/{s['max']}")
        lines += [f"    - {x}" for x in s["reasons"][:3]]
    if a.get("mtf"):
        m = a["mtf"]
        lines += ["", f"Multi-timeframe : 4H {m['4h']} | 1H {m['1h']} | 15M {m['15m']}"]
    lines += ["", "Fondamental : " + ("; ".join(f["reasons"]) if f else "indisponible")]
    for i in (f["items"][:3] if f else []):
        lines.append(f"  [{i['sentiment']}] {i['title'][:100]} ({i['source']})")
    if sent:
        lines += ["", "Sentiment : " + ("; ".join(sent["reasons"]) if sent.get("reasons") else "indisponible")]
        if sent.get("labels"):
            lines.append("  -> " + ", ".join(sent["labels"]))
    if conf:
        parts = conf["parts"]
        lines += ["", f"CONFLUENCE : {conf['score']}/100 ({conf['class']}) - technique {parts['technique'][0]}/40, fondamental "
                      f"{parts['fondamental'][0] if parts['fondamental'][0] is not None else 'n/d'}/35, sentiment "
                      f"{parts['sentiment'][0] if parts['sentiment'][0] is not None else 'n/d'}/25"]
        if conf.get("blocks"):
            lines.append("BLOCAGE : " + " ; ".join(conf["blocks"]))
        lines += conf.get("reasons", [])
    return "\n".join(lines)


def format_news_digest(items):
    """items : actualites NOUVELLES (symbol, title, source, url, sentiment, importance, reliability)."""
    lines = ["NOUVELLES ACTUALITES", ""]
    for i in items:
        lines += [f"[{i['symbol']}] {i['sentiment'].upper()} - importance {i['importance']} - source {i['source']} ({i['reliability']})",
                  i["title"], i["url"], ""]
    return "\n".join(lines)
