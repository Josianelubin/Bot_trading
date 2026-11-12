from django.core.management.base import BaseCommand, CommandError

from apps.market_data.gate_client import GateAPIError, GateClient
from apps.market_scanner.scanner import select_top
from apps.notifications.telegram import send_message


class Command(BaseCommand):
    help = "Scanne Gate.io (lecture seule) et affiche les 20 contrats retenus."

    def add_arguments(self, parser):
        parser.add_argument("--telegram", action="store_true", help="Envoyer le resume sur Telegram")

    def handle(self, *args, **opts):
        client = GateClient()
        try:
            top = select_top(client.contracts(), client.tickers())
        except GateAPIError as e:
            raise CommandError(f"DONNEES INDISPONIBLES : {e}")
        if not top:
            raise CommandError("Aucun contrat ne respecte les criteres.")
        lines = []
        for i, r in enumerate(top, 1):
            lines.append(f"{i:2d}. {r['contract']:<14} {r['last']:<12g} {r['change_pct']:+.2f}%  "
                         f"vol {r['quote_volume']/1e6:.1f}M  score {r['score']}")
        report = "\n".join(lines)
        self.stdout.write(report)
        if opts["telegram"]:
            ok = send_message("KPS - Top 20\n" + report)
            self.stdout.write("Telegram : envoye" if ok else "Telegram : ECHEC (verifie token et chat id)")
