from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.trade_approval.models import TradeProposal


def mk(mode, pnl=None, **kw):
    return TradeProposal.objects.create(
        symbol="BTC_USDT", direction="LONG", mode=mode, entry=1.0, stop_loss=0.9, take_profit=1.2, leverage=5,
        capital_usdt=10, score_technical=20, expires_at=timezone.now() + timedelta(hours=1),
        net_pnl=pnl, closed_at=timezone.now() if pnl is not None else None,
        exec_status="closed" if pnl is not None else "none", **kw)


class ModeSeparationTests(TestCase):
    """DEMO et REEL ne se melangent jamais (performance, positions, execution)."""

    def setUp(self):
        get_user_model().objects.create_user("owner", password="Un-Mot-De-Passe-Long-42")
        self.client.login(username="owner", password="Un-Mot-De-Passe-Long-42")
        mk("DEMO", 10.0)
        mk("REAL", -4.0)

    @override_settings(TRADING_MODE="DEMO")
    def test_demo_sees_only_demo(self):
        self.assertEqual(self.client.get("/live/api/performance/?days=30").json()["pnl"], 10.0)

    @override_settings(TRADING_MODE="REAL", ALLOW_LIVE=True)
    def test_real_sees_only_real(self):
        self.assertEqual(self.client.get("/live/api/performance/?days=30").json()["pnl"], -4.0)

    @override_settings(TRADING_MODE="REAL", ALLOW_LIVE=True)
    def test_demo_proposal_cannot_be_executed_in_real(self):
        t = mk("DEMO")
        self.client.post(f"/trades/{t.pk}/", {"action": "execute", "confirm": "on", "real_confirm": "REAL", "entry": "1",
                                              "stop_loss": "0.9", "take_profit": "1.2", "capital_usdt": "10", "leverage": "5"})
        t.refresh_from_db()
        self.assertEqual(t.exec_status, "none")
