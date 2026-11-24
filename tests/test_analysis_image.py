import struct
from unittest import TestCase

from apps.smart_money import overlays
from apps.smart_money.setup import find_setup
from apps.trade_history.analysis_image import fmt, render_analysis
from tests.test_ict_setup import long_candles


def with_time(c):
    for i, x in enumerate(c):
        x["t"] = 1_700_000_000 + i * 900
    return c


def png_size(png):
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", png[16:24])


class AnalysisImageTests(TestCase):
    def setUp(self):
        self.c = with_time(long_candles())
        self.setup = find_setup(self.c, "UP")
        self.smc = overlays.build(self.c, tf_sec=900)

    def _res(self, **kw):
        s = self.setup
        return {"direction": "LONG", "entry": s["entry"], "stop_loss": s["stop_loss"], "take_profits": s["take_profits"], "ict": s,
                "score": 30, "max_score": 40, "confluence": {"score": 70, "class": "modere"}, "message": "Setup ICT LONG", **kw}

    def test_long_image_is_valid_png(self):
        png = render_analysis(self.c, self._res(), self.smc, "BTC_USDT", "15m", n=45)
        self.assertEqual(png_size(png), (1500, 860))
        self.assertGreater(len(png), 20_000)

    def test_short_image(self):
        inv = with_time([{**x, "o": 200 - x["o"], "h": 200 - x["l"], "l": 200 - x["h"], "c": 200 - x["c"]} for x in long_candles()])
        s = find_setup(inv, "DOWN")
        self.assertEqual(s["direction"], "SHORT")
        res = {"direction": "SHORT", "entry": s["entry"], "stop_loss": s["stop_loss"], "take_profits": s["take_profits"], "ict": s,
               "message": "Setup ICT SHORT"}
        self.assertEqual(png_size(render_analysis(inv, res, overlays.build(inv, tf_sec=900), "ETH_USDT", "1h", n=45)), (1500, 860))

    def test_attente_image_without_levels_or_smc(self):
        res = {"direction": "ATTENTE", "message": "ATTENTE : aucun setup ICT"}
        self.assertEqual(png_size(render_analysis(self.c, res, None, "SOL_USDT", "5m")), (1500, 860))

    def test_levels_without_ict_and_single_take_profit(self):
        res = {"direction": "LONG", "entry": 99.0, "stop_loss": 95.0, "take_profit": 108.0, "message": "Signal"}
        self.assertEqual(png_size(render_analysis(self.c, res, self.smc, "XAUT_USDT", "1d")), (1500, 860))

    def test_too_few_candles(self):
        with self.assertRaises(ValueError):
            render_analysis(self.c[:3], {"direction": "ATTENTE"}, None)

    def test_fmt(self):
        self.assertEqual(fmt(67482.21), "67,482.21")
        self.assertEqual(fmt(0.61240), "0.6124")
