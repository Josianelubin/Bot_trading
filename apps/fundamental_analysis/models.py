from django.db import models


class NewsItem(models.Model):
    url = models.CharField(max_length=500, unique=True)
    title = models.CharField(max_length=500)
    source = models.CharField(max_length=120, blank=True, default="")
    published_at = models.DateTimeField()
    fetched_at = models.DateTimeField(auto_now_add=True)
    symbols = models.JSONField(default=list)
    sentiment = models.CharField(max_length=10)
    importance = models.PositiveSmallIntegerField(default=1)
    reliability = models.CharField(max_length=10, default="moyenne")

    class Meta:
        ordering = ["-published_at"]
