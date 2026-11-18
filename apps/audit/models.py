from django.db import models


class SystemFlag(models.Model):
    key = models.CharField(max_length=40, unique=True)
    value = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)


def emergency_active():
    return SystemFlag.objects.filter(key="emergency_stop", value=True).exists()
