def performance(rows):
    """rows : [(timestamp_secondes, pnl_net)] des trades CLOTURES, tries par date. Courbe cumulee reelle."""
    cum, pts, last_t = 0.0, [], 0
    for t, p in rows:
        cum += p
        t = max(int(t), last_t + 1)
        last_t = t
        pts.append({"time": t, "value": round(cum, 4)})
    wins = sum(1 for _, p in rows if p > 0)
    n = len(rows)
    return {"points": pts, "n": n, "wins": wins, "losses": n - wins, "pnl": round(cum, 4),
            "rate": round(100 * wins / n, 1) if n else None}
