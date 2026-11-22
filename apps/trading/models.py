from django.db import models


class BotStatus(models.Model):
    """Etat unique (pk=1) du moteur d'analyse automatique : verrou (lease), dernier cycle, erreurs."""
    enabled = models.BooleanField(default=True)
    run_requested = models.BooleanField(default=False)
    running = models.BooleanField(default=False)
    owner = models.CharField(max_length=80, blank=True, default="")
    heartbeat = models.DateTimeField(null=True, blank=True)
    last_started_at = models.DateTimeField(null=True, blank=True)
    last_cycle_at = models.DateTimeField(null=True, blank=True)
    cycles = models.PositiveIntegerField(default=0)
    last_summary = models.TextField(blank=True, default="")
    last_error = models.TextField(blank=True, default="")
