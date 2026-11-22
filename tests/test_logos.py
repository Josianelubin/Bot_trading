from unittest import TestCase
from unittest.mock import MagicMock

from apps.market_data import logos


def resp(status=200, ctype="image/png", body=b"\x89PNG....", js=None):
    m = MagicMock(status_code=status, headers={"Content-Type": ctype}, content=body)
    m.json = lambda: js
    return m


class LogoTests(TestCase):
    def setUp(self):
        logos._cg.update(t=0.0, map={})

    def test_clean_base(self):
        self.assertEqual(logos.clean_base("BTC_USDT"), "BTC")
        self.assertEqual(logos.clean_base("1000PEPE_USDT"), "PEPE")
        self.assertEqual(logos.clean_base("1000000MOG_USDT"), "MOG")
        self.assertEqual(logos.clean_base("XAUT_USDT"), "XAUT")
        self.assertIsNone(logos.clean_base("../../etc"))
        self.assertIsNone(logos.clean_base(""))

    def test_coingecko_map_first_symbol_wins(self):
        s = MagicMock()
        s.get.return_value = resp(js=[{"symbol": "btc", "image": "https://coin-images.coingecko.com/coins/images/1/large/bitcoin.png"},
                                      {"symbol": "btc", "image": "https://coin-images.coingecko.com/x/large/fake.png"},
                                      {"symbol": "eth", "image": "https://coin-images.coingecko.com/coins/images/279/large/ethereum.png"}])
        m = logos.coingecko_map(s, pages=1)
        self.assertEqual(m["BTC"].split("/")[-1], "bitcoin.png")
        self.assertIn("ETH", m)

    def test_candidates_order_and_small_variant(self):
        c = logos.candidates("BTC", {"BTC": "https://coin-images.coingecko.com/coins/images/1/large/bitcoin.png"})
        self.assertIn("/small/", c[0])
        self.assertTrue(c[1].endswith("/btc.png"))
        self.assertEqual(len(logos.candidates("XYZ", {})), 2)

    def test_download_rejects_bad_content_and_hosts(self):
        s = MagicMock()
        s.get.return_value = resp(ctype="text/html", body=b"<html>")
        self.assertIsNone(logos.download("https://assets.coincap.io/x.png", s))
        s.get.return_value = resp(ctype="image/svg+xml", body=b"<svg/>")
        self.assertIsNone(logos.download("https://assets.coincap.io/x.svg", s))
        s.get.return_value = resp(body=b"x" * (logos.MAX_BYTES + 1))
        self.assertIsNone(logos.download("https://assets.coincap.io/x.png", s))
        s.get.reset_mock()
        self.assertIsNone(logos.download("https://evil.example.com/a.png", s))   # hote non autorise
        self.assertIsNone(logos.download("http://assets.coincap.io/a.png", s))   # pas de http
        s.get.assert_not_called()
        s.get.return_value = resp()
        self.assertEqual(logos.download("https://assets.coincap.io/ok.png", s)[1], "image/png")

    def test_fetch_falls_back_to_next_source(self):
        s = MagicMock()

        def get(url, **kw):
            if "coingecko.com/api" in url:
                return resp(js=[{"symbol": "sui", "image": "https://coin-images.coingecko.com/coins/images/1/large/sui.png"}])
            if "coin-images.coingecko.com" in url or "jsdelivr" in url:
                return resp(404)
            return resp()  # coincap
        s.get.side_effect = get
        got = logos.fetch_logo("SUI_USDT", s)
        self.assertIsNotNone(got)
        self.assertIn("coincap", got[2])

    def test_fetch_none_when_nothing_found_or_invalid_symbol(self):
        s = MagicMock()
        s.get.return_value = resp(404, js=[])
        self.assertIsNone(logos.fetch_logo("ZZZZ_USDT", s))
        self.assertIsNone(logos.fetch_logo("../x", s))
