from django.contrib import admin
from .models import TradingSignal, SignalOutcome


@admin.register(TradingSignal)
class TradingSignalAdmin(admin.ModelAdmin):
    list_display  = ("symbol", "timestamp", "cqs_final", "confidence", "risk_reward", "is_suspicious", "created_at")
    list_filter   = ("symbol", "confidence", "is_suspicious")
    search_fields = ("symbol",)
    ordering      = ("-timestamp",)
    readonly_fields = ("signal_id", "created_at")


@admin.register(SignalOutcome)
class SignalOutcomeAdmin(admin.ModelAdmin):
    list_display = ("signal", "outcome_time", "pnl_pct", "hit_tp1", "hit_tp2", "hit_sl")
    list_filter  = ("hit_tp1", "hit_tp2", "hit_sl")
