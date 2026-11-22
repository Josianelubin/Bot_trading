from django.db import models


class CoinLogo(models.Model):
    """Logo d'une crypto, stocke en base (pas sur le disque du serveur : Render l'efface)."""
    symbol = models.CharField(max_length=20, unique=True)
    content_type = models.CharField(max_length=30)
    data = models.BinaryField()
    source = models.CharField(max_length=300, blank=True, default="")
    fetched_at = models.DateTimeField(auto_now=True)
