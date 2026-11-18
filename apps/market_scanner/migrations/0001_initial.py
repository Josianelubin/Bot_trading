from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="SymbolAnalysis",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("symbol", models.CharField(max_length=32, unique=True)),
                ("price", models.FloatField(blank=True, null=True)),
                ("change_pct", models.FloatField(blank=True, null=True)),
                ("direction", models.CharField(default="NEUTRE", max_length=6)),
                ("score", models.PositiveIntegerField(default=0)),
                ("payload", models.JSONField(default=dict)),
                ("chart_png", models.BinaryField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-score", "symbol"]},
        ),
    ]
