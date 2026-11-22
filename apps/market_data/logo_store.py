"""Acces base de donnees pour les logos : lecture, telechargement a la demande, prechauffage."""
import threading
import time

from django.conf import settings
from django.db import close_old_connections

from . import logos
from .models import CoinLogo

_miss = {}          # symbole -> instant du dernier echec (on ne re-essaie pas avant 6 h)
_warm_started = False


def get_logo(symbol):
    """Retourne (octets, content_type) ou None. Telecharge et memorise si absent."""
    base = logos.clean_base(symbol)
    if not base:
        return None
    obj = CoinLogo.objects.filter(symbol=base).first()
    if obj:
        return bytes(obj.data), obj.content_type
    if time.time() - _miss.get(base, 0) < 6 * 3600:
        return None
    got = logos.fetch_logo(base, api_key=settings.COINGECKO_API_KEY)
    if not got:
        _miss[base] = time.time()
        return None
    data, ctype, src = got
    CoinLogo.objects.update_or_create(symbol=base, defaults={"content_type": ctype, "data": data, "source": src[:300]})
    return data, ctype


def warm(symbols):
    """Prechauffe les logos des paires affichees, en arriere-plan (une seule fois par processus)."""
    global _warm_started
    if _warm_started:
        return
    _warm_started = True

    def work():
        try:
            for s in symbols:
                try:
                    get_logo(s)
                except Exception:
                    continue
                time.sleep(0.2)
        finally:
            close_old_connections()

    threading.Thread(target=work, daemon=True).start()
