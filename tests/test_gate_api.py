from unittest import TestCase
from unittest.mock import MagicMock

import requests

from apps.market_data.gate_client import GateAPIError, GateClient


class GateClientTests(TestCase):
    def _client(self, status=200, payload=None, exc=None):
        s = MagicMock()
        if exc:
            s.get.side_effect = exc
        else:
            resp = MagicMock(status_code=status, text="x")
            resp.json.return_value = payload
            s.get.return_value = resp
        return GateClient(session=s), s

    def test_ok(self):
        c, s = self._client(payload=[{"name": "BTC_USDT"}])
        self.assertEqual(c.contracts(), [{"name": "BTC_USDT"}])
        self.assertIn("/futures/usdt/contracts", s.get.call_args[0][0])

    def test_http_error_raises(self):
        c, _ = self._client(status=500)
        with self.assertRaises(GateAPIError):
            c.tickers()

    def test_network_error_raises(self):
        c, _ = self._client(exc=requests.ConnectionError("down"))
        with self.assertRaises(GateAPIError):
            c.tickers()
