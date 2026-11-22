"""Client Gate.io V4 en LECTURE SEULE (endpoints publics, aucune cle requise).

Aucun ordre n'est envoye ici. Les erreurs reseau ou de format levent GateAPIError :
on n'invente jamais de donnees.
"""
import requests

BASE_URL = "https://api.gateio.ws/api/v4"
SETTLE = "usdt"


class GateAPIError(Exception):
    pass


class GateClient:
    def __init__(self, base_url=BASE_URL, timeout=10, session=None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()

    def _get(self, path, params=None):
        url = f"{self.base_url}{path}"
        try:
            r = self.session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as e:
            raise GateAPIError(f"Reseau indisponible : {e}") from e
        if r.status_code != 200:
            raise GateAPIError(f"HTTP {r.status_code} sur {path} : {r.text[:200]}")
        try:
            return r.json()
        except ValueError as e:
            raise GateAPIError(f"Reponse non JSON sur {path}") from e

    def contracts(self):
        return self._get(f"/futures/{SETTLE}/contracts")

    def tickers(self):
        return self._get(f"/futures/{SETTLE}/tickers")

    def candlesticks(self, contract, interval="15m", limit=200):
        return self._get(
            f"/futures/{SETTLE}/candlesticks",
            {"contract": contract, "interval": interval, "limit": limit},
        )

    def contract_stats(self, contract, interval="1h", limit=24):
        """Statistiques futures : open interest, ratio long/short, liquidations (endpoint public)."""
        return self._get(f"/futures/{SETTLE}/contract_stats", {"contract": contract, "interval": interval, "limit": limit})

    def ticker(self, contract):
        r = self._get(f"/futures/{SETTLE}/tickers", {"contract": contract})
        if not r:
            raise GateAPIError("Ticker indisponible")
        return r[0]
