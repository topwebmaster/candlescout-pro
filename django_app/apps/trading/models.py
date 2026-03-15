import uuid
from django.db import models


class Position(models.Model):

    class Status(models.TextChoices):
        OPEN   = "open",   "Open"
        CLOSED = "closed", "Closed"

    class Side(models.TextChoices):
        LONG  = "long",  "Long"
        SHORT = "short", "Short"

    class ExitReason(models.TextChoices):
        TP1         = "TP1",         "Take Profit 1"
        TP2         = "TP2",         "Take Profit 2"
        SL          = "SL",          "Stop Loss"
        TRAILING    = "TRAILING",    "Trailing Stop"
        MANUAL      = "MANUAL",      "Manual Close"
        LIQUIDATION = "LIQUIDATION", "Liquidation"

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    signal        = models.ForeignKey(
        "signals.TradingSignal", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="positions"
    )
    exchange      = models.CharField(max_length=10)  # bybit / okx
    symbol        = models.CharField(max_length=20, db_index=True)
    side          = models.CharField(max_length=5, choices=Side.choices)
    qty           = models.DecimalField(max_digits=18, decimal_places=4)
    leverage      = models.IntegerField(default=1)

    entry_price   = models.DecimalField(max_digits=20, decimal_places=8)
    current_sl    = models.DecimalField(max_digits=20, decimal_places=8)
    take_profit_1 = models.DecimalField(max_digits=20, decimal_places=8)
    take_profit_2 = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)

    status        = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN, db_index=True)
    tp1_closed    = models.BooleanField(default=False)
    be_moved      = models.BooleanField(default=False)

    open_time     = models.DateTimeField(auto_now_add=True)
    close_time    = models.DateTimeField(null=True, blank=True)
    exit_price    = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    exit_reason   = models.CharField(max_length=15, choices=ExitReason.choices, null=True, blank=True)

    realised_pnl   = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    unrealised_pnl = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    fees_paid      = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    net_pnl        = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)

    class Meta:
        db_table = "positions"
        ordering = ["-open_time"]
        indexes  = [
            models.Index(fields=["status", "exchange"]),
            models.Index(fields=["symbol", "-open_time"]),
        ]

    def __str__(self) -> str:
        return f"{self.exchange.upper()} {self.symbol} {self.side.upper()} {self.status}"


class OrderLog(models.Model):
    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    position       = models.ForeignKey(Position, on_delete=models.CASCADE, related_name="orders")
    exchange       = models.CharField(max_length=10)
    exchange_oid   = models.CharField(max_length=64)
    client_oid     = models.CharField(max_length=64, db_index=True)
    symbol         = models.CharField(max_length=20)
    side           = models.CharField(max_length=5)
    order_type     = models.CharField(max_length=10)
    qty            = models.DecimalField(max_digits=18, decimal_places=4)
    price          = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    filled_qty     = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    avg_fill_price = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    status         = models.CharField(max_length=20)
    fee            = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    created_at     = models.DateTimeField(auto_now_add=True)
    filled_at      = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "orders_log"
        indexes  = [models.Index(fields=["exchange_oid"])]


class DailyPnL(models.Model):
    date             = models.DateField(primary_key=True)
    starting_balance = models.DecimalField(max_digits=18, decimal_places=4)
    ending_balance   = models.DecimalField(max_digits=18, decimal_places=4)
    realised_pnl     = models.DecimalField(max_digits=18, decimal_places=4)
    fees_paid        = models.DecimalField(max_digits=18, decimal_places=4)
    trades_count     = models.IntegerField(default=0)
    win_count        = models.IntegerField(default=0)
    loss_count       = models.IntegerField(default=0)
    win_rate         = models.FloatField(default=0.0)
    max_drawdown     = models.FloatField(default=0.0)

    class Meta:
        db_table = "daily_pnl"
        ordering = ["-date"]
