"""Rendu PNG d'une analyse a partir des VRAIES bougies (aucune dependance externe).
Pas de texte dans l'image : la legende est dans la legende Telegram (CHART_LEGEND)."""
import struct
import zlib

from apps.technical_analysis import bollinger

CHART_LEGEND = ("Legende : jaune = entree, rouge = Stop Loss, vert = Take Profit, "
                "bleu = Bandes de Bollinger, zones vertes/rouges = Order Blocks et FVG valides "
                "(haussier/baissier).")

BG, GREEN, RED = (15, 23, 42), (38, 166, 154), (239, 83, 80)
YELLOW, SLC, TPC, BLUE, GREY = (250, 204, 21), (239, 68, 68), (34, 197, 94), (96, 165, 250), (100, 116, 139)


def _png(rows, w, h):
    raw = b"".join(b"\x00" + bytes(r) for r in rows)

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def render_png(candles, entry=None, stop_loss=None, take_profit=None, zones=None, n=80, W=900, H=520):
    c = candles[-n:]
    if len(c) < 5:
        raise ValueError("Pas assez de bougies pour le graphique")
    offset = len(candles) - len(c)
    L, R, T, B = 10, W - 10, 10, 10
    rows = [bytearray(bytes(BG) * W) for _ in range(H)]
    levels = [v for v in (entry, stop_loss, take_profit) if v is not None]
    hi = max([x["h"] for x in c] + levels)
    lo = min([x["l"] for x in c] + levels)
    pad = (hi - lo) * 0.04 or 1.0
    hi, lo = hi + pad, lo - pad

    def Y(p):
        return int(T + (hi - p) / (hi - lo) * (H - T - B - 1))

    def px(x, y, col):
        if L <= x < R and 0 <= y < H:
            i = x * 3
            rows[y][i], rows[y][i + 1], rows[y][i + 2] = col

    def rect(x0, y0, x1, y1, col, a=1.0):
        x0, x1 = max(L, x0), min(R, x1)
        y0, y1 = max(0, min(y0, y1)), min(H - 1, max(y0, y1))
        for y in range(y0, y1 + 1):
            if a >= 1:
                rows[y][x0 * 3:x1 * 3] = bytes(col) * max(0, x1 - x0)
            else:
                row = rows[y]
                for x in range(x0, x1):
                    i = x * 3
                    row[i] = int(row[i] * (1 - a) + col[0] * a)
                    row[i + 1] = int(row[i + 1] * (1 - a) + col[1] * a)
                    row[i + 2] = int(row[i + 2] * (1 - a) + col[2] * a)

    def line(x0, y0, x1, y1, col):
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            px(x0, y0, col)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy; x0 += sx
            if e2 <= dx:
                err += dx; y0 += sy

    step = (R - L) / len(c)

    def X(i):
        return int(L + (i + 0.5) * step)

    # zones ICT valides
    z = zones or {}
    for g in z.get("fvg", []):
        if g["status"] in ("ouvert", "partiel") and g["index"] >= offset:
            rect(X(g["index"] - offset), Y(g["hi"]), R, Y(g["lo"]), GREEN if g["type"] == "bullish" else RED, 0.22)
    for ob in z.get("order_blocks", []):
        if ob["valid"] and ob["index"] >= offset:
            rect(X(ob["index"] - offset), Y(ob["hi"]), R, Y(ob["lo"]), GREEN if ob["type"] == "bullish" else RED, 0.32)
    # zones risque / gain
    if entry is not None and stop_loss is not None:
        rect(R - 120, Y(entry), R, Y(stop_loss), SLC, 0.15)
    if entry is not None and take_profit is not None:
        rect(R - 120, Y(entry), R, Y(take_profit), TPC, 0.15)
    # Bollinger
    bands = bollinger.compute_bands([x["c"] for x in candles])[offset:]
    for key, col in (("upper", BLUE), ("lower", BLUE), ("middle", GREY)):
        pts = [(X(i), Y(b[key])) for i, b in enumerate(bands) if b]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            line(x0, y0, x1, y1, col)
    # bougies
    half = max(1, int(step * 0.35))
    for i, x in enumerate(c):
        col = GREEN if x["c"] >= x["o"] else RED
        cx = X(i)
        line(cx, Y(x["h"]), cx, Y(x["l"]), col)
        rect(cx - half, Y(max(x["o"], x["c"])), cx + half + 1, max(Y(min(x["o"], x["c"])), Y(max(x["o"], x["c"])) + 1), col)
    # niveaux
    for val, col in ((entry, YELLOW), (stop_loss, SLC), (take_profit, TPC)):
        if val is not None:
            y = Y(val)
            for x in range(L, R):
                if (x // 8) % 2 == 0:
                    px(x, y, col)
                    px(x, y + 1, col)
    return _png(rows, W, H)
