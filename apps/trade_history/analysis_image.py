"""PHOTO D'ANALYSE annotee (comme un graphique commente) : bougies reelles, Bandes de Bollinger, zones de demande /
support ou d'offre / resistance, FVG / imbalance, zone d'entree, liquidite Buy-Side / Sell-Side, CHoCH, Stop Loss,
TP1-TP3 et legende. Tout est calcule a partir des vraies bougies et du resultat du scanner (aucun niveau invente).
Necessite Pillow ; sans Pillow, l'appelant retombe sur le rendu simple (chart.render_png)."""
import io
import os
from datetime import datetime, timezone

from PIL import Image, ImageDraw, ImageFont

from apps.technical_analysis import bollinger, indicators as ind

W, H = 1500, 860
LM, RM, TM, BM = 12, 104, 64, 22
BG = (10, 18, 38)
GREEN, RED, BLUE, GREY = (38, 166, 154), (239, 83, 80), (96, 165, 250), (130, 140, 155)
TEAL, ORANGE, LIQ = (20, 120, 120), (234, 140, 40), (160, 40, 50)
YELLOW, WHITE = (250, 204, 21), (235, 240, 250)


_FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")


def _font(size, bold=False):
    """DejaVu Sans (fournie avec le projet : accents francais OK) ; sinon police par defaut de Pillow."""
    try:
        return ImageFont.truetype(os.path.join(_FONT_DIR, "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"), size)
    except OSError:
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()


def fmt(v):
    a = abs(v)
    d = 2 if a >= 1000 else 4 if a >= 1 else 6
    return f"{v:,.{d}f}".rstrip("0").rstrip(".") if "." in f"{v:,.{d}f}" else f"{v:,.{d}f}"


