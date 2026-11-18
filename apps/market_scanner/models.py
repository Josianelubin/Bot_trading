from django.db import models


class SymbolAnalysis(models.Model):
    """Derniere analyse de chaque symbole (image stockee en base, pas sur le disque du serveur)."""
    symbol = models.CharField(max_length=32, unique=True)
    price = models.FloatField(null=True, blank=True)
    change_pct = models.FloatField(null=True, blank=True)
    direction = models.CharField(max_length=6, default="NEUTRE")
    score = models.PositiveIntegerField(default=0)
    payload = models.JSONField(default=dict)
    chart_png = models.BinaryField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-score", "symbol"]
