from django.conf import settings


def kps_mode(request):
    return {"KPS_MODE": settings.TRADING_MODE, "KPS_MARGIN": settings.MARGIN_MODE}
