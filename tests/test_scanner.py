from unittest import TestCase

from apps.market_scanner.scanner import select_top


def t(name, vol, chg, last=1.0):
    return {"contract": name, "volume_24h_quote": str(vol), "change_percentage": str(chg),
            "last": str(last), "funding_rate": "0.0001"}


class ScannerTests(TestCase):
    contracts = [{"name": "A_USDT"}, {"name": "B_USDT"}, {"name": "C_USDT", "in_delisting": True},
                 {"name": "D_USDT"}]

    def test_excludes_delisting_lowvolume_and_missing(self):
        tickers = [t("A_USDT", 9e7, 3), t("B_USDT", 1e3, 5), t("C_USDT", 9e8, 9),
                   {"contract": "D_USDT", "last": "1"}]
        res = select_top(self.contracts, tickers)
        self.assertEqual([r["contract"] for r in res], ["A_USDT"])

    def test_limit_n_and_order(self):
        tickers = [t("A_USDT", 9e7, 1), t("B_USDT", 5e7, 8)]
        res = select_top(self.contracts, tickers, n=1)
        self.assertEqual(len(res), 1)
        self.assertGreaterEqual(res[0]["score"], 0)

    def test_empty(self):
        self.assertEqual(select_top([], []), [])
