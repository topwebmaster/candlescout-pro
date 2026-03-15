import uuid
from django.db import models


class TradingSignal(models.Model):

    class ConfidenceLevel(models.TextChoices):
        HIGH   = "HIGH",   "High (CQS >= 75)"
        MEDIUM = "MEDIUM", "Medium (CQS 60-74)"
        LOW    = "LOW",    "Low (CQS 45-59)"

    signal_id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candle_analysis = models.OneToOneField(
        "candles.CandleAnalysis", on_delete=models.CASCADE, related_name="signal"
    )
    symbol          = models.CharField(max_length=20, db_index=True)
    timestamp       = models.DateTimeField(db_index=True)
    timeframe       = models.CharField(max_length=5, default="15m")

    entry_price     = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss       = models.DecimalField(max_digits=20, decimal_places=8)
    take_profit_1   = models.DecimalField(max_digits=20, decimal_places=8)
    take_profit_2   = models.DecimalField(max_digits=20, decimal_places=8, null=True, blank=True)
    risk_reward     = models.FloatField()

    cqs_final       = models.FloatField(db_index=True)
    ml_probability  = models.FloatField(null=True, blank=True)
    confidence      = models.CharField(max_length=10, choices=ConfidenceLevel.choices)
    detected_patterns = models.JSONField(default=list)
    is_suspicious   = models.BooleanField(default=False)

    created_at      = models.DateTimeField(auto_now_add=True)
    notified_at     = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "trading_signals"
        ordering = ["-timestamp"]
        indexes  = [
            models.Index(fields=["symbol", "-timestamp"]),
            models.Index(fields=["-cqs_final"]),
        ]

    def __str__(self) -> str:
        return f"Signal {self.symbol} CQS:{self.cqs_final:.0f} @ {self.timestamp}"


class SignalOutcome(models.Model):
    """Outcome recorded automatically 5 candles after signal."""
    signal        = models.OneToOneField(TradingSignal, on_delete=models.CASCADE, related_name="outcome")
    outcome_time  = models.DateTimeField()
    exit_price    = models.DecimalField(max_digits=20, decimal_places=8)
    pnl_pct       = models.FloatField()
    hit_tp1       = models.BooleanField(default=False)
    hit_tp2       = models.BooleanField(default=False)
    hit_sl        = models.BooleanField(default=False)
    max_favorable = models.FloatField(help_text="Max favorable excursion %")
    max_adverse   = models.FloatField(help_text="Max adverse excursion %")

    class Meta:
        db_table = "signal_outcomes"