def render_analysis(candles, result, smc=None, symbol="", tf="", n=90):
    c = candles[-n:]
    if len(c) < 5:
        raise ValueError("Pas assez de bougies pour la photo d'analyse")
    off = len(candles) - len(c)
    smc = smc or {}
    d = result.get("direction")
    has_levels = d in ("LONG", "SHORT") and result.get("entry") is not None
    long = d == "LONG"
    atr = ind.atr(candles, 14)[-1] or (c[-1]["h"] - c[-1]["l"]) or 1.0
    times = [x.get("t") for x in c]

    entry = result.get("entry")
    sl = result.get("stop_loss")
    tps = list(result.get("take_profits") or ([result["take_profit"]] if result.get("take_profit") else []))
    ict = result.get("ict")

    # ---- niveaux de liquidite retenus (sommets / creux non pris + extremes 24 h) ----
    last = c[-1]["c"]
    bsl = [l["price"] for l in smc.get("liquidity", []) if l["side"] == "BSL" and l["price"] > last]
    ssl = [l["price"] for l in smc.get("liquidity", []) if l["side"] == "SSL" and l["price"] < last]
    r24 = smc.get("range24")
    if r24:
        bsl.append(r24["high"]["price"])
        ssl.append(r24["low"]["price"])
    bsl_p = max(bsl) if bsl else None
    ssl_p = min(ssl) if ssl else None

    # ---- echelle de prix ----
    scale_tps = tps[:2]   # TP3 (extension lointaine) n'ecrase pas l'echelle : s'il sort du cadre, il est cite dans l'en-tete
    lo = min([x["l"] for x in c] + [v for v in (sl, entry) if v is not None] + scale_tps)
    hi = max([x["h"] for x in c] + [v for v in (sl, entry) if v is not None] + scale_tps)
    span = hi - lo or 1.0
    if bsl_p and bsl_p - hi <= 0.35 * span:
        hi = max(hi, bsl_p + 0.3 * atr)
    if ssl_p and lo - ssl_p <= 0.35 * span:
        lo = min(lo, ssl_p - 0.3 * atr)
    pad = (hi - lo) * 0.05
    hi, lo = hi + pad, lo - pad
    px0, px1, py0, py1 = LM, W - RM, TM, H - BM

    def Y(p):
        return py0 + (hi - p) / (hi - lo) * (py1 - py0)

    step = (px1 - px0) / len(c)

    def X(i):
        return px0 + (i + 0.5) * step

    def idx_of(t):
        if t is None or None in times:
            return None
        for i, tt in enumerate(times):
            if tt >= t:
                return i
        return None

    img = Image.new("RGBA", (W, H), BG + (255,))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)

    def zone(lo_p, hi_p, color, alpha, x_from=px0):
        y_a, y_b = Y(min(hi_p, hi)), Y(max(lo_p, lo))
        if y_b - y_a < 2:
            y_b = y_a + 2
        od.rectangle([x_from, y_a, px1, y_b], fill=color + (alpha,), outline=color + (min(255, alpha + 70),))
        return y_a, y_b

    labels = []   # (x, y, texte, fond, texte_couleur)

    # ---- zone de demande / support (LONG) ou d'offre / resistance (SHORT) ----
    obs = [o for o in smc.get("ob", []) if o["type"] == ("bullish" if long else "bearish")]
    z_lo = z_hi = None
    if ict:
        z_lo, z_hi = (min(ict["invalidation"], ict["zone"][0]), ict["zone"][0]) if long else (ict["zone"][1], max(ict["invalidation"], ict["zone"][1]))
    if obs:
        ob = min(obs, key=lambda o: abs((o["lo"] + o["hi"]) / 2 - (entry if entry is not None else last)))
        z_lo = ob["lo"] if z_lo is None else min(z_lo, ob["lo"])
        z_hi = ob["hi"] if z_hi is None else max(z_hi, ob["hi"])
    if z_lo is not None and z_hi is not None and z_hi > z_lo and d in ("LONG", "SHORT"):
        col = TEAL if long else (140, 50, 60)
        start = None
        if ict and ict.get("leg"):
            start = ict["leg"]["low_index"] - off if long else ict["leg"].get("high_index", 0) - off
        elif obs:
            j = idx_of(ob["time"])
            start = j
        xz = max(px0, X(start) - step) if start is not None and start >= 0 else px0
        ya, yb = zone(z_lo, z_hi, col, 110, x_from=xz)
        labels.append(((xz + px1) / 2, (ya + yb) / 2, "SUPPORT" if long else "RÉSISTANCE", None, WHITE, 30))
    # ---- FVG / imbalance ----
    fv = [g for g in smc.get("fvg", [])]
    fv.sort(key=lambda g: (g["type"] != ("bullish" if long else "bearish"), -g["time"]))
    for g in fv[:3]:
        i0 = idx_of(g["time"])
        xf = X(i0) if i0 is not None else px0
        ya, yb = zone(g["lo"], g["hi"], ORANGE, 120, x_from=max(px0, xf))
    if fv:
        g = fv[0]
        labels.append((px0 + (px1 - px0) * 0.52, Y((g["lo"] + g["hi"]) / 2), "FVG / IMBALANCE", (190, 100, 20), WHITE, 18))
    # ---- zone d'entree ----
    if has_levels:
        e_lo, e_hi = (ict["zone"][0], ict["zone"][1]) if ict else (entry - 0.25 * atr, entry + 0.25 * atr)
        xs = max(px0, X(max(0, len(c) - 26)))
        ya, yb = zone(e_lo, e_hi, (40, 170, 70), 120, x_from=xs)
        labels.append((xs + 150, (ya + yb) / 2, "ENTRY / POINT D'ENTRÉE" if long else "ENTRY / POINT D'ENTRÉE (SELL)", None, WHITE, 20))
    # ---- liquidite Buy-Side / Sell-Side ----
    for p_, txt, up in ((bsl_p, "LIQUIDITÉ BUY-SIDE", True), (ssl_p, "LIQUIDITÉ SELL-SIDE", False)):
        if p_ is not None and lo <= p_ <= hi:
            ya, yb = zone(p_ - 0.0 if up else p_ - 0.3 * atr, p_ + 0.3 * atr if up else p_, LIQ, 140)
            labels.append((px0 + (px1 - px0) * (0.80 if up else 0.70), (ya + yb) / 2 - 2, txt, (150, 35, 45), WHITE, 22))
    img = Image.alpha_composite(img, ov)
    dr = ImageDraw.Draw(img)

    # ---- Bandes de Bollinger + bougies ----
    bands = bollinger.compute_bands([x["c"] for x in candles])[off:]
    for key, col, w in (("upper", BLUE, 2), ("lower", BLUE, 2), ("middle", GREY, 1)):
        pts = [(X(i), Y(b[key])) for i, b in enumerate(bands) if b]
        if len(pts) > 1:
            dr.line(pts, fill=col, width=w)
    half = max(1, int(step * 0.32))
    for i, x in enumerate(c):
        col = GREEN if x["c"] >= x["o"] else RED
        cx = X(i)
        dr.line([(cx, Y(x["h"])), (cx, Y(x["l"]))], fill=col, width=1)
        y_a, y_b = sorted((Y(x["o"]), Y(x["c"])))
        dr.rectangle([cx - half, y_a, cx + half, max(y_b, y_a + 1)], fill=col)

    # ---- CHoCH / MSS / BOS ----
    evs = [e for e in smc.get("events", []) if e["type"] in ("CHoCH", "MSS", "BOS")]
    if evs:
        e = next((x for x in reversed(evs) if x["type"] in ("CHoCH", "MSS")), evs[-1])
        i = idx_of(e["to"])
        if i is not None and lo <= e["level"] <= hi:
            xx, yy = X(i), Y(e["level"])
            dr.line([(X(max(0, idx_of(e["from"]) or 0)), yy), (xx, yy)], fill=(120, 190, 255), width=1)
            labels.append((xx - 80, yy - 54, e["type"], (20, 120, 70), WHITE, 22))
            dr.line([(xx - 60, yy - 38), (xx - 6, yy - 4)], fill=(60, 230, 120), width=3)

    # ---- lignes Stop Loss / Entree / Take Profit ----
    if has_levels:
        xs = max(px0, X(max(0, len(c) - 26)))
        for val, col, txt in [(sl, RED, "STOP LOSS")] + [(t, (60, 230, 90), f"TP{k + 1}") for k, t in enumerate(tps[:3])] + [(entry, YELLOW, "ENTRÉE")]:
            if val is None or not (lo <= val <= hi):
                continue
            y = Y(val)
            dr.line([(xs, y), (px1, y)], fill=col, width=2)
            fbig = _font(18, True)
            tw = dr.textlength(txt, font=fbig)
            dr.rounded_rectangle([xs - tw - 28, y - 15, xs - 6, y + 15], radius=6, fill=(120, 20, 30) if col == RED else (20, 90, 40) if txt.startswith("TP") else (110, 90, 10))
            dr.text((xs - tw - 17, y - 11), txt, fill=WHITE, font=fbig)
            ft = _font(17)
            tag = fmt(val)
            tw2 = dr.textlength(tag, font=ft)
            dr.rounded_rectangle([px1 + 4, y - 12, px1 + 14 + tw2, y + 12], radius=4, fill=col if col != RED else (200, 40, 50))
            dr.text((px1 + 9, y - 9), tag, fill=(10, 10, 20), font=ft)

    # ---- etiquettes ----
    for x, y, txt, bg, fg, size in labels:
        f_ = _font(int(size * 0.85), True)
        tw = dr.textlength(txt, font=f_)
        if bg:
            dr.rounded_rectangle([x - tw / 2 - 10, y - size * 0.7, x + tw / 2 + 10, y + size * 0.7], radius=6, fill=bg, outline=(255, 255, 255, 90))
        dr.text((x - tw / 2, y - size * 0.5), txt, fill=fg, font=f_)

    # ---- en-tete ----
    big, small = _font(26, True), _font(17)
    title = f"{symbol.replace('_', '/')}  ·  {tf.upper()}  ·  " + (d if has_levels else "ATTENTE")
    dr.text((LM + 4, 10), title, fill=WHITE, font=big)
    sub = []
    conf = result.get("confluence")
    if conf:
        sub.append(f"Confluence {conf['score']}/100 ({conf['class']})")
    if result.get("score") is not None:
        sub.append(f"Score technique {result['score']}/{result.get('max_score', 40)}")
    if ict:
        sub.append(f"Setup ICT {ict['grade']} ({ict['score']}/{ict['max']})")
    if has_levels and sl is not None and entry:
        risk = abs(entry - sl)
        if risk and tps:
            sub.append("R:R TP1 " + f"{abs(tps[0] - entry) / risk:.1f}" + (f" · TP2 {abs(tps[1] - entry) / risk:.1f}" if len(tps) > 1 else ""))
        if len(tps) > 2 and not (lo <= tps[2] <= hi):
            sub.append(f"TP3 {fmt(tps[2])} (hors cadre)")
    dr.text((LM + 4, 38), "  |  ".join(sub) if sub else (result.get("message") or "")[:120], fill=(170, 185, 210), font=small)
    stamp = result.get("timestamp") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sw = dr.textlength(stamp[:19].replace("T", " ") + " UTC", font=small)
    dr.text((W - RM - sw, 14), stamp[:19].replace("T", " ") + " UTC", fill=(170, 185, 210), font=small)
    if not has_levels:
        msg = (result.get("message") or "ATTENTE")[:110]
        f_ = _font(20, True)
        tw = dr.textlength(msg, font=f_)
        dr.rounded_rectangle([W / 2 - tw / 2 - 16, TM + 8, W / 2 + tw / 2 + 16, TM + 46], radius=8, fill=(120, 70, 10), outline=(250, 170, 60))
        dr.text((W / 2 - tw / 2, TM + 15), msg, fill=WHITE, font=f_)

    # ---- legende ----
    rows = [((TEAL if long else (140, 50, 60)), "Zone de demande / Support" if long else "Zone d'offre / Résistance", "box"),
            (LIQ, "Zone de liquidité", "box"), (ORANGE, "FVG / Imbalance", "box"),
            ((40, 170, 70), "Entrée (Buy)" if long else "Entrée (Sell)", "box"), (RED, "Stop Loss", "line"),
            ((60, 230, 90), "Take Profit (TP)", "line"), (BLUE, "Bandes de Bollinger", "line")]
    fl, ft2 = _font(16), _font(21, True)
    lx, ly, lw, lh = LM + 6, H - BM - 8 - (len(rows) * 28 + 46), 300, len(rows) * 28 + 46
    dr.rounded_rectangle([lx, ly, lx + lw, ly + lh], radius=8, fill=(12, 22, 44), outline=(70, 90, 130))
    dr.text((lx + 12, ly + 8), "LÉGENDE", fill=WHITE, font=ft2)
    for k, (col, txt, kind) in enumerate(rows):
        yy = ly + 44 + k * 28
        if kind == "box":
            dr.rectangle([lx + 12, yy, lx + 52, yy + 18], fill=col + (150,), outline=col)
        else:
            dr.line([(lx + 12, yy + 9), (lx + 52, yy + 9)], fill=col, width=3)
        dr.text((lx + 64, yy), txt, fill=WHITE, font=fl)

    out = io.BytesIO()
    img.convert("RGB").save(out, "PNG", optimize=True)
    return out.getvalue()
