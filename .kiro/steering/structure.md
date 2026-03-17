# Project Structure & Organization

## Directory Layout

```
candlescout-pro/
├── django_app/              # Django 6.0 application (legacy/admin)
│   ├── apps/                # Django apps (accounts, candles, ml, signals, trading)
│   ├── settings/            # Split settings (base, development, production, testing)
│   ├── manage.py            # Django management CLI
│   ├── celery_app.py        # Celery configuration
│   └── urls.py              # URL routing
│
├── services/                # Microservices architecture
│   ├── common/              # Shared utilities and configuration
│   │   ├── config.py        # Centralized pydantic settings
│   │   └── __init__.py
│   │
│   ├── data_ingestion/      # Binance WebSocket data collector
│   ├── analysis_pipeline/   # 5-layer candle analysis
│   ├── ml_service/          # XGBoost training & inference
│   ├── signal_dispatcher/   # Signal routing (Telegram/WebSocket)
│   ├── trade_executor/      # Order execution (Bybit/OKX)
│   ├── position_manager/    # Position monitoring & management
│   ├── api_service/         # FastAPI REST + WebSocket API
│   └── README.md            # Services architecture documentation
│
├── models/                  # ML model storage (mounted volume)
├── .kiro/                   # Kiro configuration
│   ├── specs/               # Feature specs
│   └── steering/            # Steering documents (this file)
│
├── init_db.sql              # TimescaleDB schema (hypertables, indexes)
├── docker-compose.yml       # All services orchestration
├── Makefile                 # Development commands
├── pyproject.toml           # Python project metadata
├── requirements.txt         # Python dependencies
├── .env.example             # Configuration template
└── README.md                # Project overview
```

## Architecture Patterns

### Microservices Communication

**Event-Driven (Redis Pub/Sub)**:
- `candle:closed:{symbol}` - New candle available for analysis
- `signal:generated:{symbol}` - Trading signal created

**Shared Data (TimescaleDB)**:
- Hypertables: candles_15m, candle_analysis, trading_signals, orders_log
- Regular tables: positions, ml_models, daily_pnl

**HTTP/WebSocket**: External API access via api_service

### Service Responsibilities

Each microservice is single-purpose:
- **data_ingestion**: Collect data only
- **analysis_pipeline**: Process candles only
- **ml_service**: ML inference only
- **signal_dispatcher**: Route signals only
- **trade_executor**: Execute orders only
- **position_manager**: Monitor positions only
- **api_service**: Serve API only

### Configuration Pattern

All services use `services/common/config.py`:
- Load from environment variables
- Type-safe with pydantic-settings
- Single source of truth
- No hardcoded values

### Django Apps Organization

Django apps follow domain-driven design:
- `accounts`: User management
- `candles`: Candle data models
- `signals`: Signal models
- `trading`: Order and position models
- `ml`: ML model registry

Each app contains: `models.py`, `admin.py`, `apps.py`

## File Naming Conventions

- **Python modules**: snake_case (e.g., `data_ingestion.py`)
- **Classes**: PascalCase (e.g., `CandleAnalyzer`)
- **Functions/variables**: snake_case (e.g., `calculate_bss`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `MAX_OPEN_POSITIONS`)
- **Service directories**: snake_case (e.g., `analysis_pipeline/`)
- **Docker containers**: kebab-case prefix (e.g., `candlescout-api-service`)

## Code Organization Rules

**Service Entry Points**: Each service has `main.py` with:
- Async main() function
- Logging setup with loguru
- Graceful shutdown handling
- Health check mechanism

**Shared Code**: Place in `services/common/` for cross-service utilities

**Django Models**: Use django-timescaledb for time-series tables

**Async Code**: Use asyncio, aiohttp, asyncpg for I/O operations

**Error Handling**: Use tenacity for retries, loguru for structured logging

## Testing Structure

```
tests/
├── unit/            # Fast, isolated tests (no DB/Redis)
├── integration/     # Tests with DB + Redis (testcontainers)
├── e2e/             # Full system tests
└── backtesting/     # Strategy backtesting (marked as slow)
```

Use pytest markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.e2e`, `@pytest.mark.slow`

## Docker Patterns

- Each service has its own Dockerfile
- Base image: `python:3.11-slim`
- Health checks defined in docker-compose.yml
- Services depend on infrastructure (timescaledb, redis)
- Named volumes for persistence
- Custom network for service isolation

## Import Conventions

**Django**: Use absolute imports from app root
```python
from apps.candles.models import Candle
from django_app.settings import settings
```

**Services**: Use relative imports within service, absolute for common
```python
from services.common.config import settings
from .analyzer import CandleAnalyzer  # Within same service
```

## Environment Variables

All configuration via `.env` file:
- Database credentials (DB_NAME, DB_USER, DB_PASSWORD)
- API keys (BYBIT_API_KEY, OKX_API_KEY, TELEGRAM_TOKEN)
- Risk parameters (RISK_PER_TRADE_PCT, MAX_OPEN_POSITIONS)
- Feature flags (PAPER_TRADING, TRAILING_STOP_ENABLED)

Never hardcode secrets or configuration values.
