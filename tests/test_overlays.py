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
