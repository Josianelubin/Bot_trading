from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("trades/", include("apps.trade_approval.urls")),
    path("analysis/", include("apps.market_scanner.urls")),
    path("live/", include("apps.market_scanner.live_urls")),
    path("", include("apps.dashboard.urls")),
]
