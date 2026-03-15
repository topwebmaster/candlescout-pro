from django.contrib import admin
from .models import Position, OrderLog, DailyPnL


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display  = ("symbol", "exchange", "side", "status", "entry_price", "unrealised_pnl", "net_pnl", "open_time")
    list_filter   = ("status", "exchange", "side", "exit_reason")
    search_fields = ("symbol",)
    ordering      = ("-open_time",)
    readonly_fields = ("id", "open_time")


@admin.register(DailyPnL)
class DailyPnLAdmin(admin.ModelAdmin):
    list_display = ("date", "starting_balance", "ending_balance", "realised_pnl", "trades_count", "win_rate", "max_drawdown")
    ordering     = ("-date",)
