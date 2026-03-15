from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, ExchangeAPIKey


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display  = ("username", "email", "telegram_id", "notify_signals", "min_cqs_notify", "is_staff")
    fieldsets     = UserAdmin.fieldsets + (
        ("CandleScout Settings", {"fields": ("telegram_id", "telegram_chat", "notify_signals", "min_cqs_notify")}),
    )


@admin.register(ExchangeAPIKey)
class ExchangeAPIKeyAdmin(admin.ModelAdmin):
    list_display  = ("user", "exchange", "api_key", "is_testnet", "is_active", "created_at", "last_used")
    list_filter   = ("exchange", "is_testnet", "is_active")
    readonly_fields = ("created_at", "last_used", "_api_secret_encrypted")
