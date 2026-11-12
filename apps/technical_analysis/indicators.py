"""Indicateurs de J. Welles Wilder (RSI, ATR, ADX avec lissage de Wilder) et EMA/SMA.
Les bougies sont des dicts {o,h,l,c,v} en float (voir normalize_candles)."""


def normalize_candles(raw):
    """Convertit les bougies Gate.io (valeurs en texte) en floats. Leve ValueError si invalide."""
    out = []
    for r in raw:
        out.append({k: float(r[k]) for k in ("o", "h", "l", "c", "v")})
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
