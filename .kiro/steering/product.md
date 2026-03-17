# CandleScout Pro - Product Overview

CandleScout Pro is a self-hosted algorithmic trading system for SOL/USDT that autonomously analyzes bullish candlestick patterns and executes trades.

## Core Functionality

**Data Collection**: Real-time 15-minute OHLCV candles from Binance via WebSocket

**5-Layer Analysis Pipeline**:
- Layer 1: Candle Classification (BSS score, body/wick ratios)
- Layer 2: Morphology Analysis (Z-score, Marubozu, Hammer, Engulfing)
- Layer 3: Context Filtering (Volume, VWAP, Delta, OFI, Fractal Dimension)
- Layer 4: Pattern Recognition (Three White Soldiers, Wavelet, S/R levels)
- Layer 5: ML Scoring + CQS (XGBoost + Composite Quality Score 0-100)

**Trading Execution**: Automated trades on Bybit and OKX with risk management, position monitoring, trailing stops, and breakeven logic

**Notifications**: Real-time signals via WebSocket (FastAPI) and Telegram alerts for all trading events

**Monitoring**: Grafana dashboards with Prometheus metrics

## Key Concepts

- **BSS (Bullish Strength Score)**: 0-100 score measuring candle bullishness
- **CQS (Composite Quality Score)**: 0-100 final score combining analysis layers + ML probability
- **Signal**: Trading recommendation with entry price, stop-loss, take-profit targets, and risk/reward ratio
- **Paper Trading Mode**: Simulated trading without real money (default enabled)

## Trading Flow

1. Binance streams 15m candles → TimescaleDB
2. Analysis pipeline processes each candle through 5 layers
3. ML service scores signal confidence with XGBoost
4. Signal dispatcher routes to Telegram/WebSocket/Trade Executor
5. Trade executor places orders on Bybit/OKX (if approved by risk manager)
6. Position manager monitors open positions with trailing stops
7. All events logged to TimescaleDB and broadcast via WebSocket
