# CandleScout Pro Microservices

This directory contains all microservices for the CandleScout Pro automated trading system.

## Architecture

```
services/
├── common/                  # Shared utilities and configuration
│   ├── config.py           # Centralized configuration management
│   └── __init__.py
│
├── data_ingestion/         # Collects real-time market data from Binance
│   ├── main.py
│   ├── Dockerfile
│   └── __init__.py
│
├── analysis_pipeline/      # 5-layer candle analysis (L1→L2→L3→L4→L5)
│   ├── main.py
│   ├── Dockerfile
│   └── __init__.py
│
├── ml_service/             # XGBoost model training and inference
│   ├── main.py
│   ├── Dockerfile
│   └── __init__.py
│
├── signal_dispatcher/      # Routes signals to Telegram/WebSocket/Executor
│   ├── main.py
│   ├── Dockerfile
│   └── __init__.py
│
├── trade_executor/         # Executes trades on Bybit/OKX
│   ├── main.py
│   ├── Dockerfile
│   └── __init__.py
│
├── position_manager/       # Manages open positions (trailing stops, etc.)
│   ├── main.py
│   ├── Dockerfile
│   └── __init__.py
│
└── api_service/            # FastAPI REST and WebSocket API
    ├── main.py
    ├── Dockerfile
    └── __init__.py
```

## Services Overview

### 1. Data Ingestion Service
- **Responsibility**: Collect real-time 15-minute OHLCV data from Binance
- **Technology**: Python 3.11+, asyncio, websockets, aiohttp
- **Input**: Binance WebSocket streams
- **Output**: TimescaleDB tables, Redis cache, Redis pub/sub events

### 2. Analysis Pipeline Service
- **Responsibility**: Process candles through 5 layers of analysis
- **Technology**: Python 3.11+, pandas, numpy, pandas_ta, PyWavelets
- **Input**: Redis candle:closed events
- **Output**: TimescaleDB candle_analysis, Redis signal:generated events

### 3. ML Service
- **Responsibility**: Train and serve XGBoost model for signal scoring
- **Technology**: Python 3.11+, XGBoost, scikit-learn, SHAP
- **Input**: Feature vectors, training data from TimescaleDB
- **Output**: ML probability predictions, model metrics

### 4. Signal Dispatcher Service
- **Responsibility**: Route signals to multiple channels
- **Technology**: Python 3.11+, aiogram, aioredis, FastAPI WebSocket
- **Input**: Redis signal:generated events
- **Output**: Telegram messages, WebSocket broadcasts, Risk Manager

### 5. Trade Executor Service
- **Responsibility**: Execute approved trades on exchanges
- **Technology**: Python 3.11+, aiohttp, hmac
- **Input**: Risk-approved signals
- **Output**: Order confirmations, position records

### 6. Position Manager Service
- **Responsibility**: Monitor and manage open positions
- **Technology**: Python 3.11+, asyncio
- **Input**: Open positions, mark prices
- **Output**: Updated positions, stop loss updates, Telegram notifications

### 7. API Service
- **Responsibility**: Provide REST and WebSocket interfaces
- **Technology**: FastAPI 0.115, uvicorn, WebSockets
- **Input**: HTTP requests, WebSocket connections
- **Output**: JSON responses, WebSocket messages

## Communication

Services communicate via:
- **Redis Pub/Sub**: Event-driven messaging (candle:closed, signal:generated)
- **TimescaleDB**: Shared data storage
- **HTTP/WebSocket**: External API access

## Development

### Running a Single Service

```bash
# Set environment variables
export $(cat .env | xargs)

# Run service
cd services/data_ingestion
python main.py
```

### Running All Services

```bash
# Start all services with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f data-ingestion

# Stop all services
docker-compose down
```

### Testing

```bash
# Run tests for a specific service
pytest services/data_ingestion/tests/

# Run all tests
pytest services/
```

## Configuration

All services use the shared configuration in `services/common/config.py`, which loads settings from environment variables defined in `.env`.

See `.env.example` for all available configuration options.

## Health Checks

Each service implements a health check mechanism:
- **Docker**: Health check defined in docker-compose.yml
- **API Service**: GET /api/v1/health endpoint

## Monitoring

Services expose Prometheus metrics for monitoring:
- Candle processing latency
- Signal generation count
- ML inference latency
- WebSocket reconnect count
- Database write latency

Access metrics at: http://localhost:9090 (Prometheus) and http://localhost:3000 (Grafana)
