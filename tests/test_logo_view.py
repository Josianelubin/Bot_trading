from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase


class LogoViewTests(TestCase):
    def test_requires_login(self):
        self.assertEqual(self.client.get("/live/logo/BTC.png").status_code, 302)

    def test_serves_stored_logo_and_404_when_missing(self):
        get_user_model().objects.create_user("owner", password="Un-Mot-De-Passe-Long-42")
        self.client.login(username="owner", password="Un-Mot-De-Passe-Long-42")
        with patch("apps.market_scanner.live_views.logo_store.get_logo", return_value=(b"\x89PNG", "image/png")):
            r = self.client.get("/live/logo/BTC.png")
            self.assertEqual((r.status_code, r["Content-Type"]), (200, "image/png"))
            self.assertIn("max-age", r["Cache-Control"])
        with patch("apps.market_scanner.live_views.logo_store.get_logo", return_value=None):
            self.assertEqual(self.client.get("/live/logo/ZZZZ.png").status_code, 404)
