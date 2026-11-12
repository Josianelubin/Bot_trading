from unittest.mock import MagicMock

from django.test import SimpleTestCase, override_settings

from apps.notifications.telegram import send_message


class TelegramTests(SimpleTestCase):
    @override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHAT_ID="")
    def test_not_configured(self):
        self.assertFalse(send_message("x"))

    @override_settings(TELEGRAM_BOT_TOKEN="t", TELEGRAM_CHAT_ID="1")
    def test_success_only_if_ok_true(self):
        s = MagicMock()
        s.post.return_value = MagicMock(status_code=200, json=lambda: {"ok": True})
        self.assertTrue(send_message("x", session=s))
        s.post.return_value = MagicMock(status_code=200, json=lambda: {"ok": False})
        self.assertFalse(send_message("x", session=s))
