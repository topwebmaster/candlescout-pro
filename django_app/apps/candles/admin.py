from django.contrib import admin
from .models import Candle15m, CandleTickAgg, CandleAnalysis


@admin.register(Candle15m)
class Candle15mAdmin(admin.ModelAdmin):
    list_display  = ("symbol", "time", "open", "high", "low", "close", "volume", "is_bullish")
    list_filter   = ("symbol",)
    search_fields = ("symbol",)
    ordering      = ("-time",)
    readonly_fields = ("time", "symbol")

    def is_bullish(self, obj):
        return obj.is_bullish
    is_bullish.boolean = True


@admin.register(CandleAnalysis)
class CandleAnalysisAdmin(admin.ModelAdmin):
    list_display  = ("__str__", "candle_class", "bss", "cqs_final", "is_suspicious", "market_regime", "created_at")
    list_filter   = ("candle_class", "market_regime", "is_suspicious")
    search_fields = ("candle__symbol",)
    ordering      = ("-created_at",)
    readonly_fields = ("created_at",)
