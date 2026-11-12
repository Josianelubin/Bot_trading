import hashlib
import hmac
from unittest import TestCase

from apps.trading.executor import execute
from apps.trading.gate_private import GateTradeError, sign_headers
from apps.trading.sizing import contracts_for, round_price


class SignTests(TestCase):
    def test_signature_matches_documented_scheme(self):
        h = sign_headers("K", "S", "POST", "/api/v4/futures/usdt/orders", "a=1", '{"x":1}', ts=1700000000)
        body_hash = hashlib.sha512(b'{"x":1}').hexdigest()
        expected = hmac.new(b"S", f"POST\n/api/v4/futures/usdt/orders\na=1\n{body_hash}\n1700000000".encode(),
                            hashlib.sha512).hexdigest()
        self.assertEqual(h["SIGN"], expected)
        self.assertEqual((h["KEY"], h["Timestamp"]), ("K", "1700000000"))

    def test_empty_body_hash(self):
        h = sign_headers("K", "S", "GET", "/api/v4/x", "", "", ts=1)
        e = hmac.new(b"S", f"GET\n/api/v4/x\n\n{hashlib.sha512(b'').hexdigest()}\n1".encode(), hashlib.sha512).hexdigest()
        self.assertEqual(h["SIGN"], e)


class SizingTests(TestCase):
    def test_contracts(self):
        self.assertEqual(contracts_for(20, 5, 100.0, "0.01", 1), 100)  # 100 USDT / (100*0.01)

    def test_too_small(self):
        with self.assertRaises(ValueError):
            contracts_for(1, 1, 50000, "0.0001", 1)

    def test_round_price(self):
        self.assertEqual(round_price(100.123456, "0.01"), "100.12")
        self.assertEqual(round_price(0.123456, "0.0001"), "0.1235")


class FakeTrader:
    def __init__(self, **o):
        self.o, self.calls = o, []

    def _c(self, name, *a):
        self.calls.append(name)
        if name in self.o.get("raise_on", ()):
            raise GateTradeError(f"{name} refuse")

    def balance(self):
        self._c("balance"); return {"available": self.o.get("avail", "500"), "total": "1000"}

    def ticker(self, c):
        self._c("ticker"); return {"last": self.o.get("last", "100")}

    def contract(self, c):
        self._c("contract"); return {"quanto_multiplier": "0.01", "order_size_min": 1, "leverage_max": "50",
                                     "order_price_round": "0.01", "status": "trading"}

    def set_isolated_leverage(self, c, lev):
        self._c("leverage"); return {"leverage": str(self.o.get("lev_back", lev))}

    def market_order(self, c, size, text):
        self._c("market"); self.size, self.text = size, text; return {"id": 11}

    def get_order(self, i):
        self._c("get_order"); return {"status": "finished", "finish_as": self.o.get("finish", "filled"), "fill_price": "100.05"}

    def price_order(self, c, price, rule):
        self._c("price_order"); self.last_rule = rule; return {"id": 20 + len(self.calls)}

    def close_position(self, c):
        self._c("close"); return {}


P = {"id": 5, "symbol": "BTC_USDT", "direction": "LONG", "entry": 100.0, "stop_loss": 99.0,
     "take_profit": 102.0, "leverage": 5, "capital_usdt": 20.0}


class ExecutorTests(TestCase):
    def test_success_order_of_steps(self):
        t = FakeTrader()
        r = execute(t, P)
        self.assertTrue(r["ok"])
        self.assertEqual(t.calls.index("leverage") < t.calls.index("market"), True)  # isolee AVANT l'ordre
        self.assertEqual(t.calls.count("price_order"), 2)
        self.assertEqual(t.size, 100)
        self.assertEqual(t.text, "t-kps5")
        self.assertEqual(r["fill_price"], 100.05)

    def test_short_size_negative(self):
        t = FakeTrader(last="100")
        r = execute(t, {**P, "direction": "SHORT", "stop_loss": 101.0, "take_profit": 98.0})
        self.assertTrue(r["ok"])
        self.assertLess(t.size, 0)

    def test_slippage_blocks_before_any_order(self):
        t = FakeTrader(last="101")
        r = execute(t, P)
        self.assertFalse(r["ok"])
        self.assertNotIn("market", t.calls)

    def test_isolated_not_confirmed_blocks(self):
        t = FakeTrader(lev_back=0)
        r = execute(t, P)
        self.assertFalse(r["ok"])
        self.assertNotIn("market", t.calls)

    def test_insufficient_balance(self):
        t = FakeTrader(avail="5")
        self.assertFalse(execute(t, P)["ok"])
        self.assertNotIn("market", t.calls)

    def test_risk_rules_block(self):
        t = FakeTrader()
        r = execute(t, {**P, "stop_loss": None})
        self.assertFalse(r["ok"])
        self.assertNotIn("market", t.calls)

    def test_not_filled_triggers_safety_close(self):
        t = FakeTrader(finish="cancelled")
        r = execute(t, P)
        self.assertFalse(r["ok"])
        self.assertIn("close", t.calls)

    def test_sl_failure_closes_position(self):
        t = FakeTrader(raise_on=("price_order",))
        r = execute(t, P)
        self.assertFalse(r["ok"])
        self.assertTrue(r.get("emergency_closed"))
        self.assertIn("close", t.calls)

    def test_sl_and_close_failure_is_critical(self):
        t = FakeTrader(raise_on=("price_order", "close"))
        r = execute(t, P)
        self.assertTrue(r.get("critical"))

    def test_api_error_never_claims_success(self):
        r = execute(FakeTrader(raise_on=("market",)), P)
        self.assertFalse(r["ok"])
