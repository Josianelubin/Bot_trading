from unittest import TestCase

from apps.market_scanner.scan import scan
from apps.technical_analysis import indicators as ind
from tests.test_pipeline import breakout
from tests.test_strategies import candle, flat


class IndicatorExtraTests(TestCase):
    def test_macd_constant_is_zero(self):
        m = ind.macd([10.0] * 60)
        self.assertAlmostEqual(m["hist"][-1], 0.0)
        self.assertIsNone(m["macd"][0])

    def test_macd_positive_in_uptrend(self):
        self.assertGreater(ind.macd([100 + i for i in range(80)])["hist"][-1] + ind.macd([100 + i for i in range(80)])["macd"][-1], 0)

    def test_vwap_equals_price_when_flat(self):
        c = [candle(100, spread=0.0) for _ in range(10)]
        self.assertAlmostEqual(ind.vwap(c)[-1], 100.0)

    def test_vwap_resets_each_day(self):
        c = [{"o": 1, "h": 1, "l": 1, "c": 1, "v": 1, "t": 0}, {"o": 5, "h": 5, "l": 5, "c": 5, "v": 1, "t": 86400}]
        self.assertAlmostEqual(ind.vwap(c)[-1], 5.0)

    def test_fib_levels(self):
        c = [candle(100 + i) for i in range(50)]  # mouvement haussier
        f = ind.fib_levels(c)
        self.assertEqual(f["trend"], "up")
        self.assertLess(f["levels"][0.618], f["levels"][0.236])

    def test_normalize_keeps_time(self):
        out = ind.normalize_candles([{"o": "1", "h": "2", "l": "0.5", "c": "1.5", "v": "10", "t": 1700000000}])
        self.assertEqual(out[0]["t"], 1700000000)


class ScanTests(TestCase):
    def test_signal_with_levels(self):
        r = scan(breakout()[:-1], "BTC_USDT", "15m", {"min_score": 1})
        self.assertEqual(r["status"], "signal")
        self.assertEqual(r["direction"], "LONG")
        self.assertLess(r["stop_loss"], r["entry"])
        tp = r["take_profits"]
        self.assertTrue(r["entry"] < tp[0] < tp[1] < tp[2])
        self.assertIn("T", r["timestamp"])
        self.assertEqual(r["market"], "Gate Futures USDT")
        self.assertTrue(r["confirmations"])

    def test_attente_when_flat(self):
        r = scan(flat(100), "BTC_USDT", "1h")
        self.assertEqual((r["status"], r["direction"]), ("ATTENTE", "ATTENTE"))
        self.assertNotIn("entry", r)

    def test_attente_when_score_too_low(self):
        r = scan(breakout()[:-1], "BTC_USDT", "15m", {"min_score": 40})
        self.assertEqual(r["direction"], "ATTENTE")

    def test_unavailable_when_few_candles(self):
        r = scan(flat(10), "BTC_USDT", "15m")
        self.assertEqual(r["status"], "indisponible")
        self.assertIn("DONNEES INDISPONIBLES", r["message"])

    def test_short_levels_descend(self):
        down = flat(90) + [candle(97), candle(93), candle(88, v=400), candle(87)]
        r = scan(down[:-1], "BTC_USDT", "15m", {"min_score": 1})
        self.assertEqual((r["status"], r["direction"]), ("signal", "SHORT"))
        self.assertTrue(r["entry"] > r["take_profits"][0] > r["take_profits"][1] > r["take_profits"][2])
        self.assertGreater(r["stop_loss"], r["entry"])


class StochAndPerfTests(TestCase):
    def test_stoch_rsi_range_and_alignment(self):
        closes = [100 + ((i * 7) % 11) - 5 + i * 0.1 for i in range(80)]
        s = ind.stoch_rsi(closes)
        self.assertEqual(len(s["k"]), 80)
        vals = [x for x in s["k"] + s["d"] if x is not None]
        self.assertTrue(vals)
        self.assertTrue(all(0 <= x <= 100 for x in vals))
        self.assertIsNone(s["k"][10])

    def test_performance_curve(self):
        from apps.market_scanner.perf import performance
        r = performance([(100, 10.0), (100, -4.0), (200, 6.0)])
        self.assertEqual((r["n"], r["wins"], r["losses"]), (3, 2, 1))
        self.assertEqual(r["pnl"], 12.0)
        self.assertEqual([p["value"] for p in r["points"]], [10.0, 6.0, 12.0])
        self.assertTrue(r["points"][0]["time"] < r["points"][1]["time"] < r["points"][2]["time"])
        self.assertEqual(r["rate"], 66.7)

    def test_performance_empty(self):
        from apps.market_scanner.perf import performance
        self.assertIsNone(performance([])["rate"])
