from django.urls import path

from . import live_views as v

app_name = "live"

urlpatterns = [
    path("", v.live, name="page"),
    path("api/candles/", v.candles_api, name="candles"),
    path("api/scan/", v.scan_api, name="scan"),
    path("api/prices/", v.prices_api, name="prices"),
    path("api/account/", v.account_api, name="account"),
    path("api/emergency/", v.emergency_api, name="emergency"),
    path("api/backtest/", v.backtest_api, name="backtest"),
    path("api/contracts/", v.contracts_api, name="contracts"),
    path("api/performance/", v.performance_api, name="performance"),
    path("api/close/<int:pk>/", v.close_api, name="close"),
]
