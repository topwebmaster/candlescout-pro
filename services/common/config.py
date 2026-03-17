"""
Configuration management for CandleScout Pro services.
"""

import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    DB_NAME: str = "candlescout"
    DB_USER: str = "candlescout"
    DB_PASSWORD: str = "changeme"
    DB_HOST: str = "timescaledb"
    DB_PORT: int = 5432
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    REDIS_CACHE_DB: int = 1
    REDIS_PUBSUB_DB: int = 2
    REDIS_MAX_CONNECTIONS: int = 50
    
    # Binance
    BINANCE_WS_URL: str = "wss://stream.binance.com:9443/ws"
    BINANCE_REST_URL: str = "https://api.binance.com/api/v3"
    BINANCE_SYMBOL: str = "SOLUSDT"
    BINANCE_INTERVAL: str = "15m"
    BINANCE_RECONNECT_DELAYS: str = "1,2,5,10,30"
    BINANCE_BACKFILL_LIMIT: int = 1000
    
    # Bybit
    BYBIT_API_KEY: str = ""
    BYBIT_API_SECRET: str = ""
    BYBIT_TESTNET: bool = True
    BYBIT_BASE_URL: str = "https://api-testnet.bybit.com"
    BYBIT_LEVERAGE: int = 5
    BYBIT_RECV_WINDOW: int = 5000
    
    # OKX
    OKX_API_KEY: str = ""
    OKX_API_SECRET: str = ""
    OKX_PASSPHRASE: str = ""
    OKX_TESTNET: bool = True
    OKX_BASE_URL: str = "https://www.okx.com"
    OKX_LEVERAGE: int = 5
    
    # Risk Management
    RISK_PER_TRADE_PCT: float = 1.0
    MAX_OPEN_POSITIONS: int = 3
    MAX_DAILY_LOSS_PCT: float = 2.0
    MAX_DRAWDOWN_PCT: float = 5.0
    MIN_CQS_TO_TRADE: int = 65
    MIN_RR_RATIO: float = 1.5
    COOLDOWN_AFTER_LOSS_MIN: int = 60
    PAPER_TRADING: bool = True
    MAX_POSITION_SIZE_PCT: float = 20.0
    
    # Position Management
    MONITORING_INTERVAL_SEC: int = 15
    TRAILING_STOP_ENABLED: bool = True
    TRAILING_STOP_ACTIVATION_PCT: float = 1.0
    TRAILING_STOP_DISTANCE_PCT: float = 0.5
    BREAKEVEN_ACTIVATION_PCT: float = 0.5
    BREAKEVEN_OFFSET_PCT: float = 0.1
    TP1_CLOSE_PCT: int = 50
    TP2_CLOSE_PCT: int = 100
    
    # Telegram
    TELEGRAM_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    NOTIFY_ON_SIGNAL: bool = True
    NOTIFY_ON_ENTRY: bool = True
    NOTIFY_ON_EXIT: bool = True
    NOTIFY_ON_SL_HIT: bool = True
    NOTIFY_ON_BE_MOVE: bool = True
    NOTIFY_ON_TRAILING_UPDATE: bool = True
    DAILY_REPORT_TIME: str = "23:55"
    DAILY_REPORT_ENABLED: bool = True
    
    # CQS Thresholds
    CQS_HIGH_THRESHOLD: int = 80
    CQS_MEDIUM_THRESHOLD: int = 60
    CQS_LOW_THRESHOLD: int = 45
    CQS_SIGNAL_THRESHOLD: int = 60
    
    # ML Model
    ML_MODEL_PATH: str = "/models/xgboost_latest.ubj"
    ML_RETRAIN_MIN_SAMPLES: int = 500
    ML_RETRAIN_SCHEDULE: str = "00:05"
    ML_MIN_AUC: float = 0.58
    ML_MIN_PRECISION: float = 0.55
    ML_MIN_RECALL: float = 0.45
    ML_MIN_F1: float = 0.50
    ML_INFERENCE_TIMEOUT_MS: int = 50
    
    # Analysis Pipeline - Layer 1
    BSS_STRONG_THRESHOLD: int = 70
    BSS_MODERATE_THRESHOLD: int = 40
    BSS_WEAK_THRESHOLD: int = 10
    DOJI_THRESHOLD: float = 0.0005
    
    # Analysis Pipeline - Layer 2
    Z_SCORE_HISTORY_CANDLES: int = 50
    MARUBOZU_SHADOW_THRESHOLD: float = 0.05
    MARUBOZU_BSS_THRESHOLD: int = 90
    HAMMER_LOWER_SHADOW_RATIO: float = 2.0
    HAMMER_UPPER_SHADOW_RATIO: float = 0.3
    
    # Analysis Pipeline - Layer 3
    VOLUME_HISTORY_CANDLES: int = 20
    ATR_PERIOD: int = 14
    EXTREME_VOLUME_THRESHOLD: float = 3.0
    HIGH_VOLUME_THRESHOLD: float = 2.0
    LOW_VOLUME_THRESHOLD: float = 0.5
    VWAP_THRESHOLD_PCT: float = 0.5
    SUSPICIOUS_DELTA_THRESHOLD: float = -0.2
    OFI_THRESHOLD: float = 0.3
    FRACTAL_DIMENSION_CANDLES: int = 40
    
    # Analysis Pipeline - Layer 4
    WAVELET_TYPE: str = "db4"
    WAVELET_LEVEL: int = 3
    PATTERN_SCORE_CAP: int = 35
    
    # Analysis Pipeline - Layer 5
    CQS_BASE_WEIGHT: float = 0.7
    ML_PROBABILITY_WEIGHT: float = 0.3
    
    # API Service
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 4
    API_RELOAD: bool = False
    API_LOG_LEVEL: str = "info"
    API_CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"
    API_MAX_CONNECTIONS: int = 100
    
    # Monitoring
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    
    # Performance
    CANDLE_PROCESSING_TIMEOUT_MS: int = 500
    SIGNAL_GENERATION_TIMEOUT_MS: int = 500
    DB_WRITE_TIMEOUT_MS: int = 100
    WS_RECONNECT_TIMEOUT_SEC: int = 60
    MAX_CANDLE_LAG_MIN: int = 20
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @property
    def database_url(self) -> str:
        """Get PostgreSQL connection URL."""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def async_database_url(self) -> str:
        """Get async PostgreSQL connection URL."""
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def reconnect_delays(self) -> List[int]:
        """Get reconnect delays as list of integers."""
        return [int(x) for x in self.BINANCE_RECONNECT_DELAYS.split(",")]
    
    @property
    def cors_origins(self) -> List[str]:
        """Get CORS origins as list."""
        return [x.strip() for x in self.API_CORS_ORIGINS.split(",")]


# Global settings instance
settings = Settings()
