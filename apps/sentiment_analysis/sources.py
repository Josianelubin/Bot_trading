"""Sources de sentiment : Fear & Greed (alternative.me, sans cle) et statistiques futures de Gate (contract_stats)."""
import requests

FNG_URL = "https://api.alternative.me/fng/"


class SentimentError(Exception):
    pass


def fetch_fear_greed(session=None, timeout=15):
    try:
        r = (session or requests).get(FNG_URL, params={"limit": 1}, timeout=timeout)
        item = r.json()["data"][0]
        if r.status_code != 200:
            raise SentimentError(f"Fear & Greed HTTP {r.status_code}")
        return {"value": int(item["value"]), "label": item.get("value_classification", "")}
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as e:
        raise SentimentError(f"Fear & Greed indisponible : {e}") from e
