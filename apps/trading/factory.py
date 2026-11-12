from django.conf import settings

from .gate_private import GateTradeError, GateTrader


def trader_from_settings():
    """DEMO -> cles et URL du TESTNET uniquement. REAL -> exige KPS_ALLOW_LIVE=true."""
    if settings.TRADING_MODE == "REAL":
        if not settings.ALLOW_LIVE:
            raise GateTradeError("Mode REAL verrouille (KPS_ALLOW_LIVE != true)")
        key, secret, base = settings.GATEIO_API_KEY, settings.GATEIO_API_SECRET, "https://api.gateio.ws/api/v4"
    else:
        key, secret, base = (settings.GATEIO_TESTNET_API_KEY, settings.GATEIO_TESTNET_API_SECRET,
                             settings.GATEIO_TESTNET_BASE_URL)
    if not key or not secret:
        raise GateTradeError("Cles API Gate.io absentes pour le mode " + settings.TRADING_MODE)
    return GateTrader(key, secret, base)
