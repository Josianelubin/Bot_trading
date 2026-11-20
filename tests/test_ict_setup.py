from unittest import TestCase

from apps.smart_money.setup import find_setup


def build(closes, base=None):
    out, prev = [], closes[0]
    for cl in closes[1:]:
        out.append({"o": prev, "h": max(prev, cl) + 0.2, "l": min(prev, cl) - 0.2, "c": cl, "v": 100.0})
        prev = cl
    return out


FLAT = [100 + (0.2 if i % 2 else 0.0) for i in range(32)]
LONG_PATH = [100, 101.33, 102.67, 104, 102, 100, 98, 99.5, 101, 98, 96, 94, 98.7, 103.4, 108.1, 105, 102, 100, 98.5]


def long_candles():
    return build(FLAT + LONG_PATH[1:], None)


class SetupTests(TestCase):
    def test_bullish_setup_in_ote_zone(self):
        r = find_setup(long_candles(), htf_trend="UP")
        self.assertIsNotNone(r)
        self.assertEqual((r["direction"], r["status"]), ("LONG", "zone"))
        lo, hi = r["zone"]
        self.assertTrue(lo <= r["entry"] <= hi)
        self.assertLess(r["stop_loss"], r["invalidation"])
        tp1, tp2, tp3 = r["take_profits"]
        self.assertTrue(r["entry"] < tp1 < tp2 < tp3)
        for k in ("CHoCH / MSS", "Zone OTE", "Imbalance", "Liquidity sweep", "Tendance HTF"):
            self.assertIn(k, r["confluences"])
        self.assertGreaterEqual(r["score"], 8)

    def test_bearish_setup_by_symmetry(self):
        c = build([200 - x for x in FLAT + LONG_PATH[1:]])
        r = find_setup(c, htf_trend="DOWN")
        self.assertIsNotNone(r)
        self.assertEqual(r["direction"], "SHORT")
        self.assertTrue(r["entry"] > r["take_profits"][0] > r["take_profits"][1] > r["take_profits"][2])
        self.assertGreater(r["stop_loss"], r["invalidation"])
        lo, hi = r["zone"]
        self.assertTrue(lo <= r["entry"] <= hi)
        self.assertIn("Premium", r["confluences"])

    def test_htf_contrary_lowers_score(self):
        a = find_setup(long_candles(), htf_trend="UP")
        b = find_setup(long_candles(), htf_trend="DOWN", min_score=0)
        self.assertGreater(a["score"], b["score"])

    def test_invalidated_when_origin_breaks(self):
        c = long_candles() + [{"o": 98.5, "h": 98.6, "l": 92.0, "c": 92.5, "v": 100.0}]
        r = find_setup(c, htf_trend="UP")
        self.assertTrue(r is None or r["direction"] != "LONG")

    def test_no_setup_on_flat_or_short_data(self):
        self.assertIsNone(find_setup(build(FLAT)))
        self.assertIsNone(find_setup(build(FLAT[:10])))
