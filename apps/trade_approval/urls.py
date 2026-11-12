from django.urls import path

from . import views

app_name = "trade_approval"

urlpatterns = [
    path("", views.proposals, name="proposals"),
    path("positions/", views.positions, name="positions"),
    path("<int:pk>/", views.detail, name="detail"),
]
