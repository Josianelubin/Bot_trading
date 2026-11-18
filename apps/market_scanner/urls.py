from django.urls import path

from . import views

app_name = "market_scanner"

urlpatterns = [
    path("", views.analysis_list, name="list"),
    path("<str:symbol>/", views.analysis_detail, name="detail"),
    path("<str:symbol>/chart.png", views.chart_png, name="chart"),
    path("<str:symbol>/trade/", views.create_trade, name="create_trade"),
]
