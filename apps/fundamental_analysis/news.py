"""Actualites par crypto (et l'or) : GDELT (sans cle) + CryptoPanic (cle facultative).
Classification par mots-cles sur le TITRE (approximative, rien n'est invente) ; chaque element garde
titre, source, URL, date de publication, fiabilite, importance. Doublons et anciennes news ecartes."""
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import requests

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

QUERIES = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "XRP": "ripple XRP", "BNB": "binance BNB",
    "DOGE": "dogecoin", "ADA": "cardano", "AVAX": "avalanche crypto", "LINK": "chainlink", "LTC": "litecoin",
    "DOT": "polkadot", "TRX": "tron TRX", "BCH": "bitcoin cash", "SUI": "sui blockchain", "APT": "aptos",
    "NEAR": "near protocol", "TON": "toncoin", "UNI": "uniswap", "OP": "optimism crypto", "ARB": "arbitrum",
    "XAUT": "gold price", "XAU": "gold price",
}
GOLD = {"XAUT", "XAU"}

POS = ["approv", "etf", "partnership", "adoption", "upgrade", "launch", "surge", "rally", "record high",
       "integrat", "listing", "bullish", "institutional", "inflow", "soar", "gain", "rate cut", "safe haven",
       "safe-haven", "accumulat", "breakout"]
NEG = ["hack", "exploit", "stolen", "lawsuit", "sues", "banned", "ban ", "crackdown", "fraud", "collapse",
       "delist", "bankrupt", "plunge", "crash", "reject", "investigation", "charges", "outage", "liquidat",
       "bearish", "outflow", "selloff", "sell-off", "rate hike", "strong dollar", "slump", "tumble", "scam"]
BIG = ["hack", "exploit", "stolen", "etf", "sec ", "ban", "bankrupt", "collapse", "fed ", "federal reserve",
       "delist", "crackdown", "lawsuit", "rate cut", "rate hike", "approv", "record high"]

HIGH_SRC = {"reuters.com", "bloomberg.com", "coindesk.com", "cointelegraph.com", "theblock.co", "apnews.com",
            "wsj.com", "ft.com", "cnbc.com", "federalreserve.gov", "sec.gov", "bls.gov", "bea.gov", "decrypt.co"}


class NewsError(Exception):
    pass


def query_for(symbol):
    base = symbol.split("_")[0]
    return QUERIES.get(base, f"{base} crypto")


def is_gold(symbol):
    return symbol.split("_")[0] in GOLD


def reliability(domain):
    d = (domain or "").lower().removeprefix("www.")
    if d in HIGH_SRC or any(d.endswith("." + h) for h in HIGH_SRC):
        return "haute"
    return "moyenne" if d else "faible"


def classify(title):
    t = " " + title.lower() + " "
    pos = sum(1 for w in POS if w in t)
    neg = sum(1 for w in NEG if w in t)
    sentiment = "positif" if pos > neg else "negatif" if neg > pos else "neutre"
    big = sum(1 for w in BIG if w in t)
    importance = 3 if big >= 2 or (big == 1 and sentiment != "neutre") else 2 if big == 1 else 1
    return sentiment, importance


def _norm(url):
    u = urlsplit(url or "")
    return f"{u.netloc.lower()}{u.path}".rstrip("/")


def fetch_gdelt(symbol, session=None, timespan="2d", maxrecords=15, timeout=20):
    params = {"query": f"{query_for(symbol)} sourcelang:english", "mode": "artlist", "format": "json",
              "maxrecords": maxrecords, "sort": "datedesc", "timespan": timespan}
    try:
        r = (session or requests).get(GDELT_URL, params=params, timeout=timeout)
    except requests.RequestException as e:
        raise NewsError(f"GDELT indisponible : {e}") from e
    if r.status_code != 200:
        raise NewsError(f"GDELT HTTP {r.status_code}")
    try:
        data = r.json()
    except ValueError as e:
        raise NewsError("GDELT n'a pas renvoye de JSON") from e
    out = []
    for a in data.get("articles", []):
        try:
            pub = datetime.strptime(a["seendate"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            out.append({"title": a["title"].strip(), "url": a["url"], "source": a.get("domain", ""),
                        "published_at": pub, "provider": "gdelt"})
        except (KeyError, ValueError):
            continue
    return out


def fetch_cryptopanic(symbol, token, plan="developer", session=None, timeout=20):
    """Facultatif (cle gratuite). Champs lus de facon defensive : format a verifier dans la doc."""
    if not token or is_gold(symbol):
        return []
    url = f"https://cryptopanic.com/api/{plan}/v2/posts/"
    try:
        r = (session or requests).get(url, params={"auth_token": token, "currencies": symbol.split("_")[0],
                                                   "public": "true"}, timeout=timeout)
    except requests.RequestException as e:
        raise NewsError(f"CryptoPanic indisponible : {e}") from e
    if r.status_code != 200:
        raise NewsError(f"CryptoPanic HTTP {r.status_code}")
    out = []
    try:
        for it in r.json().get("results", []):
            pub = datetime.fromisoformat(str(it["published_at"]).replace("Z", "+00:00"))
            src = it.get("source") or {}
            link = it.get("original_url") or it.get("url")
            if link and it.get("title"):
                out.append({"title": it["title"].strip(), "url": link, "provider": "cryptopanic",
                            "source": src.get("domain") or src.get("title") or "cryptopanic.com",
                            "published_at": pub if pub.tzinfo else pub.replace(tzinfo=timezone.utc)})
    except (ValueError, KeyError, AttributeError) as e:
        raise NewsError("Reponse CryptoPanic inattendue") from e
    return out


def prepare(items, now=None, max_age_hours=48):
    """Dedoublonne, retire les news anciennes ou datees du futur, classe et trie (recent d'abord)."""
    now = now or datetime.now(timezone.utc)
    seen, out = set(), []
    for it in sorted(items, key=lambda x: x["published_at"], reverse=True):
        age = now - it["published_at"]
        if age > timedelta(hours=max_age_hours) or age < timedelta(hours=-1):
            continue
        key, tkey = _norm(it["url"]), re.sub(r"\W+", "", it["title"].lower())[:80]
        if key in seen or tkey in seen:
            continue
        seen.update({key, tkey})
        s, imp = classify(it["title"])
        out.append({**it, "sentiment": s, "importance": imp, "reliability": reliability(it.get("source"))})
    return out
