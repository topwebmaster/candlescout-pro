# Technology Stack & Build System

## Core Technologies

**Python**: 3.11+ (3.12 preferred)

**Web Frameworks**:
- Django 6.0 - Models, admin, migrations, ORM
- FastAPI 0.115 - REST API + WebSocket server
- Tortoise-ORM - Async ORM for microservices

**Databases**:
- PostgreSQL 17 + TimescaleDB 2.x - Time-series data (hypertables)
- Redis 7.4 - Pub/sub messaging, caching, task queue

**Task Queue**: Celery 6 + Redis (queues: default, ml, reporting)

**ML/Data**: XGBoost, scikit-learn, pandas, numpy, pandas-ta, PyWavelets, SHAP

**Exchange APIs**: Bybit V5 API, OKX V5 API (aiohttp for async HTTP)

**Notifications**: aiogram, python-telegram-bot

**Testing**: pytest, pytest-django, pytest-asyncio, hypothesis (property-based testing), testcontainers

**Code Quality**: ruff (linting + formatting), mypy (type checking)

**Monitoring**: Prometheus + Grafana

**Containerization**: Docker + Docker Compose

## Project Configuration

**Dependencies**: Managed in `pyproject.toml` and `requirements.txt`

**Environment**: All configuration via `.env` file (see `.env.example`)

**Settings**: Centralized in `services/common/config.py` using pydantic-settings

## Common Commands

### Development Setup
```bash
make dev-setup          # Copy .env.example to .env
make up                 # Start all services with Docker Compose
make down               # Stop all services and remove volumes
make migrate            # Run Django migrations
make status             # Check service status
```

### Testing
```bash
make test               # Run all tests
make test-unit          # Unit tests only (fast, no external deps)
make test-integration   # Integration tests (DB + Redis)
make test-e2e           # End-to-end tests
make coverage           # Generate coverage report
pytest tests/ -v        # Direct pytest invocation
```

### Code Quality
```bash
make lint               # Run ruff linter
make format             # Format code with ruff
make typecheck          # Run mypy type checker
make clean              # Remove __pycache__, .pyc files
```

### Database Operations
```bash
make db-shell           # PostgreSQL shell
make db-backup          # Backup database
make db-restore FILE=backup.sql  # Restore from backup
```

### Redis Operations
```bash
make redis-cli          # Redis CLI
make redis-flush        # Clear all Redis data
make redis-monitor      # Monitor Redis commands
```

### Service Management
```bash
make start-data-ingestion    # Start data ingestion service
make start-analysis          # Start analysis pipeline
make start-ml                # Start ML service
make start-api               # Start API service
make logs                    # View all service logs
docker compose logs -f <service>  # View specific service logs
```

### Monitoring
```bash
make start-monitoring   # Start Prometheus + Grafana
make open-grafana       # Open Grafana (http://localhost:3000)
make open-prometheus    # Open Prometheus (http://localhost:9090)
```

## Build System Notes

- Docker Compose manages all services with health checks and dependencies
- Each microservice has its own Dockerfile (Python 3.11-slim base)
- Services auto-restart on failure (unless-stopped policy)
- Named volumes persist data (db_data, redis_data, models_data)
- Custom network (candlescout-network) for service communication
- Analysis pipeline runs with 2 replicas for load distribution

## Configuration Management

All services load configuration from environment variables via `services/common/config.py`:
- Type-safe with pydantic
- Computed properties for connection URLs
- Default values for all settings
- Single source of truth for all microservices
