from unittest import TestCase
from unittest.mock import MagicMock

from apps.decision_engine.confluence import classify, confluence
from apps.sentiment_analysis import engine as se
from apps.sentiment_analysis.sources import SentimentError, fetch_fear_greed


def stats(oi0=1_000_000.0, oi1=1_100_000.0, p0=100.0, p1=105.0, lsr=1.0, long_liq=0.0, short_liq=0.0, n=24):
    pts = []
    for i in range(n):
        f = i / (n - 1)
        pts.append({"open_interest_usd": oi0 + (oi1 - oi0) * f, "mark_price": p0 + (p1 - p0) * f, "lsr_account": lsr,
                    "long_liq_usd": long_liq / 6, "short_liq_usd": short_liq / 6})
    return pts


class SentimentTests(TestCase):
    def test_unavailable_when_no_data(self):
        r = se.assess({}, "LONG")
        self.assertFalse(r["available"])
        self.assertIn("DONNEES INDISPONIBLES", r["reasons"][0])
        self.assertFalse(se.assess(None, "LONG")["available"])

    def test_neutral_is_half_points(self):
        r = se.assess({"fear_greed": {"value": 50, "label": "Neutral"}, "funding_rate": 0.0001, "stats": stats(1e6, 1e6, 100, 100, 1.0)}, "LONG")
        self.assertEqual(r["score"], 13)  # 25 / 2

    def test_extreme_fear_and_negative_funding_favor_long(self):
        d = {"fear_greed": {"value": 15, "label": "Extreme Fear"}, "funding_rate": -0.0008, "stats": stats(lsr=0.5)}
        long_, short = se.assess(d, "LONG"), se.assess(d, "SHORT")
        self.assertGreater(long_["score"], 18)
        self.assertLess(short["score"], 8)
        self.assertIn("Surchauffe baissiere", long_["labels"])
        self.assertIn("Risque de retournement", long_["labels"])

    def test_overheated_longs_hurt_long(self):
        d = {"fear_greed": {"value": 85, "label": "Extreme Greed"}, "funding_rate": 0.0009, "stats": stats(1e6, 1e6, 100, 100, lsr=3.0)}
        r = se.assess(d, "LONG")
        self.assertLess(r["score"], 8)
        self.assertIn("Surchauffe haussiere", r["labels"])
        self.assertIn("Desequilibre extreme des positions", r["labels"])

    def test_oi_up_price_up_is_accumulation(self):
        r = se.assess({"stats": stats(1e6, 1.2e6, 100, 108, 1.0)}, "LONG")
        self.assertIn("Accumulation (nouveaux longs)", r["labels"])
        r2 = se.assess({"stats": stats(1e6, 1.2e6, 100, 92, 1.0)}, "SHORT")
        self.assertIn("Distribution (nouveaux shorts)", r2["labels"])

    def test_long_liquidations_are_contrarian_bullish(self):
        r = se.assess({"stats": stats(1e6, 1e6, 100, 100, 1.0, long_liq=50_000.0, short_liq=1_000.0)}, "LONG")
        self.assertTrue(any(c["name"] == "liquidations" and c["bias"] > 0 for c in r["components"]))

    def test_fear_greed_source_parsing_and_errors(self):
        s = MagicMock()
        s.get.return_value = MagicMock(status_code=200, json=lambda: {"data": [{"value": "23", "value_classification": "Extreme Fear"}]})
        self.assertEqual(fetch_fear_greed(s), {"value": 23, "label": "Extreme Fear"})
        s.get.return_value = MagicMock(status_code=200, json=lambda: {"data": []})
        with self.assertRaises(SentimentError):
            fetch_fear_greed(s)


class ConfluenceTests(TestCase):
    def _f(self, score, bias):
        return {"score": score, "bias": bias, "block": None}

    def test_classification_thresholds(self):
        self.assertEqual([classify(x) for x in (100, 80, 79, 65, 64, 50, 49, 0)],
                         ["fort", "fort", "modere", "modere", "surveillance", "surveillance", "aucun", "aucun"])

    def test_strong_when_all_aligned(self):
        r = confluence("LONG", 36, self._f(32, 0.8), self._f(22, 0.7))
        self.assertEqual((r["score"], r["class"]), (90, "fort"))
        self.assertFalse(r["partial"])

    def test_blocks_always_win_over_score(self):
        r = confluence("LONG", 40, {"score": 35, "bias": 1.0, "block": "Actualite majeure defavorable : hack"}, self._f(25, 1.0))
        self.assertGreaterEqual(r["score"], 95)
        self.assertEqual(r["class"], "aucun")
        self.assertTrue(r["blocked"])
        r2 = confluence("LONG", 40, self._f(35, 1.0), self._f(25, 1.0), blocks=["Spread anormal"])
        self.assertEqual(r2["class"], "aucun")

    def test_one_contradiction_caps_and_two_cancel(self):
        one = confluence("LONG", 40, self._f(35, 0.9), self._f(5, -0.8))
        self.assertLessEqual(one["score"], 64)
        two = confluence("LONG", 40, self._f(3, -0.8), self._f(5, -0.8))
        self.assertEqual((two["score"], two["class"]), (0, "aucun"))

    def test_partial_when_component_missing(self):
        r = confluence("SHORT", 30, self._f(20, -0.5), None)
        self.assertTrue(r["partial"])
        self.assertEqual(r["missing"], ["sentiment"])
        self.assertEqual(r["max_available"], 75)
        self.assertEqual(r["score"], round(100 * 50 / 75))
