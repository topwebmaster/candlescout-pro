from django.db import models
from timescale.db.models.fields import TimescaleDateTimeField
from timescale.db.models.managers import TimescaleManager


class Candle15m(models.Model):
    """
    15-minute OHLCV candle stored as a TimescaleDB hypertable.
    Partitioned by week for efficient time-range queries.
    """
    time         = TimescaleDateTimeField(interval="1 week", db_index=True)
    symbol       = models.CharField(max_length=20, db_index=True)
    open         = models.DecimalField(max_digits=20, decimal_places=8)
    high         = models.DecimalField(max_digits=20, decimal_places=8)
    low          = models.DecimalField(max_digits=20, decimal_places=8)
    close        = models.DecimalField(max_digits=20, decimal_places=8)
    volume       = models.DecimalField(max_digits=24, decimal_places=4)
    quote_volume = models.DecimalField(max_digits=24, decimal_places=4)
    trades_count = models.IntegerField(default=0)

    objects = TimescaleManager()

    class Meta:
        db_table        = "candles_15m"
        unique_together = ("time", "symbol")
        ordering        = ["-time"]
        indexes         = [models.Index(fields=["symbol", "-time"])]

    def __str__(self) -> str:
        return f"{self.symbol} {self.time} O:{self.open} C:{self.close}"

    @property
    def body(self):
        return self.close - self.open

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def upper_wick(self):
        return self.high - max(self.open, self.close)

    @property
    def lower_wick(self):
        return min(self.open, self.close) - self.low

    @property
    def total_range(self):
        return self.high - self.low


class CandleTickAgg(models.Model):
    """
    Aggregated tick data per 15m candle.
    Stores delta volume and OFI for Layer 3 analysis.
    """
    time        = TimescaleDateTimeField(interval="1 week")
    symbol      = models.CharField(max_length=20)
    buy_volume  = models.DecimalField(max_digits=24, decimal_places=4)
    sell_volume = models.DecimalField(max_digits=24, decimal_places=4)
    delta       = models.DecimalField(max_digits=24, decimal_places=4)
    delta_ratio = models.DecimalField(max_digits=8, decimal_places=6)
    avg_ofi     = models.DecimalField(max_digits=8, decimal_places=6)
    trades_buy  = models.IntegerField(default=0)
    trades_sell = models.IntegerField(default=0)

    objects = TimescaleManager()

    class Meta:
        db_table        = "candle_tick_agg"
        unique_together = ("time", "symbol")


class CandleAnalysis(models.Model):
    """Result of the 5-layer analysis pipeline for a single candle."""

    class CandleClass(models.TextChoices):
        STRONG_BULLISH   = "STRONG_BULLISH",   "Strong Bullish"
        MODERATE_BULLISH = "MODERATE_BULLISH", "Moderate Bullish"
        WEAK_BULLISH     = "WEAK_BULLISH",     "Weak Bullish"
        DOJI             = "DOJI",             "Doji"
        BEARISH          = "BEARISH",          "Bearish"
        INVALID          = "INVALID",          "Invalid"

    class MarketRegime(models.TextChoices):
        TREND   = "TREND",   "Trend"
        NEUTRAL = "NEUTRAL", "Neutral"
        CHAOS   = "CHAOS",   "Chaos"

    candle            = models.OneToOneField(
        Candle15m, on_delete=models.CASCADE, related_name="analysis"
    )
    # Layer 1
    candle_class      = models.CharField(max_length=20, choices=CandleClass.choices)
    bss               = models.FloatField(help_text="Body Strength Score 0-100")
    # Layer 2
    morphology_type   = models.CharField(max_length=30)
    z_score           = models.FloatField()
    l2_score          = models.SmallIntegerField(default=0)
    # Layer 3
    vol_ratio         = models.FloatField()
    vpc               = models.FloatField()
    vwap              = models.DecimalField(max_digits=20, decimal_places=8)
    vwap_distance_pct = models.FloatField()
    delta_ratio       = models.FloatField()
    ofi               = models.FloatField()
    fractal_dimension = models.FloatField()
    market_regime     = models.CharField(max_length=10, choices=MarketRegime.choices)
    is_suspicious     = models.BooleanField(default=False)
    l3_score          = models.SmallIntegerField(default=0)
    # Layer 4
    detected_patterns = models.JSONField(default=list)
    wavelet_slope     = models.FloatField(null=True, blank=True)
    wavelet_confirmed = models.BooleanField(default=False)
    l4_score          = models.SmallIntegerField(default=0)
    # Layer 5 / Final
    cqs_base          = models.SmallIntegerField()
    ml_probability    = models.FloatField(null=True, blank=True)
    cqs_final         = models.FloatField()
    penalties         = models.SmallIntegerField(default=0)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "candle_analysis"
        indexes  = [models.Index(fields=["-created_at"])]

    def __str__(self) -> str:
        return f"{self.candle.symbol} CQS:{self.cqs_final:.1f} [{self.candle_class}]"
