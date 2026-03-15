from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings


class User(AbstractUser):
    """Extended user model with Telegram notification settings."""
    telegram_id    = models.BigIntegerField(null=True, blank=True, unique=True)
    telegram_chat  = models.CharField(max_length=50, null=True, blank=True)
    notify_signals = models.BooleanField(default=True)
    min_cqs_notify = models.IntegerField(default=65)

    class Meta:
        db_table = "auth_user"

    def __str__(self) -> str:
        return self.username


class ExchangeAPIKey(models.Model):
    """
    Encrypted exchange API keys.
    The secret is never stored in plaintext — encrypted via Fernet (AES-128-CBC).
    """

    class Exchange(models.TextChoices):
        BYBIT = "bybit", "Bybit"
        OKX   = "okx",   "OKX"

    user         = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_keys")
    exchange     = models.CharField(max_length=10, choices=Exchange.choices)
    api_key      = models.CharField(max_length=128)
    _api_secret_encrypted = models.BinaryField()
    passphrase   = models.CharField(max_length=128, blank=True)
    is_testnet   = models.BooleanField(default=False)
    is_active    = models.BooleanField(default=True)
    ip_whitelist = models.GenericIPAddressField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    last_used    = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table        = "exchange_api_keys"
        unique_together = ("user", "exchange", "is_testnet")

    def set_secret(self, raw_secret: str) -> None:
        from cryptography.fernet import Fernet
        f = Fernet(settings.FERNET_KEY)
        self._api_secret_encrypted = f.encrypt(raw_secret.encode())

    def get_secret(self) -> str:
        from cryptography.fernet import Fernet
        f = Fernet(settings.FERNET_KEY)
        return f.decrypt(bytes(self._api_secret_encrypted)).decode()

    def __str__(self) -> str:
        return f"{self.user.username} — {self.exchange} ({'testnet' if self.is_testnet else 'live'})"
