from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="CoinLogo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("symbol", models.CharField(max_length=20, unique=True)),
                ("content_type", models.CharField(max_length=30)),
                ("data", models.BinaryField()),
                ("source", models.CharField(blank=True, default="", max_length=300)),
                ("fetched_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
