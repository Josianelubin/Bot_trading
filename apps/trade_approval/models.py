from django.db import models


class TradeProposal(models.Model):
    symbol = models.CharField(max_length=32)
    direction = models.CharField(max_length=5)
    mode = models.CharField(max_length=4)
    entry = models.FloatField()
    stop_loss = models.FloatField()
    take_profit = models.FloatField()
    leverage = models.PositiveIntegerField()
    capital_usdt = models.FloatField()
    score_technical = models.PositiveIntegerField()
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=10, default="pending")  # pending/accepted/rejected/expired
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    decided_at = models.DateTimeField(null=True, blank=True)
    # --- execution Gate.io ---
    exec_status = models.CharField(max_length=10, default="none")  # none/executing/open/closed/error
    gate_order_id = models.CharField(max_length=40, blank=True, default="")
    sl_order_id = models.CharField(max_length=40, blank=True, default="")
    tp_order_id = models.CharField(max_length=40, blank=True, default="")
    fill_price = models.FloatField(null=True, blank=True)
    size_contracts = models.IntegerField(null=True, blank=True)
    net_pnl = models.FloatField(null=True, blank=True)
    exec_log = models.JSONField(default=list)
    executed_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"#{self.pk} {self.symbol} {self.direction} [{self.status}]"
