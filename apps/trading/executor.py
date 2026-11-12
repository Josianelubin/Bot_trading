"""Execution d'un trade sur Gate.io. Chaque etape est verifiee ; en cas de doute on N'OUVRE PAS.
Politique de securite : si le Stop Loss ne peut pas etre place apres l'ouverture, la position
est fermee immediatement."""
from apps.risk_management.discipline import check_plan

from .gate_private import GateTradeError
from .sizing import contracts_for, round_price

DEFAULT = {"max_slippage_pct": 0.5, "limits": {}}


def _fail(log, msg, **extra):
    log.append("ECHEC : " + msg)
    return {"ok": False, "error": msg, "log": log, **extra}


def execute(trader, p, cfg=None, state=None):
    cfg = {**DEFAULT, **(cfg or {})}
    log, sym, d = [], p["symbol"], p["direction"]
    entry, sl, tp, lev, cap = p["entry"], p["stop_loss"], p["take_profit"], int(p["leverage"]), p["capital_usdt"]
    try:
        bal = trader.balance()
        avail, total = float(bal["available"]), float(bal["total"])
        log.append(f"Solde : {avail:g} disponible / {total:g} total USDT")
        if avail < cap:
            return _fail(log, f"Solde disponible {avail:g} < capital demande {cap:g} USDT")
        st = {"daily_loss_pct": 0.0, "consecutive_losses": 0, "minutes_since_last_loss": None, **(state or {}),
              "equity_usdt": total}
        if "daily_loss_usdt" in st:
            st["daily_loss_pct"] = max(0.0, st["daily_loss_usdt"]) / total * 100 if total else 0.0
        chk = check_plan({"direction": d, "entry": entry, "stop_loss": sl, "take_profit": tp,
                          "capital_usdt": cap, "leverage": lev}, st, cfg["limits"])
        if not chk["allowed"]:
            return _fail(log, "Gestion du risque : " + "; ".join(chk["violations"]))
        log.append("Controles de risque : OK")

        last = float(trader.ticker(sym)["last"])
        slip = abs(last - entry) / entry * 100
        if slip > cfg["max_slippage_pct"]:
            return _fail(log, f"Le prix actuel {last:g} s'ecarte de {slip:.2f}% de ton entree {entry:g} "
                              f"(max {cfg['max_slippage_pct']}%). Redefinis entree, SL et TP puis reconfirme.")
        if not ((d == "LONG" and sl < last < tp) or (d == "SHORT" and tp < last < sl)):
            return _fail(log, f"Le prix actuel {last:g} n'est plus entre ton Stop Loss et ton Take Profit")
        log.append(f"Prix actuel {last:g} (ecart {slip:.2f}%) : OK")

        ct = trader.contract(sym)
        if ct.get("in_delisting") or ct.get("status", "trading") != "trading":
            return _fail(log, "Contrat non negociable")
        if lev > float(ct.get("leverage_max", lev)):
            return _fail(log, f"Levier x{lev} superieur au maximum du contrat ({ct.get('leverage_max')})")
        try:
            n = contracts_for(cap, lev, last, ct["quanto_multiplier"], ct.get("order_size_min", 1))
        except ValueError as e:
            return _fail(log, str(e))
        size = n if d == "LONG" else -n
        log.append(f"Quantite : {n} contrat(s)")

        pos = trader.set_isolated_leverage(sym, lev)
        isolated = int(float(pos.get("leverage", 0))) == lev and pos.get("pos_margin_mode", "isolated") != "cross"
        if not isolated:
            return _fail(log, "Marge ISOLEE non confirmee par Gate : position NON ouverte")
        log.append(f"Marge ISOLEE confirmee, levier x{lev}")

        order = trader.market_order(sym, size, f"t-kps{p['id']}")
        oid = str(order["id"])
        o2 = trader.get_order(oid)
        if not (o2.get("status") == "finished" and o2.get("finish_as") == "filled"):
            try:
                trader.close_position(sym)
            except GateTradeError:
                pass
            return _fail(log, f"Ordre {oid} non rempli completement ({o2.get('status')}/{o2.get('finish_as')}) : "
                              f"fermeture de securite tentee", gate_order_id=oid)
        fill = float(o2.get("fill_price") or last)
        log.append(f"Ordre {oid} REMPLI a {fill:g} (confirme par Gate)")
        out = {"ok": True, "gate_order_id": oid, "fill_price": fill, "size": size, "log": log}

        tick = ct.get("order_price_round", "0.0001")
        try:
            out["sl_order_id"] = str(trader.price_order(sym, round_price(sl, tick), 2 if d == "LONG" else 1)["id"])
            log.append(f"Stop Loss place a {sl:g}")
        except GateTradeError as e:
            log.append(f"Stop Loss IMPOSSIBLE ({e}) : fermeture immediate de la position")
            try:
                trader.close_position(sym)
                return _fail(log, "Stop Loss non place : position refermee par securite", gate_order_id=oid,
                             emergency_closed=True)
            except GateTradeError as e2:
                return _fail(log, f"CRITIQUE : position ouverte SANS Stop Loss et fermeture echouee ({e2}). "
                                  f"FERME-LA MANUELLEMENT SUR GATE MAINTENANT.", gate_order_id=oid, critical=True)
        try:
            out["tp_order_id"] = str(trader.price_order(sym, round_price(tp, tick), 1 if d == "LONG" else 2)["id"])
            log.append(f"Take Profit place a {tp:g}")
        except GateTradeError as e:
            out["warning"] = f"Take Profit NON place ({e}) : la position est protegee par le Stop Loss"
            log.append(out["warning"])
        return out
    except (GateTradeError, KeyError, ValueError, TypeError) as e:
        return _fail(log, f"Erreur ou reponse inattendue de Gate : {e}")
