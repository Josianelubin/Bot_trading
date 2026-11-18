from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="NewsItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("url", models.CharField(max_length=500, unique=True)),
                ("title", models.CharField(max_length=500)),
                ("source", models.CharField(blank=True, default="", max_length=120)),
                ("published_at", models.DateTimeField()),
                ("fetched_at", models.DateTimeField(auto_now_add=True)),
                ("symbols", models.JSONField(default=list)),
                ("sentiment", models.CharField(max_length=10)),
                ("importance", models.PositiveSmallIntegerField(default=1)),
                ("reliability", models.CharField(default="moyenne", max_length=10)),
            ],
            options={"ordering": ["-published_at"]},
        ),
    ]
