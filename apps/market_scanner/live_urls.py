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
    path("api/analysis-image/", v.analysis_image_api, name="analysis_image"),
    path("api/analysis-image/send/", v.analysis_image_send_api, name="analysis_image_send"),
    path("photos/", v.photos_page, name="photos"),
    path("api/bot/", v.bot_api, name="bot"),
    path("api/bot/control/", v.bot_control_api, name="bot_control"),
    path("logo/<str:base>.png", v.logo_api, name="logo"),
    path("api/performance/", v.performance_api, name="performance"),
    path("api/close/<int:pk>/", v.close_api, name="close"),
]
