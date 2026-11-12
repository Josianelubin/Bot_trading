from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("trade_approval", "0001_initial")]
    operations = [
        migrations.AddField("tradeproposal", "exec_status", models.CharField(default="none", max_length=10)),
        migrations.AddField("tradeproposal", "gate_order_id", models.CharField(blank=True, default="", max_length=40)),
        migrations.AddField("tradeproposal", "sl_order_id", models.CharField(blank=True, default="", max_length=40)),
        migrations.AddField("tradeproposal", "tp_order_id", models.CharField(blank=True, default="", max_length=40)),
        migrations.AddField("tradeproposal", "fill_price", models.FloatField(blank=True, null=True)),
        migrations.AddField("tradeproposal", "size_contracts", models.IntegerField(blank=True, null=True)),
        migrations.AddField("tradeproposal", "net_pnl", models.FloatField(blank=True, null=True)),
        migrations.AddField("tradeproposal", "exec_log", models.JSONField(default=list)),
        migrations.AddField("tradeproposal", "executed_at", models.DateTimeField(blank=True, null=True)),
        migrations.AddField("tradeproposal", "closed_at", models.DateTimeField(blank=True, null=True)),
    ]
