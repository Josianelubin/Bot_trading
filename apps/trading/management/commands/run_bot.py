"""Lance le bot en ligne de commande (facultatif : le site lance deja l'analyse automatiquement).
Si l'analyse automatique du site tourne deja, cette commande attend son tour (un seul moteur a la fois)."""
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.trading import autorun
from apps.trading.runner import BotRunner, RunnerError


class Command(BaseCommand):
    help = "Lance le bot (analyse + envoi Telegram). --once = un seul cycle."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--symbols", default="", help="ex: BTC_USDT,XAUT_USDT (sinon top 20 + extras)")
        parser.add_argument("--dry-run", action="store_true", help="rien sur Telegram ni en base")

    def handle(self, *args, **o):
        dry = o["dry_run"]
        owner = autorun.cli_owner()
        runner = BotRunner(dry=dry, log=self.stdout.write, err=self.stderr.write,
                           heartbeat=(lambda: None) if dry else (lambda: autorun.acquire(owner=owner)))
        symbols = [s.strip() for s in o["symbols"].split(",") if s.strip()]
        self.stdout.write(f"KPS demarre | mode {settings.TRADING_MODE} | marge {settings.MARGIN_MODE} | "
                          f"cycle {settings.KPS_SCAN_INTERVAL_SECONDS}s | Telegram = envoi seul | aucun trade ici")
        while True:
            if dry or autorun.acquire(owner=owner):
                try:
                    runner.cycle(symbols)
                except RunnerError as e:
                    self.stderr.write(str(e))
            else:
                self.stdout.write("Un autre moteur (analyse automatique du site) tourne deja : cycle ignore.")
            if o["once"]:
                break
            time.sleep(settings.KPS_SCAN_INTERVAL_SECONDS)
