import struct
import zlib
from unittest import TestCase

from apps.technical_analysis import divergence, wyckoff
from apps.trade_history.chart import render_png
from apps.trading.pipeline import build_proposal
from tests.test_strategies import candle, flat
from tests.test_wyckoff_elliott import downtrend, mk, path, range_bars


def breakout():
    return flat(90) + [candle(103), candle(107), candle(112, v=400), candle(113)]


class DivergenceTests(TestCase):
    def test_bullish_divergence(self):
        c = path([100] * 21 + [100, 90, 96, 89.5, 93])
        r = divergence.analyze(c)
        self.assertEqual(r["direction"], "LONG")

    def test_bearish_divergence(self):
        c = path([100] * 21 + [100, 110, 104, 110.5, 107])
        self.assertEqual(divergence.analyze(c)["direction"], "SHORT")

    def test_none_on_flat(self):
        self.assertEqual(divergence.analyze(flat(60))["direction"], "NEUTRE")


class WyckoffBackupTests(TestCase):
    def test_lps_after_breakout(self):
        c = downtrend() + range_bars(50)
        c += [mk(105, 106, 104, 105), mk(106, 107, 105, 106),
              mk(106, 111.5, 105.5, 111, v=400),
              mk(110, 110.5, 107.6, 108.2, v=80), mk(108, 108.8, 107.4, 108.4, v=70)]
        c += [mk(108.3, 108.9, 107.9, 108.5, v=60)] * 8
        r = wyckoff.analyze(c)
        self.assertEqual(r["direction"], "LONG")
        self.assertIn("LPS", r["reasons"][0])


class ChartTests(TestCase):
    def test_png_valid(self):
        c = breakout()
        png = render_png(c, entry=110, stop_loss=104, take_profit=122, zones={"fvg": [], "order_blocks": []})
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        w, h = struct.unpack(">II", png[16:24])
        self.assertEqual((w, h), (900, 520))
        idat = png[png.index(b"IDAT") + 4:png.index(b"IEND") - 8]
        self.assertEqual(len(zlib.decompress(idat)), h * (1 + w * 3))

    def test_too_few_candles(self):
        with self.assertRaises(ValueError):
            render_png([candle(100)] * 3)


class PipelineTests(TestCase):
    def test_proposal_built_from_real_shape_data(self):
        r = build_proposal("BTC_USDT", breakout(), breakout(), breakout(), {"min_score": 1, "require_news": False})
        self.assertEqual(r["status"], "proposal")
        p = r["proposal"]
        self.assertEqual(p["direction"], "LONG")
        self.assertLess(p["stop_loss"], p["entry"])
        self.assertGreater(p["take_profit"], p["entry"])
        self.assertIsNone(p["score_global"])
        self.assertTrue(p["tools"])

    def test_flat_gives_none(self):
        self.assertEqual(build_proposal("X", flat(100), flat(100), flat(100))["status"], "none")

    def test_blocked_by_discipline(self):
        r = build_proposal("BTC_USDT", breakout(), breakout(), breakout(),
                           {"min_score": 1, "require_news": False, "capital_usdt": 100000, "limits": {"max_risk_pct": 0.01}})
        self.assertEqual(r["status"], "blocked")
        self.assertTrue(r["violations"])

    def test_last_candle_ignored(self):
        c = breakout()
        self.assertEqual(build_proposal("X", c, c, c, {"min_score": 1, "require_news": False})["proposal"]["entry"], c[-2]["c"])
