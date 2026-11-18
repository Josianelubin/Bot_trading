import requests
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Affiche l'adresse IP publique SORTANTE de ce serveur (a mettre dans la liste blanche IP de la cle API Gate.io)."

    def handle(self, *args, **opts):
        for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
            try:
                r = requests.get(url, timeout=10)
                if r.status_code == 200 and r.text.strip():
                    self.stdout.write(self.style.SUCCESS(f"IP publique sortante : {r.text.strip()}"))
                    self.stdout.write("Mets cette IP dans la liste blanche de ta cle API Gate.io. "
                                      "Attention : elle change si tu changes de reseau (Wi-Fi / donnees mobiles) ou de serveur.")
                    return
            except requests.RequestException:
                continue
        raise CommandError("Impossible de lire l'IP publique (pas de reseau ?).")
