from unittest import TestCase
from unittest.mock import MagicMock

from django.test import SimpleTestCase, override_settings

from apps.notifications import messages as m
from apps.notifications.telegram import send_photo

P = {"id": 7, "symbol": "BTC_USDT", "direction": "LONG", "mode": "DEMO", "leverage": 10,
     "entry": 100.0, "stop_loss": 98.0, "take_profit": 105.0, "capital_usdt": 50,
     "score_technical": 30, "score_fundamental": 20, "score_sentiment": 15, "score_global": 65,
     "tools": ["EMA", "RSI"], "reasons": ["BOS haussier"], "risks": ["Volatilite"]}


class MessageTests(TestCase):
    def test_pnl_long_and_short(self):
        self.assertAlmostEqual(m.pnl_percent(100, 105, 10, "LONG"), 50.0)
        self.assertAlmostEqual(m.pnl_percent(100, 105, 10, "SHORT"), -50.0)

    def test_proposal_contains_entry_and_no_fake_probability(self):
        txt = m.format_proposal(P)
        self.assertIn("POINT D'ENTREE : 100.0", txt)
        self.assertIn("+50.00%", txt)
        self.assertIn("-20.00%", txt)
        self.assertIn("donnees insuffisantes", txt)

    def test_result_win_and_loss(self):
        base = {"symbol": "ETH_USDT", "direction": "SHORT", "mode": "DEMO", "entry": 1, "exit": 2}
        self.assertIn("REUSSI", m.format_result({**base, "net_pnl": 3.0}))
        self.assertIn("ECHOUE", m.format_result({**base, "net_pnl": -1.0}))

    def test_news(self):
        txt = m.format_news({"title": "T", "source": "S", "url": "http://x", "sentiment": "positif"})
        self.assertIn("http://x", txt)


class TelegramExtraTests(SimpleTestCase):
    @override_settings(TELEGRAM_BOT_TOKEN="t", TELEGRAM_CHAT_ID="1")
    def test_photo(self):
        s = MagicMock()
        s.post.return_value = MagicMock(status_code=200, json=lambda: {"ok": True})
        self.assertTrue(send_photo(b"png", "x", session=s))
