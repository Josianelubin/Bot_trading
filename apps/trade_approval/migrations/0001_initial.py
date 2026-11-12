from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="TradeProposal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("symbol", models.CharField(max_length=32)),
                ("direction", models.CharField(max_length=5)),
                ("mode", models.CharField(max_length=4)),
                ("entry", models.FloatField()),
                ("stop_loss", models.FloatField()),
                ("take_profit", models.FloatField()),
                ("leverage", models.PositiveIntegerField()),
                ("capital_usdt", models.FloatField()),
                ("score_technical", models.PositiveIntegerField()),
                ("payload", models.JSONField(default=dict)),
                ("status", models.CharField(default="pending", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
