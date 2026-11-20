"""Actualites par crypto (et l'or) : GDELT (sans cle) + CryptoPanic (cle facultative).
Classification par mots-cles sur le TITRE (approximative, rien n'est invente) ; chaque element garde
titre, source, URL, date de publication, fiabilite, importance. Doublons et anciennes news ecartes."""
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import requests

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
NEWSAPI_URL = "https://newsapi.org/v2/everything"

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


NEWSAPI_Q = {"XRP": "ripple OR XRP", "BNB": '"Binance Coin" OR BNB', "TRX": "tron OR TRX", "AVAX": "avalanche AND crypto",
             "OP": '"Optimism" AND crypto', "UNI": "uniswap", "SUI": '"Sui" AND crypto', "TON": "toncoin OR \"The Open Network\"",
             "XAUT": '"gold price" OR "Tether Gold"', "XAU": '"gold price"'}


def newsapi_query(symbol):
    base = symbol.split("_")[0]
    if base in NEWSAPI_Q:
        return NEWSAPI_Q[base]
    term = QUERIES.get(base, f"{base} crypto")
    return f'"{term}"' if " " in term else term


class Budget:
    """Compteur quotidien de requetes (le plan gratuit NewsAPI est limite) : on s'arrete AVANT la limite."""

    def __init__(self, limit):
        self.limit, self.day, self.n = int(limit), None, 0

    def allow(self, today=None):
        today = today or datetime.now(timezone.utc).date()
        if today != self.day:
            self.day, self.n = today, 0
        return self.n < self.limit

    def used(self):
        self.n += 1


def fetch_newsapi(symbol, key, session=None, max_age_hours=48, page_size=15, timeout=20, now=None):
    """NewsAPI (/v2/everything). Source = domaine de l'URL (pour juger la fiabilite). Erreurs -> NewsError."""
    if not key:
        return []
    now = now or datetime.now(timezone.utc)
    params = {"q": newsapi_query(symbol), "language": "en", "sortBy": "publishedAt", "pageSize": page_size,
              "from": (now - timedelta(hours=max_age_hours)).strftime("%Y-%m-%dT%H:%M:%S")}
    try:
        r = (session or requests).get(NEWSAPI_URL, params=params, headers={"X-Api-Key": key}, timeout=timeout)
    except requests.RequestException as e:
        raise NewsError(f"NewsAPI indisponible : {e}") from e
    try:
        data = r.json()
    except ValueError as e:
        raise NewsError(f"NewsAPI HTTP {r.status_code} sans JSON") from e
    if r.status_code != 200 or data.get("status") != "ok":
        raise NewsError(f"NewsAPI refuse ({r.status_code}) : {data.get('code', '')} {str(data.get('message', ''))[:120]}")
    out = []
    for a in data.get("articles", []):
        try:
            title, url = (a["title"] or "").strip(), a["url"]
            pub = datetime.fromisoformat(a["publishedAt"].replace("Z", "+00:00"))
            if not title or title == "[Removed]":
                continue
            out.append({"title": title, "url": url, "source": urlsplit(url).netloc.lower(),
                        "published_at": pub if pub.tzinfo else pub.replace(tzinfo=timezone.utc), "provider": "newsapi"})
        except (KeyError, ValueError, AttributeError):
            continue
    return out


NEWSDATA_BASE = "https://newsdata.io/api/1"


def fetch_newsdata(symbol, key, session=None, timeout=20, now=None):
    """NewsData.io : endpoint /crypto (filtre coin) ; pour l'or, /latest avec recherche 'gold price'.
    Plan gratuit : peu de resultats par requete et articles retardes. Erreurs -> NewsError."""
    if not key:
        return []
    base = symbol.split("_")[0]
    if is_gold(symbol):
        url, params = f"{NEWSDATA_BASE}/latest", {"apikey": key, "q": '"gold price"', "language": "en"}
    else:
        url, params = f"{NEWSDATA_BASE}/crypto", {"apikey": key, "coin": base.lower(), "language": "en"}
    try:
        r = (session or requests).get(url, params=params, timeout=timeout)
    except requests.RequestException as e:
        raise NewsError(f"NewsData indisponible : {e}") from e
    try:
        data = r.json()
    except ValueError as e:
        raise NewsError(f"NewsData HTTP {r.status_code} sans JSON") from e
    if r.status_code != 200 or data.get("status") != "success":
        res = data.get("results")
        msg = res.get("message", "") if isinstance(res, dict) else ""
        raise NewsError(f"NewsData refuse ({r.status_code}) : {str(msg)[:120]}")
    out = []
    for a in data.get("results") or []:
        try:
            title, link = (a["title"] or "").strip(), a["link"]
            pub = datetime.strptime(a["pubDate"][:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)  # UTC
            if title:
                out.append({"title": title, "url": link, "source": urlsplit(link).netloc.lower(),
                            "published_at": pub, "provider": "newsdata"})
        except (KeyError, ValueError, TypeError):
            continue
    return out
