from unittest import TestCase

from apps.smart_money import ict


def mk(o, h, l, c, v=100.0):
    return {"o": o, "h": h, "l": l, "c": c, "v": v}


class FVGTests(TestCase):
    base = [mk(100, 100.5, 99.5, 100), mk(100, 104, 99.8, 103.5), mk(103.5, 105, 102, 104.5)]
    # gap haussier entre h(bougie0)=100.5 et l(bougie2)=102

    def test_bullish_fvg_open(self):
        g = ict.fvgs(self.base, atr_val=1.0)
        self.assertEqual(len(g), 1)
        self.assertEqual((g[0]["type"], g[0]["status"]), ("bullish", "ouvert"))

    def test_partial_filled_invalid(self):
        part = ict.fvgs(self.base + [mk(104, 104.5, 101.5, 103)], 1.0)[0]
        self.assertEqual(part["status"], "partiel")
        full = ict.fvgs(self.base + [mk(104, 104.5, 100.2, 101)], 1.0)[0]
        self.assertEqual(full["status"], "comble")
        inv = ict.fvgs(self.base + [mk(104, 104.5, 99, 100)], 1.0)[0]
        self.assertEqual(inv["status"], "invalide")

    def test_small_gap_ignored(self):
        self.assertEqual(ict.fvgs(self.base, atr_val=10.0), [])

    def test_bearish_fvg(self):
        c = [mk(100, 100.5, 99.5, 100), mk(100, 100.2, 96, 96.5), mk(96.5, 98, 95, 95.5)]
        g = ict.fvgs(c, 1.0)
        self.assertEqual(g[0]["type"], "bearish")


class OrderBlockTests(TestCase):
    def test_bullish_ob_and_invalidation(self):
        c = [mk(100, 100.6, 99.6, 100.1) for _ in range(12)]
        c += [mk(100.5, 100.7, 99.5, 99.8)]            # derniere bougie baissiere = OB
        c += [mk(99.8, 104.2, 99.7, 104)]              # impulsion + cassure de structure
        obs = ict.order_blocks(c, atr_val=1.0)
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0]["type"], "bullish")
        self.assertTrue(obs[0]["valid"])
        self.assertAlmostEqual(obs[0]["lo"], 99.5)
        c2 = c + [mk(104, 104, 98, 99)]                # cloture sous la zone
        self.assertFalse(ict.order_blocks(c2, 1.0)[0]["valid"])


class LiquidityTests(TestCase):
    def test_equal_highs_sweep(self):
        closes = [100, 102, 105, 110, 105, 102, 100, 102, 105, 110, 105, 102, 100, 102, 104, 106]
        c = [mk(x, x + 0.2, x - 0.2, x) for x in closes]
        c.append(mk(107, 111, 106.5, 108))             # wick au-dessus de 110.2, cloture dessous
        r = ict.liquidity(c)
        self.assertIsNotNone(r["equal_highs"])
        self.assertEqual(r["sweep"]["dir"], "SHORT")


class StructureAndAnalyzeTests(TestCase):
    def test_bos_bullish(self):
        pts = [100, 106, 102, 108, 104, 111]
        c = []
        for a, b in zip(pts, pts[1:]):
            for k in range(5):
                x = a + (b - a) * k / 5
                c.append(mk(x, x + 0.3, x - 0.3, x))
        c += [mk(111, 112.5, 110.8, 112.4)] * 3
        s = ict.structure(c)
        self.assertEqual(s["trend"], "UP")
        self.assertEqual(s["event"]["dir"], "LONG")

    def test_analyze_no_data_and_flat(self):
        self.assertIn("DONNEES INDISPONIBLES", ict.analyze([mk(1, 1, 1, 1)] * 10)["reasons"][0])
        flat = [mk(100, 100.5, 99.5, 100 + ((i * 7) % 5 - 2) * 0.1) for i in range(80)]
        self.assertEqual(ict.analyze(flat)["direction"], "NEUTRE")
