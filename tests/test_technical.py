from unittest import TestCase

from apps.technical_analysis.bollinger import analyze, compute_bands


class BollingerTests(TestCase):
    def test_constant_series_zero_width(self):
        b = compute_bands([10.0] * 25)[-1]
        self.assertAlmostEqual(b["middle"], 10.0)
        self.assertAlmostEqual(b["upper"], b["lower"])
        self.assertIsNone(compute_bands([10.0] * 25)[18])

    def test_known_values(self):
        closes = list(range(1, 21))  # SMA 10.5, sd population = sqrt(33.25)
        b = compute_bands(closes)[-1]
        self.assertAlmostEqual(b["middle"], 10.5)
        self.assertAlmostEqual(b["upper"] - b["middle"], 2 * 33.25 ** 0.5, places=6)

    def test_insufficient_data(self):
        r = analyze([1, 2, 3])
        self.assertEqual(r["direction"], "NEUTRE")
        self.assertIn("DONNEES INDISPONIBLES", r["reasons"][0])

    def test_squeeze_is_neutral(self):
        closes = [100 + (i % 7) * 3 for i in range(120)] + [100 + (i % 2) * 0.01 for i in range(40)]
        r = analyze(closes)
        self.assertEqual(r["direction"], "NEUTRE")
        self.assertTrue(any("Squeeze" in x for x in r["reasons"]))

    def test_walking_upper_band_long_needs_confirmation(self):
        closes = [100 + (i % 3) * 0.2 for i in range(60)]
        for i in range(1, 9):
            closes.append(closes[-1] + 1.5 + i * 0.1)
        r = analyze(closes)
        self.assertEqual(r["direction"], "LONG")
        self.assertLessEqual(r["score"], 3)  # non confirme => score reduit
        self.assertGreater(analyze(closes, rsi=65)["score"], r["score"])

    def test_rsi_contradiction_reduces_score(self):
        closes = [100 + (i % 3) * 0.2 for i in range(60)]
        for i in range(1, 9):
            closes.append(closes[-1] + 1.5 + i * 0.1)
        ok, bad = analyze(closes, rsi=70), analyze(closes, rsi=30)
        self.assertEqual(ok["direction"], "LONG")
        self.assertGreater(ok["score"], bad["score"])


class BollingerFormationsTests(TestCase):
    def _noise(self, n, base=100.0):
        return [base + ((i * 7) % 5 - 2) * 0.3 for i in range(n)]

    def test_head_and_shoulders_top(self):
        c = self._noise(30)
        c += [101, 104, 108, 104, 101, 104, 108, 112, 116, 112, 108, 104, 101, 104, 108, 104, 100, 96, 93]
        r = analyze(c, rsi=35)
        self.assertIn("head_shoulders", r["patterns"])
        self.assertEqual(r["direction"], "SHORT")

    def test_inverse_head_and_shoulders(self):
        c = self._noise(30)
        c += [99, 96, 92, 96, 99, 96, 92, 88, 84, 88, 92, 96, 99, 96, 92, 96, 100, 104, 107]
        r = analyze(c, rsi=65)
        self.assertIn("inverse_head_shoulders", r["patterns"])
        self.assertEqual(r["direction"], "LONG")

    def test_head_fake_short(self):
        c = [100 + (i % 7) * 3 for i in range(120)] + [100 + (i % 2) * 0.01 for i in range(25)]
        c += [100.5, 101.5, 103, 106, 104, 99, 96]
        r = analyze(c, rsi=40)
        self.assertIn("head_fake", r["patterns"])
        self.assertEqual(r["direction"], "SHORT")

    def test_returns_patterns_key(self):
        r = analyze(self._noise(60))
        self.assertIn("patterns", r)

    def test_w_bottom(self):
        c = self._noise(30) + [99, 96, 90, 93, 96, 98, 95, 92, 91.5, 94, 97, 100]
        r = analyze(c, rsi=55)
        self.assertIn("w_bottom", r["patterns"])
        self.assertEqual(r["direction"], "LONG")

    def test_m_top(self):
        c = self._noise(30) + [101, 104, 110, 107, 104, 102, 105, 108, 108.5, 106, 103, 100]
        r = analyze(c, rsi=45)
        self.assertIn("m_top", r["patterns"])
        self.assertEqual(r["direction"], "SHORT")
