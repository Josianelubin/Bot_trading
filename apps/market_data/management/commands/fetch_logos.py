from django.core.management.base import BaseCommand, CommandError

from apps.market_data import logo_store, logos
from apps.market_data.gate_client import GateAPIError, GateClient
from apps.market_data.models import CoinLogo


class Command(BaseCommand):
    help = "Telecharge et stocke en base le vrai logo de chaque crypto des paires USDT Futures de Gate."

    def handle(self, *args, **opts):
        try:
            names = [c["name"] for c in GateClient().contracts() if not c.get("in_delisting")]
        except GateAPIError as e:
            raise CommandError(f"DONNEES INDISPONIBLES : {e}")
        bases = sorted({logos.clean_base(n) for n in names} - {None})
        have = set(CoinLogo.objects.values_list("symbol", flat=True))
        ok = miss = 0
        for b in bases:
            if b in have:
                continue
            if logo_store.get_logo(b):
                ok += 1
            else:
                miss += 1
                self.stdout.write(f"pas de logo : {b}")
        self.stdout.write(self.style.SUCCESS(f"{len(have)} deja en base, {ok} telecharges, {miss} introuvables sur {len(bases)} cryptos"))
