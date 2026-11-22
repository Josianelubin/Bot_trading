from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.trading import autorun
from apps.trading.models import BotStatus


class LeaseTests(TestCase):
    def test_single_engine_at_a_time(self):
        self.assertTrue(autorun.acquire(owner="web:a"))
        self.assertTrue(autorun.acquire(owner="web:a"))      # renouvellement
        self.assertFalse(autorun.acquire(owner="web:b"))     # un autre processus attend
        self.assertFalse(autorun.acquire(owner="cli:c"))

    def test_stale_lease_is_taken_over(self):
        autorun.acquire(owner="web:a")
        BotStatus.objects.filter(pk=1).update(heartbeat=timezone.now() - timedelta(seconds=autorun.LEASE_SECONDS + 5))
        self.assertTrue(autorun.acquire(owner="web:b"))
        self.assertEqual(autorun.get_status().owner, "web:b")

    def test_ensure_started_is_noop_when_disabled(self):
        with override_settings(KPS_AUTORUN=False):
            self.assertFalse(autorun.ensure_started())


@patch("apps.trading.middleware.ensure_started", lambda: True)
@patch("apps.trading.autorun.ensure_started", lambda: True)
class BotApiTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user("owner", password="Un-Mot-De-Passe-Long-42")

    def login(self):
        self.client.login(username="owner", password="Un-Mot-De-Passe-Long-42")

    def test_requires_login(self):
        self.assertEqual(self.client.get("/live/api/bot/").status_code, 302)
        self.assertEqual(self.client.post("/live/api/bot/control/", {"action": "toggle"}).status_code, 302)

    def test_status_and_toggle(self):
        self.login()
        r = self.client.get("/live/api/bot/").json()
        self.assertTrue(r["enabled"])
        self.assertEqual(r["cycles"], 0)
        with patch("apps.market_scanner.live_views.telegram.send_message", return_value=True):
            r = self.client.post("/live/api/bot/control/", {"action": "toggle"}).json()
        self.assertFalse(r["enabled"])

    @override_settings(KPS_AUTORUN=True)
    def test_run_now_sets_request(self):
        self.login()
        r = self.client.post("/live/api/bot/control/", {"action": "run_now"}).json()
        self.assertTrue(r["run_requested"])

    @override_settings(KPS_AUTORUN=False)
    def test_run_now_refused_when_autorun_disabled(self):
        self.login()
        self.assertEqual(self.client.post("/live/api/bot/control/", {"action": "run_now"}).status_code, 400)

    def test_unknown_action(self):
        self.login()
        self.assertEqual(self.client.post("/live/api/bot/control/", {"action": "x"}).status_code, 400)
