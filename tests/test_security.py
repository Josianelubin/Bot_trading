from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase


class SecurityPhase1Tests(TestCase):
    def test_health_is_public(self):
        self.assertEqual(self.client.get("/health/").status_code, 200)

    def test_dashboard_requires_login(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r["Location"])

    def test_no_public_signup(self):
        for url in ("/accounts/signup/", "/accounts/register/"):
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_demo_and_isolated_by_default(self):
        self.assertEqual(settings.TRADING_MODE, "DEMO")
        self.assertEqual(settings.MARGIN_MODE, "ISOLATED")

    def test_login_then_dashboard(self):
        get_user_model().objects.create_user("owner", password="Un-Mot-De-Passe-Long-42")
        self.assertTrue(self.client.login(username="owner", password="Un-Mot-De-Passe-Long-42"))
        r = self.client.get("/", follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "DEMO")

    def test_live_requires_login_and_validates_params(self):
        for url in ("/live/", "/live/api/candles/", "/live/api/scan/", "/live/api/emergency/"):
            self.assertEqual(self.client.get(url).status_code, 302)
        get_user_model().objects.create_user("owner", password="Un-Mot-De-Passe-Long-42")
        self.client.login(username="owner", password="Un-Mot-De-Passe-Long-42")
        self.assertEqual(self.client.get("/live/api/candles/?symbol=../../x&tf=1h").status_code, 400)
        self.assertEqual(self.client.get("/live/api/scan/?symbol=BTC_USDT&tf=99x").status_code, 400)
        self.assertEqual(self.client.get("/live/api/emergency/").status_code, 405)
