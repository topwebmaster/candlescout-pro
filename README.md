# 🕯️ CandleScout Pro

> Autonomous 5-layer bullish candle analysis & automated trading system for SOL/USDT

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![Django](https://img.shields.io/badge/Django-6.0-green)](https://djangoproject.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-teal)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

## Overview

**CandleScout Pro** is a self-hosted algorithmic trading system that:

- 📥 Collects real-time 15-minute OHLCV candles from Binance (WebSocket)
- 🔬 Applies a **5-layer analysis pipeline** to classify every bullish candle
- 🤖 Trains and uses an **XGBoost ML model** to boost signal confidence
- 📊 Generates ranked trading signals with entry, stop-loss, TP, and R/R
- ⚡ Executes trades automatically on **Bybit** and/or **OKX** via REST API
- 📡 Streams signals in real-time via **WebSocket** (FastAPI)
- 🔔 Sends Telegram notifications for every event
- 📈 Visualises everything on a **Grafana** dashboard

---

## 5-Layer Analysis Architecture

```
Layer 1 → Candle Classification   (BSS score, body/wick ratio)
Layer 2 → Morphology Analysis     (Z-score, Marubozu, Hammer, Engulfing)
Layer 3 → Context Filter          (Volume, VWAP, Delta, OFI, Fractal Dim)
Layer 4 → Pattern Recognition     (Three White Soldiers, Wavelet, SR levels)
Layer 5 → ML Scoring + CQS        (XGBoost + Composite Quality Score 0-100)
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Data Models | Django 6.0 + django-timescaledb |
| Async API + WebSocket | FastAPI 0.115 + Starlette |
| Async ORM | Tortoise-ORM + aerich |
| Primary Database | PostgreSQL 17 + TimescaleDB 2.x |
| Realtime Cache | Redis 7.4 (Pub/Sub + Streams + Cache) |
| Task Queue | Celery 6 + Redis |
| ML | XGBoost + scikit-learn + pandas |
| Exchange Connectors | Bybit V5 API + OKX V5 API |
| Testing | pytest + pytest-django + pytest-asyncio + testcontainers |
| Monitoring | Prometheus + Grafana |
| Containerisation | Docker + Podman Compose |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/topwebmaster/candlescout-pro.git
cd candlescout-pro

# 2. Configure
cp .env.example .env
# Edit .env with your API keys

# 3. Run
make up

# 4. Apply migrations
make migrate

# 5. Access
# FastAPI docs:  http://localhost:8000/api/docs
# Django Admin: http://localhost:8001/admin
# Grafana:      http://localhost:3000
```

## Project Structure

```
candlescout-pro/
├── django_app/          # Django 6.0 — models, admin, migrations, celery
├── fastapi_app/         # FastAPI — REST API + WebSocket
├── tortoise_models/     # Tortoise-ORM async models
├── services/
│   ├── data_ingestion/      # Binance WebSocket collector
│   ├── analysis_pipeline/   # 5-layer candle analysis
│   ├── ml_service/          # XGBoost training & inference
│   ├── trade_executor/      # Bybit + OKX order execution
│   └── signal_dispatcher/   # Signal routing + Telegram
├── tests/
│   ├── unit/            # Layer-by-layer unit tests
│   ├── integration/     # API + pipeline integration tests
│   ├── e2e/             # Full flow end-to-end tests
│   └── backtesting/     # Strategy backtesting
├── docs/                # Technical specification
├── grafana/             # Dashboard configs
├── docker-compose.yml
├── pyproject.toml
└── Makefile
```

## Documentation

- 📋 [Technical Specification (RU)](docs/TECHNICAL_SPEC.md)
- 🏗️ [Architecture Overview](docs/ARCHITECTURE.md)
- 🔌 [API Reference](docs/API.md)
- 🧪 [Testing Guide](docs/TESTING.md)
- 🚀 [Deployment Guide](docs/DEPLOYMENT.md)

## License

MIT © 2026 CandleScout Pro
