from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.smart_money import overlays
from apps.smart_money.setup import find_setup
from tests.test_ict_setup import long_candles


def bundle():
    c = long_candles()
    for i, x in enumerate(c):
        x["t"] = 1_700_000_000 + i * 900
    s = find_setup(c, "UP")
    res = {"symbol": "BTC_USDT", "timeframe": "15m", "direction": "LONG", "status": "signal", "entry": s["entry"],
           "stop_loss": s["stop_loss"], "take_profits": s["take_profits"], "ict": s, "message": "Setup ICT LONG", "score": 30, "max_score": 40}
    return {"candles": c, "result": res, "smc": overlays.build(c, tf_sec=900)}


class PhotoEndpointsTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user("owner", password="Un-Mot-De-Passe-Long-42")

    def login(self):
        self.client.login(username="owner", password="Un-Mot-De-Passe-Long-42")

    def test_requires_login(self):
        for url in ("/live/api/analysis-image/?symbol=BTC_USDT&tf=15m", "/live/photos/", "/live/api/scan/?symbol=BTC_USDT&tf=15m"):
            self.assertEqual(self.client.get(url).status_code, 302)

    def test_image_is_png_and_params_are_validated(self):
        self.login()
        with patch("apps.market_scanner.live_views._analysis_bundle", return_value=bundle()):
            r = self.client.get("/live/api/analysis-image/?symbol=BTC_USDT&tf=15m")
            self.assertEqual((r.status_code, r["Content-Type"]), (200, "image/png"))
            self.assertTrue(r.content.startswith(b"\x89PNG"))
            self.assertEqual(r["Cache-Control"], "no-store")
        self.assertEqual(self.client.get("/live/api/analysis-image/?symbol=../x&tf=15m").status_code, 400)
        self.assertEqual(self.client.get("/live/api/analysis-image/?symbol=BTC_USDT&tf=7s").status_code, 400)

    def test_scan_api_returns_levels_from_the_same_bundle(self):
        self.login()
        with patch("apps.market_scanner.live_views._analysis_bundle", return_value=bundle()):
            j = self.client.get("/live/api/scan/?symbol=BTC_USDT&tf=15m").json()
        self.assertEqual(j["direction"], "LONG")
        self.assertLess(j["stop_loss"], j["entry"])
        self.assertEqual(len(j["take_profits"]), 3)

    def test_photos_page_lists_all_timeframes(self):
        self.login()
        r = self.client.get("/live/photos/?symbol=BTC_USDT")
        self.assertEqual(r.status_code, 200)
        for tf in ("1m", "15m", "4h", "1d", "1w"):
            self.assertContains(r, f'data-tf="{tf}"')

    def test_send_to_telegram(self):
        self.login()
        with patch("apps.market_scanner.live_views._analysis_bundle", return_value=bundle()), \
                patch("apps.market_scanner.live_views.telegram.send_photo", return_value=True) as sp:
            r = self.client.post("/live/api/analysis-image/send/?symbol=BTC_USDT&tf=15m")
        self.assertEqual(r.json(), {"sent": True})
        self.assertTrue(sp.call_args.args[0].startswith(b"\x89PNG"))
