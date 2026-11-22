from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="BotStatus",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("enabled", models.BooleanField(default=True)),
                ("run_requested", models.BooleanField(default=False)),
                ("running", models.BooleanField(default=False)),
                ("owner", models.CharField(blank=True, default="", max_length=80)),
                ("heartbeat", models.DateTimeField(blank=True, null=True)),
                ("last_started_at", models.DateTimeField(blank=True, null=True)),
                ("last_cycle_at", models.DateTimeField(blank=True, null=True)),
                ("cycles", models.PositiveIntegerField(default=0)),
                ("last_summary", models.TextField(blank=True, default="")),
                ("last_error", models.TextField(blank=True, default="")),
            ],
        ),
    ]
