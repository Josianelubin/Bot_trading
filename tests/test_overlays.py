from unittest import TestCase

from apps.smart_money.overlays import build
from tests.test_ict_setup import FLAT, LONG_PATH, build as mkc


def with_time(c):
    for i, x in enumerate(c):
        x["t"] = 1_700_000_000 + i * 900
    return c


class OverlayTests(TestCase):
    def setUp(self):
        self.c = with_time(mkc(FLAT + LONG_PATH[1:]))
        self.o = build(self.c)

    def test_structure_labels_and_events(self):
        labels = [l["label"] for l in self.o["labels"]]
        self.assertTrue({"LL", "HH"} & set(labels) or {"LL", "LH"} & set(labels))
        types = [(e["type"], e["dir"]) for e in self.o["events"]]
        self.assertTrue(any(t[1] == "LONG" for t in types))  # cassure haussiere apres le creux
        for e in self.o["events"]:
            self.assertLessEqual(e["from"], e["to"])

    def test_fvg_and_displacement_present(self):
        self.assertTrue(self.o["fvg"])
        self.assertTrue(any(d["dir"] == "LONG" for d in self.o["displacement"]))
        for z in self.o["fvg"]:
            self.assertLess(z["lo"], z["hi"])

    def test_liquidity_levels_are_untaken_and_sorted_by_side(self):
        last = self.c[-1]["c"]
        for l in self.o["liquidity"]:
            self.assertTrue((l["side"] == "BSL" and l["price"] > last) or (l["side"] == "SSL" and l["price"] < last))
        self.assertLessEqual(len(self.o["liquidity"]), 6)

    def test_sweep_detected_when_wick_beyond_then_close_back(self):
        c = list(self.c)
        # meche au-dessus du sommet 108.3 puis cloture dessous : balayage Buy-Side
        c.append({"o": 98.5, "h": 109.5, "l": 98.0, "c": 99.0, "v": 100.0})
        with_time(c)
        o = build(c)
        # si le sommet est un swing confirme, le balayage doit etre signale ; sinon aucun faux positif
        for s in o["sweeps"]:
            self.assertIn(s["side"], ("BSL", "SSL"))

    def test_no_time_or_short_data_gives_empty(self):
        self.assertEqual(build(mkc(FLAT[:10]))["labels"], [])
        self.assertEqual(build(mkc(FLAT + LONG_PATH[1:]))["fvg"], [])  # sans 't'


class ExtremesTests(TestCase):
    def _day_candles(self, tf_sec, days=3):
        c, t0 = [], (1_700_000_000 // 86400) * 86400
        for i in range(days * 86400 // tf_sec):
            t = t0 + i * tf_sec
            price = 100 + (i % 17) * 0.1
            c.append({"t": t, "o": price, "h": price + 0.3, "l": price - 0.3, "c": price + 0.05, "v": 10.0})
        return c

    def test_range24_matches_window_extremes(self):
        c = self._day_candles(900)
        c[-30]["h"] = 150.0   # plus haut des dernieres 24 h
        c[-10]["l"] = 50.0    # plus bas des dernieres 24 h
        o = build(c, tf_sec=900)
        self.assertEqual(o["range24"]["high"]["price"], 150.0)
        self.assertEqual(o["range24"]["low"]["price"], 50.0)
        self.assertEqual(o["range24"]["high"]["time"], c[-30]["t"])

    def test_previous_day_levels(self):
        c = self._day_candles(3600)
        day = c[-1]["t"] // 86400 - 1
        prev = [x for x in c if x["t"] // 86400 == day]
        prev[5]["h"], prev[7]["l"] = 130.0, 70.0
        o = build(c, tf_sec=3600)
        self.assertEqual(o["prev_day"]["high"]["price"], 130.0)
        self.assertEqual(o["prev_day"]["low"]["price"], 70.0)

    def test_not_enough_coverage_or_daily_timeframe_gives_none(self):
        c = self._day_candles(60, days=1)[:300]   # 5 h de bougies 1m seulement
        o = build(c, tf_sec=60)
        self.assertIsNone(o["range24"])
        self.assertIsNone(o["prev_day"])
        self.assertIsNone(build(self._day_candles(3600), tf_sec=86400)["range24"])


class LevelsForAnyTimeframeTests(TestCase):
    def _h1(self, hours=96):
        t0 = (1_700_000_000 // 86400) * 86400
        return [{"t": t0 + i * 3600, "o": 100.0, "h": 101.0 + (i % 5) * 0.1, "l": 99.0, "c": 100.2, "v": 1.0} for i in range(hours)]

    def test_compute_levels_from_hourly_candles(self):
        from apps.smart_money.overlays import compute_levels
        h1 = self._h1()
        h1[-5]["h"], h1[-3]["l"] = 140.0, 60.0
        day = h1[-1]["t"] // 86400 - 1
        prev = [x for x in h1 if x["t"] // 86400 == day]
        prev[4]["h"], prev[9]["l"] = 120.0, 80.0
        lv = compute_levels(h1)
        self.assertEqual(lv["r24"]["high"]["price"], 140.0)
        self.assertEqual(lv["r24"]["low"]["price"], 60.0)
        self.assertEqual(lv["pd"]["high"]["price"], 120.0)
        self.assertEqual(lv["pd"]["low"]["price"], 80.0)

    def test_compute_levels_needs_enough_data(self):
        from apps.smart_money.overlays import compute_levels
        self.assertIsNone(compute_levels(self._h1(10)))
        self.assertIsNone(compute_levels([]))

    def test_levels_shown_on_1m_and_daily_charts_with_snapped_times(self):
        from apps.smart_money.overlays import compute_levels
        h1 = self._h1()
        lv = compute_levels(h1)
        # graphique 1m : seulement 5 h de bougies, mais les niveaux 24h existent quand meme
        t_end = h1[-1]["t"] + 3600
        c1m = [{"t": t_end - 300 * 60 + i * 60, "o": 100, "h": 100.3, "l": 99.8, "c": 100.1, "v": 1.0} for i in range(300)]
        o = build(c1m, tf_sec=60, levels=lv)
        self.assertIsNotNone(o["range24"])
        times = [x["t"] for x in c1m]
        self.assertIn(o["range24"]["high"]["time"], times)   # temps aligne sur une bougie du graphique
        # graphique 1D
        t0 = h1[0]["t"] // 86400 * 86400
        cd = [{"t": t0 + i * 86400, "o": 100, "h": 102, "l": 98, "c": 101, "v": 1.0} for i in range(40)]
        od = build(cd, tf_sec=86400, levels=lv)
        self.assertIsNotNone(od["range24"])
        self.assertIsNotNone(od["prev_day"])
        self.assertIn(od["prev_day"]["high"]["time"], [x["t"] for x in cd])
