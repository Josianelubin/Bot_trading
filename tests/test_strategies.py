from unittest import TestCase

from apps.technical_analysis import indicators as ind, strategies as st
from apps.technical_analysis.engine import analyze_all


def candle(c, spread=0.5, v=100.0, o=None):
    return {"o": c if o is None else o, "h": c + spread, "l": c - spread, "c": c, "v": v}


def flat(n, base=100.0):
    return [candle(base + ((i * 7) % 5 - 2) * 0.1) for i in range(n)]


class IndicatorTests(TestCase):
    def test_rsi_all_up_is_100(self):
        self.assertEqual(ind.rsi(list(range(1, 40)))[-1], 100.0)

    def test_rsi_all_down_is_0(self):
        self.assertAlmostEqual(ind.rsi(list(range(40, 1, -1)))[-1], 0.0)

    def test_atr_constant_range(self):
        c = [candle(100, spread=1.0) for _ in range(30)]
        self.assertAlmostEqual(ind.atr(c)[-1], 2.0)

    def test_adx_strong_trend_high(self):
        c = [candle(100 + i * 2, spread=0.5) for i in range(80)]
        a = ind.adx(c)
        self.assertGreater(a["adx"][-1], 40)
        self.assertGreater(a["plus_di"][-1], a["minus_di"][-1])

    def test_ema_constant(self):
        self.assertAlmostEqual(ind.ema([5.0] * 30, 9)[-1], 5.0)


class StrategyTests(TestCase):
    def test_turtle_long_breakout(self):
        c = flat(70) + [candle(110, spread=0.5)]
        r = st.turtle(c)
        self.assertEqual(r["direction"], "LONG")
        self.assertEqual(r["score"], 10)

    def test_turtle_short_breakout(self):
        c = flat(70) + [candle(90)]
        self.assertEqual(st.turtle(c)["direction"], "SHORT")

    def test_turtle_no_data(self):
        self.assertIn("DONNEES INDISPONIBLES", st.turtle(flat(10))["reasons"][0])

    def test_dow_uptrend(self):
        pts = [100, 104, 101, 106, 102, 108, 104, 110, 106, 112, 108, 114, 110]
        c = []
        for i, p in enumerate(pts):
            for k in range(4):
                c.append(candle(p + (k - 2) * 0.3, o=p + (k - 2) * 0.3 - 0.2, v=150))
        c2 = []
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            for k in range(5):
                x = a + (b - a) * k / 5
                c2.append(candle(x, o=x - 0.1 if b > a else x + 0.1, v=150 if b > a else 80))
        self.assertEqual(st.dow(c2)["direction"], "LONG")

    def test_livermore_breakout_with_volume(self):
        c = [candle(100 + (i % 3) * 0.5, v=100) for i in range(40)]
        c += [candle(101, v=100), candle(101.5, v=100), candle(104, spread=0.3, v=400)]
        r = st.livermore(c)
        self.assertEqual(r["direction"], "LONG")
        self.assertEqual(r["score"], 7)

    def test_livermore_breakout_without_volume_reduced(self):
        c = [candle(100 + (i % 3) * 0.5, v=100) for i in range(40)]
        c += [candle(101, v=100), candle(101.5, v=100), candle(104, spread=0.3, v=100)]
        self.assertEqual(st.livermore(c)["score"], 3)

    def test_wilder_no_trend_neutral(self):
        self.assertEqual(st.wilder(flat(80))["direction"], "NEUTRE")


class EngineTests(TestCase):
    def test_insufficient_data(self):
        r = analyze_all(flat(10))
        self.assertEqual(r["direction"], "NEUTRE")
        self.assertIn("DONNEES INDISPONIBLES", r["reasons"][0])

    def test_breakout_gives_long_with_stop(self):
        c = flat(90) + [candle(103), candle(107), candle(112, v=400)]
        r = analyze_all(c)
        self.assertEqual(r["direction"], "LONG")
        self.assertGreater(r["score"], 0)
        self.assertLessEqual(r["score"], 40)
        self.assertLess(r["suggested"]["stop_loss"], r["suggested"]["entry"])
        self.assertIn("turtle", r["tools"])

    def test_flat_market_is_neutral(self):
        self.assertEqual(analyze_all(flat(100))["direction"], "NEUTRE")
