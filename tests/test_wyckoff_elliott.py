from unittest import TestCase

from apps.technical_analysis import elliott, wyckoff


def mk(o, h, l, c, v=100.0):
    return {"o": o, "h": h, "l": l, "c": c, "v": v}


def range_bars(n, lo=100.0, hi=108.0):
    out = []
    for i in range(n):
        mid = lo + 0.8 + (hi - lo - 1.6) * (0.5 + 0.5 * ((i * 13 % 10) / 10 * 2 - 1))
        out.append(mk(mid, min(mid + 0.6, hi), max(mid - 0.6, lo + 0.0), mid))
    return out


def downtrend(n=30):
    return [mk(130 - i, 131 - i, 129 - i, 130 - i - 0.5) for i in range(n)]


class WyckoffTests(TestCase):
    def test_spring_after_downtrend(self):
        c = downtrend() + range_bars(50) + [mk(101, 101.5, 100.5, 101), mk(101, 102, 98.5, 102, v=60), mk(102, 103, 101.5, 103)]
        r = wyckoff.analyze(c)
        self.assertEqual(r["direction"], "LONG")
        self.assertEqual(r["score"], 8)

    def test_sos_with_volume(self):
        c = downtrend() + range_bars(50) + [mk(104, 105, 103, 104), mk(105, 106, 104, 106), mk(106, 111, 105.5, 110.5, v=400)]
        r = wyckoff.analyze(c)
        self.assertEqual(r["direction"], "LONG")
        self.assertEqual(r["score"], 9)

    def test_upthrust_short(self):
        up = [mk(100 + i, 101 + i, 99 + i, 100 + i + 0.5) for i in range(30)]
        c = up + range_bars(50, 130.0, 138.0) + [mk(136, 137, 135, 136), mk(137, 140, 136, 137, v=200), mk(137, 137.5, 134, 134.5)]
        r = wyckoff.analyze(c)
        self.assertEqual(r["direction"], "SHORT")

    def test_no_range(self):
        c = [mk(100 + i, 101 + i, 99 + i, 100 + i) for i in range(80)]
        self.assertEqual(wyckoff.analyze(c)["direction"], "NEUTRE")

    def test_no_data(self):
        self.assertIn("DONNEES INDISPONIBLES", wyckoff.analyze(range_bars(10))["reasons"][0])


def path(points, bars=6, spread=0.2):
    c = []
    for a, b in zip(points, points[1:]):
        for k in range(bars):
            x = a + (b - a) * k / bars
            c.append(mk(x, x + spread, x - spread, x))
    return c


class ElliottTests(TestCase):
    def test_wave5_long(self):
        c = path([120, 115, 100, 110, 104, 125, 116, 118.5, 119])
        r = elliott.analyze(c)
        self.assertEqual(r["direction"], "LONG")
        self.assertIn("vague 5", r["reasons"][0])
        self.assertLess(r["invalidation"], c[-1]["c"])

    def test_wave3_long(self):
        c = path([120, 115, 100, 110, 104, 106.5, 107.5, 108])
        r = elliott.analyze(c)
        self.assertEqual(r["direction"], "LONG")
        self.assertIn("vague 3", r["reasons"][0])

    def test_rule_violation_not_signalled(self):
        # vague 4 chevauche la vague 1 (116 -> 108 < 110) : invalide
        c = path([115, 112, 100, 110, 104, 125, 108, 112])
        self.assertEqual(elliott.analyze(c)["direction"], "NEUTRE")

    def test_no_data(self):
        self.assertIn("DONNEES INDISPONIBLES", elliott.analyze(range_bars(10))["reasons"][0])
