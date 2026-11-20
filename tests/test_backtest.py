from unittest import TestCase

from apps.market_scanner.backtest import run
from apps.market_scanner.scan import potential
from tests.test_ict_setup import FLAT, LONG_PATH, build
from tests.test_strategies import flat


class BacktestTests(TestCase):
    def test_no_signals_on_flat_market(self):
        r = run(flat(400), "BTC_USDT", "15m")
        self.assertEqual(r["trades"], 0)
        self.assertIsNone(r["rate_tp1"])
        self.assertFalse(r["reliable"])
        self.assertIn("insuffisant", r["warning"])

    def test_winning_trade_is_counted(self):
        # historique plat, puis setup haussier dans la zone OTE, puis le prix monte jusqu'aux objectifs
        path = [100 + (0.2 if i % 2 else 0.0) for i in range(120)] + LONG_PATH[1:]
        c = build([100] + path[1:])
        up = [98.5, 100, 102, 105, 108, 111, 114, 117, 120]
        c += build([98.5] + up[1:])
        r = run(c, "BTC_USDT", "15m", warmup=100, step=1)
        self.assertGreaterEqual(r["signals"], 1)
        self.assertGreaterEqual(r["wins_tp1"], 1)

    def test_losing_trade_is_counted(self):
        path = [100 + (0.2 if i % 2 else 0.0) for i in range(120)] + LONG_PATH[1:]
        c = build([100] + path[1:])
        down = [98.5, 96, 93, 90, 88]
        c += build([98.5] + down[1:])
        r = run(c, "BTC_USDT", "15m", warmup=100, step=1)
        self.assertGreaterEqual(r["losses"], 1)  # le grand setup echoue ; d'autres micro-setups peuvent gagner
        self.assertEqual(r["wins_tp1"] + r["losses"], r["trades"])


class PotentialTests(TestCase):
    def test_long_potential(self):
        p = potential("LONG", 100.0, 98.0, [102.0, 104.0, 106.0], 10, 50)
        self.assertAlmostEqual(p["targets"][0]["gain_price_pct"], 2.0)
        self.assertAlmostEqual(p["targets"][0]["gain_margin_pct"], 20.0)
        self.assertAlmostEqual(p["targets"][0]["gain_usdt"], 10.0)
        self.assertAlmostEqual(p["targets"][0]["reward_risk"], 1.0)
        self.assertAlmostEqual(p["loss_margin_pct"], -20.0)
        self.assertAlmostEqual(p["loss_usdt"], -10.0)
        self.assertFalse(p["stop_beyond_liquidation"])

    def test_short_and_liquidation_warning(self):
        p = potential("SHORT", 100.0, 108.0, [96.0, 92.0, 88.0], 20, 10)
        self.assertGreater(p["targets"][0]["gain_price_pct"], 0)
        self.assertLess(p["loss_price_pct"], 0)
        self.assertTrue(p["stop_beyond_liquidation"])  # stop a 8 % avec levier x20 (liquidation ~5 %)
