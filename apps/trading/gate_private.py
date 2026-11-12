"""Client Gate.io V4 AUTHENTIFIE (futures USDT). Signature verifiee :
SIGN = hex(HMAC-SHA512(secret, METHOD\\n/api/v4/chemin\\nquery\\nhex(SHA512(body))\\ntimestamp)).
Marge isolee : l'endpoint de levier avec leverage > 0 = ISOLEE (0 = croisee)."""
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode, urlparse

import requests


class GateTradeError(Exception):
    pass


def sign_headers(key, secret, method, full_path, query="", body="", ts=None):
    ts = str(int(time.time())) if ts is None else str(ts)
    hashed = hashlib.sha512((body or "").encode()).hexdigest()
    s = f"{method}\n{full_path}\n{query or ''}\n{hashed}\n{ts}"
    sig = hmac.new(secret.encode(), s.encode(), hashlib.sha512).hexdigest()
    return {"KEY": key, "Timestamp": ts, "SIGN": sig}


class GateTrader:
    def __init__(self, key, secret, base_url="https://api.gateio.ws/api/v4", settle="usdt", session=None, timeout=15):
        self.key, self.secret = key, secret
        self.base_url, self.settle = base_url.rstrip("/"), settle
        self.prefix = urlparse(self.base_url).path
        self.session, self.timeout = session or requests.Session(), timeout

    def _req(self, method, path, params=None, body=None):
        query = urlencode(params or {})
        payload = json.dumps(body, separators=(",", ":")) if body is not None else ""
        headers = {"Accept": "application/json", "Content-Type": "application/json",
                   **sign_headers(self.key, self.secret, method, self.prefix + path, query, payload)}
        url = self.base_url + path + (f"?{query}" if query else "")
        try:
            r = self.session.request(method, url, data=payload or None, headers=headers, timeout=self.timeout)
        except requests.RequestException as e:
            raise GateTradeError(f"Reseau indisponible : {e}") from e
        if not 200 <= r.status_code < 300:
            raise GateTradeError(f"Gate a refuse {method} {path} (HTTP {r.status_code}) : {r.text[:300]}")
        try:
            return r.json()
        except ValueError as e:
            raise GateTradeError(f"Reponse non JSON sur {path}") from e

    def _f(self, p):
        return f"/futures/{self.settle}{p}"

    def contract(self, c):
        return self._req("GET", self._f(f"/contracts/{c}"))

    def ticker(self, c):
        r = self._req("GET", self._f("/tickers"), {"contract": c})
        if not r:
            raise GateTradeError("Ticker indisponible")
        return r[0]

    def balance(self):
        return self._req("GET", self._f("/accounts"))

    def set_isolated_leverage(self, c, leverage):
        return self._req("POST", self._f(f"/positions/{c}/leverage"), {"leverage": str(int(leverage))})

    def position(self, c):
        return self._req("GET", self._f(f"/positions/{c}"))

    def market_order(self, c, size, text):
        return self._req("POST", self._f("/orders"),
                         body={"contract": c, "size": int(size), "price": "0", "tif": "ioc", "text": text})

    def get_order(self, order_id):
        return self._req("GET", self._f(f"/orders/{order_id}"))

    def close_position(self, c):
        return self._req("POST", self._f("/orders"),
                         body={"contract": c, "size": 0, "price": "0", "close": True, "tif": "ioc"})

    def price_order(self, c, trigger_price, rule):
        """rule 1 : declenche quand prix >= trigger ; rule 2 : prix <= trigger. Ferme la position."""
        return self._req("POST", self._f("/price_orders"), body={
            "initial": {"contract": c, "size": 0, "price": "0", "close": True, "tif": "ioc"},
            "trigger": {"strategy_type": 0, "price_type": 0, "price": str(trigger_price),
                        "rule": int(rule), "expiration": 2592000}})

    def cancel_price_order(self, order_id):
        return self._req("DELETE", self._f(f"/price_orders/{order_id}"))

    def position_close_history(self, c, limit=10):
        return self._req("GET", self._f("/position_close"), {"contract": c, "limit": limit})
