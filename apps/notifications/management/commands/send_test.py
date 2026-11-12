from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.notifications.telegram import send_message


class Command(BaseCommand):
    help = "Envoie un message de test sur Telegram pour verifier le token et le chat id."

    def handle(self, *args, **opts):
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
            raise CommandError("TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID doivent etre definis.")
        ok = send_message(f"KPS connecte. Mode : {settings.TRADING_MODE} | Marge : {settings.MARGIN_MODE}")
        if not ok:
            raise CommandError("Echec : verifie le token, le chat id, et que tu as ecrit au bot au moins une fois.")
        self.stdout.write(self.style.SUCCESS("Message Telegram envoye."))
