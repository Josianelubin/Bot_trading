"""Vrais logos des cryptos : CoinGecko (image officielle de chaque coin) puis 2 sources de secours.
Module PUR (sans Django) : les logos sont telecharges cote serveur, valides (type image, taille, hote autorise)
puis stockes en base (voir logo_store.py). Rien n'est invente : pas de logo trouve = pas d'image."""
import re
import time
from urllib.parse import urlsplit

import requests

ALLOWED_TYPES = ("image/png", "image/jpeg", "image/webp")
MAX_BYTES = 300_000
ALLOWED_HOSTS = ("coingecko.com", "cdn.jsdelivr.net", "assets.coincap.io")
_cg = {"t": 0.0, "map": {}}


class LogoError(Exception):
    pass


def clean_base(symbol):
    """BTC_USDT -> BTC ; 1000PEPE_USDT -> PEPE. Retourne None si invalide."""
    b = (symbol or "").upper().split("_")[0]
    b = re.sub(r"^(1000000|100000|10000|1000|1M)(?=[A-Z])", "", b)
    return b if re.fullmatch(r"[A-Z0-9]{1,15}", b) else None


def _host_ok(url):
    try:
        u = urlsplit(url)
    except ValueError:
        return False
    return u.scheme == "https" and any(u.hostname == h or (u.hostname or "").endswith("." + h) for h in ALLOWED_HOSTS)


def coingecko_map(session=None, pages=3, api_key="", force=False):
    """symbole (MAJUSCULES) -> URL d'image, pour les plus grosses capitalisations (le 1er gagne). Cache 24 h."""
    if _cg["map"] and not force and time.time() - _cg["t"] < 86400:
        return _cg["map"]
    out = {}
    headers = {"User-Agent": "KPS/1.0", **({"x-cg-demo-api-key": api_key} if api_key else {})}
    for page in range(1, pages + 1):
        try:
            r = (session or requests).get("https://api.coingecko.com/api/v3/coins/markets", headers=headers, timeout=20,
                                          params={"vs_currency": "usd", "order": "market_cap_desc", "per_page": 250, "page": page})
            if r.status_code != 200:
                break
            for coin in r.json():
                sym, img = str(coin.get("symbol", "")).upper(), coin.get("image")
                if sym and img and sym not in out:
                    out[sym] = img
        except (requests.RequestException, ValueError, AttributeError):
            break
    if out:
        _cg.update(t=time.time(), map=out)
    return out or _cg["map"]


def candidates(base, cg):
    urls = []
    if base in cg:
        u = cg[base]
        urls.append(u.replace("/large/", "/small/") if "/large/" in u else u)  # 64 px : leger
    low = base.lower()
    urls.append(f"https://cdn.jsdelivr.net/gh/spothq/cryptocurrency-icons@master/128/color/{low}.png")
    urls.append(f"https://assets.coincap.io/assets/icons/{low}@2x.png")
    return urls


def download(url, session=None):
    if not _host_ok(url):
        return None
    try:
        r = (session or requests).get(url, timeout=10, headers={"User-Agent": "KPS/1.0"})
    except requests.RequestException:
        return None
    ctype = (getattr(r, "headers", {}) or {}).get("Content-Type", "").split(";")[0].strip().lower()
    body = getattr(r, "content", b"")
    if r.status_code != 200 or ctype not in ALLOWED_TYPES or not body or len(body) > MAX_BYTES:
        return None
    return body, ctype


def fetch_logo(symbol, session=None, api_key=""):
    """Retourne (octets, type, url_source) ou None si aucune source n'a de logo pour ce symbole."""
    base = clean_base(symbol)
    if not base:
        return None
    for url in candidates(base, coingecko_map(session, api_key=api_key)):
        got = download(url, session)
        if got:
            return got[0], got[1], url
    return None
