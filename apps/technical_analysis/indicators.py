"""Indicateurs de J. Welles Wilder (RSI, ATR, ADX avec lissage de Wilder) et EMA/SMA.
Les bougies sont des dicts {o,h,l,c,v} en float (voir normalize_candles)."""


def normalize_candles(raw):
    """Convertit les bougies Gate.io (valeurs en texte) en floats. Leve ValueError si invalide."""
    out = []
    for r in raw:
        x = {k: float(r[k]) for k in ("o", "h", "l", "c", "v")}
        if "t" in r:
            x["t"] = int(float(r["t"]))
        out.append(x)
    return out


def sma(values, period):
    out = [None] * len(values)
    for i in range(period - 1, len(values)):
        out[i] = sum(values[i + 1 - period:i + 1]) / period
    return out


def ema(values, period):
    out = [None] * len(values)
    if len(values) < period:
        return out
    out[period - 1] = sum(values[:period]) / period
    k = 2 / (period + 1)
    for i in range(period, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return out


def rsi(closes, period=14):
    out = [None] * len(closes)
    if len(closes) <= period:
        return out
    gains = [max(closes[i] - closes[i - 1], 0) for i in range(1, period + 1)]
    losses = [max(closes[i - 1] - closes[i], 0) for i in range(1, period + 1)]
    ag, al = sum(gains) / period, sum(losses) / period

    def val():
        return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)

    out[period] = val()
    for i in range(period + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        ag = (ag * (period - 1) + max(d, 0)) / period
        al = (al * (period - 1) + max(-d, 0)) / period
        out[i] = val()
    return out


def _true_ranges(c):
    tr = [c[0]["h"] - c[0]["l"]]
    for i in range(1, len(c)):
        tr.append(max(c[i]["h"] - c[i]["l"], abs(c[i]["h"] - c[i - 1]["c"]), abs(c[i]["l"] - c[i - 1]["c"])))
    return tr


def atr(c, period=14):
    out = [None] * len(c)
    if len(c) < period:
        return out
    tr = _true_ranges(c)
    out[period - 1] = sum(tr[:period]) / period
    for i in range(period, len(c)):
        out[i] = (out[i - 1] * (period - 1) + tr[i]) / period
    return out


def adx(c, period=14):
    n = len(c)
    res = {"plus_di": [None] * n, "minus_di": [None] * n, "adx": [None] * n}
    if n < 2 * period + 1:
        return res
    tr, pdm, mdm = [0.0] * n, [0.0] * n, [0.0] * n
    for i in range(1, n):
        up, dn = c[i]["h"] - c[i - 1]["h"], c[i - 1]["l"] - c[i]["l"]
        pdm[i] = up if up > dn and up > 0 else 0.0
        mdm[i] = dn if dn > up and dn > 0 else 0.0
        tr[i] = max(c[i]["h"] - c[i]["l"], abs(c[i]["h"] - c[i - 1]["c"]), abs(c[i]["l"] - c[i - 1]["c"]))
    trs, ps, ms = sum(tr[1:period + 1]), sum(pdm[1:period + 1]), sum(mdm[1:period + 1])
    dx = [None] * n
    for i in range(period, n):
        if i > period:
            trs = trs - trs / period + tr[i]
            ps = ps - ps / period + pdm[i]
            ms = ms - ms / period + mdm[i]
        pdi = 100 * ps / trs if trs else 0.0
        mdi = 100 * ms / trs if trs else 0.0
        res["plus_di"][i], res["minus_di"][i] = pdi, mdi
        dx[i] = 100 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) else 0.0
    start = 2 * period - 1
    res["adx"][start] = sum(dx[period:2 * period]) / period
    for i in range(start + 1, n):
        res["adx"][i] = (res["adx"][i - 1] * (period - 1) + dx[i]) / period
    return res


def macd(closes, fast=12, slow=26, signal=9):
    """MACD (12, 26, 9) : listes alignees sur closes (None tant que non calculable)."""
    n = len(closes)
    ef, es = ema(closes, fast), ema(closes, slow)
    line = [None if a is None or b is None else a - b for a, b in zip(ef, es)]
    vals = [x for x in line if x is not None]
    sig_vals = ema(vals, signal)
    off = n - len(vals)
    sig = [None] * off + sig_vals
    hist = [None if m is None or s_ is None else m - s_ for m, s_ in zip(line, sig)]
    return {"macd": line, "signal": sig, "hist": hist}


def vwap(c):
    """VWAP recalcule chaque jour UTC (si les bougies ont un temps 't'), sinon cumule depuis le debut."""
    out, day, pv, vv = [], None, 0.0, 0.0
    for x in c:
        d = x["t"] // 86400 if "t" in x else None
        if d != day:
            day, pv, vv = d, 0.0, 0.0
        typical = (x["h"] + x["l"] + x["c"]) / 3
        pv, vv = pv + typical * x["v"], vv + x["v"]
        out.append(pv / vv if vv else typical)
    return out


def fib_levels(c, lookback=100):
    """Retracements de Fibonacci du dernier mouvement (plus bas -> plus haut ou inverse)."""
    w = c[-lookback:]
    hi_i = max(range(len(w)), key=lambda i: w[i]["h"])
    lo_i = min(range(len(w)), key=lambda i: w[i]["l"])
    hi, lo = w[hi_i]["h"], w[lo_i]["l"]
    up = hi_i > lo_i
    ratios = (0.236, 0.382, 0.5, 0.618, 0.786)
    levels = {r: (hi - r * (hi - lo) if up else lo + r * (hi - lo)) for r in ratios}
    return {"high": hi, "low": lo, "trend": "up" if up else "down", "levels": levels}


def _sma_opt(values, period):
    out = [None] * len(values)
    for i in range(period - 1, len(values)):
        w = values[i + 1 - period:i + 1]
        if all(x is not None for x in w):
            out[i] = sum(w) / period
    return out


def stoch_rsi(closes, rsi_p=14, stoch_p=14, k=3, d=3):
    """Stoch RSI (14, 14, 3, 3) : retourne {k, d} alignes sur closes, valeurs 0..100."""
    r = rsi(closes, rsi_p)
    raw = [None] * len(closes)
    for i in range(len(closes)):
        w = r[max(0, i - stoch_p + 1):i + 1]
        if len(w) == stoch_p and all(x is not None for x in w):
            hi, lo = max(w), min(w)
            raw[i] = (r[i] - lo) / (hi - lo) * 100 if hi != lo else 50.0
    kl = _sma_opt(raw, k)
    return {"k": kl, "d": _sma_opt(kl, d)}
