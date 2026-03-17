# Requirements Document

## Introduction

CandleScout Pro is an automated system for detecting, classifying, and trading bullish (green) candles on the 15-minute timeframe for the SOL/USDT trading pair. The system implements a sophisticated 5-layer analysis pipeline combining classical technical analysis with modern machine learning techniques to generate high-quality trading signals with automated execution capabilities.

## Glossary

- **System**: CandleScout Pro automated trading system
- **Data_Ingestion_Service**: Component responsible for collecting real-time market data from Binance
- **Analysis_Pipeline**: Five-layer processing system that evaluates candle quality
- **ML_Service**: Machine learning component using XGBoost for signal scoring
- **Signal_Dispatcher**: Component that routes trading signals to execution and notification systems
- **Trading_Executor**: Component that executes trades on Bybit and OKX exchanges
- **Risk_Manager**: Component that validates trades against risk parameters
- **Position_Manager**: Component that manages open positions with trailing stops and partial closes
- **TimescaleDB**: PostgreSQL-based time-series database for storing OHLCV data
- **Redis**: In-memory data store for caching, pub/sub, and streaming
- **Candle**: 15-minute OHLCV (Open, High, Low, Close, Volume) data point
- **CQS**: Candle Quality Score, a 0-100 rating of candle significance
- **BSS**: Body Strength Score, ratio of candle body to total range
- **ATR**: Average True Range, measure of volatility
- **VWAP**: Volume Weighted Average Price
- **Delta_Volume**: Difference between buy volume and sell volume
- **OFI**: Order Flow Imbalance, bid/ask size imbalance
- **FD**: Fractal Dimension, measure of market regime
- **DWT**: Discrete Wavelet Transform for signal decomposition
- **R/R**: Risk/Reward ratio

## Requirements

### Requirement 1: Real-Time Data Collection

**User Story:** As a trader, I want the system to collect real-time 15-minute candle data from Binance, so that analysis is performed on current market conditions.

#### Acceptance Criteria

1. WHEN a 15-minute candle closes on Binance, THE Data_Ingestion_Service SHALL receive the OHLCV data within 2 seconds
2. THE Data_Ingestion_Service SHALL connect to Binance WebSocket API for real-time data streaming
3. IF WebSocket connection fails, THEN THE Data_Ingestion_Service SHALL fall back to REST API polling every 30 seconds
4. THE Data_Ingestion_Service SHALL store candle data in TimescaleDB within 100 milliseconds of receipt
5. WHEN connection is lost, THE Data_Ingestion_Service SHALL automatically backfill up to 1000 missing candles upon reconnection
6. THE Data_Ingestion_Service SHALL collect tick-level data for Delta Volume and OFI calculations
7. THE Data_Ingestion_Service SHALL support up to 20 trading pairs simultaneously

### Requirement 2: Layer 1 Basic Candle Classification

**User Story:** As a trader, I want each candle classified by strength, so that weak signals are filtered out early.

#### Acceptance Criteria

1. WHEN a candle is received, THE Analysis_Pipeline SHALL calculate body strength score as (close - open) / (high - low) × 100
2. IF body strength score is greater than or equal to 70, THEN THE Analysis_Pipeline SHALL classify the candle as STRONG_BULLISH
3. IF body strength score is between 40 and 69, THEN THE Analysis_Pipeline SHALL classify the candle as MODERATE_BULLISH
4. IF body strength score is between 10 and 39, THEN THE Analysis_Pipeline SHALL classify the candle as WEAK_BULLISH
5. IF absolute body size divided by close price is less than 0.0005, THEN THE Analysis_Pipeline SHALL classify the candle as DOJI and exclude it from further processing
6. IF close is less than or equal to open, THEN THE Analysis_Pipeline SHALL classify the candle as BEARISH and exclude it from further processing
7. IF candle range equals zero, THEN THE Analysis_Pipeline SHALL mark the candle as INVALID and log an alert

### Requirement 3: Layer 2 Morphological Analysis

**User Story:** As a trader, I want candles analyzed for specific patterns like MARUBOZU and HAMMER, so that high-probability setups are identified.

#### Acceptance Criteria

1. WHEN a candle passes Layer 1, THE Analysis_Pipeline SHALL calculate Z-Score as (current_body - avg_body_50) / std_body_50
2. IF upper shadow divided by range is less than 0.05 AND lower shadow divided by range is less than 0.05 AND BSS is greater than or equal to 90, THEN THE Analysis_Pipeline SHALL classify morphology as MARUBOZU and add 20 points to CQS
3. IF lower shadow is greater than or equal to 2 times body AND upper shadow is less than or equal to 0.3 times body AND BSS is between 20 and 60 AND previous 3 candles are bearish, THEN THE Analysis_Pipeline SHALL classify morphology as HAMMER and add 15 points to CQS
4. IF Z-Score is greater than 3.0, THEN THE Analysis_Pipeline SHALL add 15 bonus points to CQS
5. IF Z-Score is between 2.0 and 3.0, THEN THE Analysis_Pipeline SHALL add 10 bonus points to CQS
6. IF current candle body fully engulfs previous red candle body, THEN THE Analysis_Pipeline SHALL detect BULLISH_ENGULFING pattern and add 18 points to CQS
7. THE Analysis_Pipeline SHALL calculate morphology score as sum of pattern bonus and Z-Score bonus

### Requirement 4: Layer 3 Context Filtering with Volume Analysis

**User Story:** As a trader, I want candles validated against volume and volatility context, so that low-confidence signals are filtered out.

#### Acceptance Criteria

1. WHEN Layer 2 completes, THE Analysis_Pipeline SHALL calculate volume ratio as current_volume / avg_volume_20
2. IF volume ratio is greater than 3.0, THEN THE Analysis_Pipeline SHALL classify as EXTREME_VOLUME and add 15 points to CQS
3. IF volume ratio is greater than 2.0, THEN THE Analysis_Pipeline SHALL classify as HIGH_VOLUME and add 10 points to CQS
4. IF volume ratio is less than 0.5, THEN THE Analysis_Pipeline SHALL classify as LOW_VOLUME and subtract 10 points from CQS and set low_confidence flag
5. THE Analysis_Pipeline SHALL calculate ATR14 using exponential weighted moving average of true range over 14 periods
6. IF body divided by ATR14 is less than 0.3, THEN THE Analysis_Pipeline SHALL subtract 15 points from CQS and mark candle for rejection
7. THE Analysis_Pipeline SHALL calculate VPC as volume_ratio × (BSS / 100)

### Requirement 5: Layer 3 Context Filtering with VWAP and Delta Analysis

**User Story:** As a trader, I want candles evaluated against VWAP position and order flow, so that bull traps are avoided.

#### Acceptance Criteria

1. THE Analysis_Pipeline SHALL calculate VWAP from session start as cumulative sum of (typical_price × volume) / cumulative sum of volume
2. IF close is greater than VWAP by more than 0.5 percent, THEN THE Analysis_Pipeline SHALL add 10 points to CQS
3. IF close is less than VWAP by more than 0.5 percent, THEN THE Analysis_Pipeline SHALL subtract 8 points from CQS
4. THE Analysis_Pipeline SHALL calculate Delta Volume as buy_volume minus sell_volume from tick data
5. THE Analysis_Pipeline SHALL calculate delta_ratio as delta / (buy_volume + sell_volume)
6. IF delta_ratio is less than -0.2 AND candle is bullish, THEN THE Analysis_Pipeline SHALL set SUSPICIOUS flag and block signal generation
7. THE Analysis_Pipeline SHALL calculate OFI from orderbook snapshots as (bid_size_top5 - ask_size_top5) / (bid_size_top5 + ask_size_top5)
8. IF OFI is greater than 0.3, THEN THE Analysis_Pipeline SHALL add 10 points to CQS

### Requirement 6: Layer 3 Context Filtering with Fractal Dimension

**User Story:** As a trader, I want market regime identified, so that signals are only generated in trending conditions.

#### Acceptance Criteria

1. THE Analysis_Pipeline SHALL calculate Fractal Dimension using Higuchi method on last 40 candles
2. IF Fractal Dimension is between 1.0 and 1.3, THEN THE Analysis_Pipeline SHALL classify market regime as TREND and add 10 points to CQS
3. IF Fractal Dimension is between 1.3 and 1.5, THEN THE Analysis_Pipeline SHALL classify market regime as NEUTRAL and add 5 points to CQS
4. IF Fractal Dimension is between 1.7 and 2.0, THEN THE Analysis_Pipeline SHALL classify market regime as CHAOS and subtract 10 points from CQS
5. THE Analysis_Pipeline SHALL output Layer 3 result containing vol_ratio, vpc, atr_14, vwap_distance_pct, delta_ratio, ofi, fractal_dimension, market_regime, and is_suspicious flag

### Requirement 7: Layer 4 Pattern Recognition for Classical Patterns

**User Story:** As a trader, I want multi-candle patterns detected, so that high-probability setups are identified.

#### Acceptance Criteria

1. WHEN Layer 3 completes, THE Analysis_Pipeline SHALL analyze windows of 2 to 10 candles for pattern detection
2. IF three consecutive candles each have close greater than previous close AND open within previous body AND BSS greater than 60, THEN THE Analysis_Pipeline SHALL detect THREE_WHITE_SOLDIERS pattern and add 25 points to CQS
3. IF candle sequence matches red candle followed by doji with gap down followed by green candle closing above midpoint of first candle, THEN THE Analysis_Pipeline SHALL detect MORNING_STAR pattern and add 22 points to CQS
4. IF 5 to 15 candles show pole phase with 3 percent rise followed by consolidation with declining volume followed by breakout with volume greater than 1.5 times average, THEN THE Analysis_Pipeline SHALL detect BULLISH_FLAG pattern and add 20 points to CQS
5. IF horizontal resistance with 3 touches AND rising support with 3 touches AND current candle breaks resistance with volume greater than 2 times average, THEN THE Analysis_Pipeline SHALL detect ASCENDING_TRIANGLE pattern and add 22 points to CQS
6. THE Analysis_Pipeline SHALL cap total Layer 4 score at 35 points maximum

### Requirement 8: Layer 4 Pattern Recognition with Wavelet Analysis

**User Story:** As a trader, I want wavelet decomposition applied, so that noise is filtered from genuine trend signals.

#### Acceptance Criteria

1. THE Analysis_Pipeline SHALL apply Discrete Wavelet Transform using db4 wavelet at level 3 to price series
2. THE Analysis_Pipeline SHALL zero out level 1 detail coefficients to remove high-frequency noise
3. THE Analysis_Pipeline SHALL reconstruct denoised price series from modified coefficients
4. THE Analysis_Pipeline SHALL calculate trend slope from last 5 points of denoised series
5. IF trend slope is greater than 0, THEN THE Analysis_Pipeline SHALL set wavelet_confirmed flag to true and add 8 points to CQS
6. THE Analysis_Pipeline SHALL output detected patterns list, pattern weights, wavelet_slope, wavelet_confirmed flag, and total Layer 4 score

### Requirement 9: Layer 5 ML Scoring and Final CQS Calculation

**User Story:** As a trader, I want machine learning probability combined with rule-based score, so that final CQS reflects both approaches.

#### Acceptance Criteria

1. WHEN Layer 4 completes, THE ML_Service SHALL calculate CQS_base as sum of Layer 1 through Layer 4 scores minus penalties with maximum of 100
2. THE ML_Service SHALL extract 30 features including BSS, Z-Score, vol_ratio, vpc, delta_ratio, ofi, fractal_dimension, pattern_score, wavelet_slope, and 5 lagged features
3. THE ML_Service SHALL use XGBoost binary classifier to predict probability of 0.3 percent price rise within next 5 candles
4. THE ML_Service SHALL complete inference within 50 milliseconds
5. THE ML_Service SHALL calculate CQS_final as 0.7 × CQS_base + 0.3 × (ml_probability × 100)
6. IF CQS_final is greater than or equal to 80, THEN THE ML_Service SHALL set confidence level to HIGH
7. IF CQS_final is between 60 and 79, THEN THE ML_Service SHALL set confidence level to MEDIUM
8. IF CQS_final is less than 60, THEN THE ML_Service SHALL not generate trading signal

### Requirement 10: Trading Signal Generation

**User Story:** As a trader, I want trading signals generated with entry, stop, and target prices, so that I can execute trades.

#### Acceptance Criteria

1. WHEN CQS_final is greater than or equal to 60 AND is_suspicious flag is false, THEN THE System SHALL generate trading signal
2. THE System SHALL set entry price to close price of analyzed candle
3. THE System SHALL calculate stop loss as entry price minus 1.5 × ATR14
4. THE System SHALL identify nearest resistance level and set take_profit_1 to that level
5. THE System SHALL calculate risk_reward ratio as (take_profit_1 - entry_price) / (entry_price - stop_loss)
6. THE System SHALL include in signal: signal_id, symbol, timestamp, entry_price, stop_loss, take_profit_1, take_profit_2, risk_reward, cqs_final, ml_probability, detected_patterns, morphology_type, market_regime, vol_ratio, delta_ratio, vwap_distance_pct, fractal_dimension, and wavelet_confirmed flag
7. THE System SHALL complete full pipeline from candle close to signal generation within 500 milliseconds

### Requirement 11: Signal Storage and Retrieval

**User Story:** As a trader, I want signals stored in database, so that I can review historical performance.

#### Acceptance Criteria

1. WHEN trading signal is generated, THE System SHALL store signal in TimescaleDB trading_signals table within 100 milliseconds
2. THE System SHALL store associated candle analysis in candle_analysis table with foreign key to candle
3. THE System SHALL create signal outcome record after 5 candles (75 minutes) with actual price movement
4. THE System SHALL calculate outcome metrics including pnl_pct, hit_tp1, hit_tp2, hit_sl, max_favorable_excursion, and max_adverse_excursion
5. THE System SHALL retain signal data for minimum 12 months
6. THE System SHALL support querying signals by symbol, date range, minimum CQS, and pattern type

### Requirement 12: REST API for Signal Access

**User Story:** As a developer, I want REST API endpoints, so that I can integrate with external systems.

#### Acceptance Criteria

1. THE System SHALL provide GET endpoint at /api/v1/candles accepting symbol, from, and to parameters returning list of candles
2. THE System SHALL provide GET endpoint at /api/v1/signals accepting symbol, min_cqs, and limit parameters returning list of trading signals
3. THE System SHALL provide GET endpoint at /api/v1/signals/{signal_id} returning single signal with outcome data
4. THE System SHALL provide GET endpoint at /api/v1/analysis/latest accepting symbol parameter returning most recent candle analysis
5. THE System SHALL provide GET endpoint at /api/v1/stats accepting symbol and days parameters returning aggregate statistics
6. THE System SHALL provide GET endpoint at /api/v1/health returning system status, last candle time, database lag, and WebSocket connection status
7. THE System SHALL respond to API requests within 200 milliseconds at 95th percentile

### Requirement 13: WebSocket API for Real-Time Streaming

**User Story:** As a developer, I want WebSocket streams, so that I can receive signals in real-time.

#### Acceptance Criteria

1. THE System SHALL provide WebSocket endpoint at /ws/signals streaming trading signals as they are generated
2. THE System SHALL provide WebSocket endpoint at /ws/candles accepting symbol parameter streaming candle data with full analysis every 15 minutes
3. WHEN new signal is generated, THE System SHALL publish to Redis pub/sub channel within 50 milliseconds
4. THE System SHALL push signal to all connected WebSocket clients within 100 milliseconds of Redis publication
5. THE System SHALL include in WebSocket message: candle, l1_result, l2_result, l3_result, l4_result, and cqs_final
6. THE System SHALL support minimum 100 concurrent WebSocket connections
7. IF WebSocket client disconnects, THEN THE System SHALL clean up resources within 5 seconds

### Requirement 14: Telegram Notification System

**User Story:** As a trader, I want signals sent to Telegram, so that I am notified immediately.

#### Acceptance Criteria

1. WHEN trading signal is generated with CQS greater than or equal to configured threshold, THE Signal_Dispatcher SHALL send formatted message to Telegram within 2 seconds
2. THE Signal_Dispatcher SHALL include in message: symbol, timeframe, timestamp, CQS score, ML probability, detected patterns, morphology type, market regime, entry price, stop loss, take profit levels, risk reward ratio, position size suggestion, volume classification, delta ratio, VWAP distance, and wavelet confirmation status
3. THE System SHALL support Telegram commands /status, /signals N, /setfilter cqs=X, /stats N, and /current
4. WHEN /status command is received, THE System SHALL respond with system status, last candle time, and uptime
5. WHEN /signals N command is received, THE System SHALL respond with last N signals
6. WHEN /setfilter cqs=X command is received, THE System SHALL update minimum CQS threshold for notifications
7. THE System SHALL send daily summary report at 23:55 UTC with trade count, win rate, PnL, and max drawdown

### Requirement 15: Risk Management Gate

**User Story:** As a trader, I want risk controls enforced, so that losses are limited.

#### Acceptance Criteria

1. WHEN trading signal is received, THE Risk_Manager SHALL validate CQS is greater than or equal to configured MIN_CQS_TO_TRADE threshold
2. THE Risk_Manager SHALL validate risk_reward ratio is greater than or equal to configured MIN_RR_RATIO threshold
3. THE Risk_Manager SHALL reject signal if is_suspicious flag is true
4. THE Risk_Manager SHALL count open positions and reject signal if count is greater than or equal to MAX_OPEN_POSITIONS
5. THE Risk_Manager SHALL calculate daily PnL percentage and reject signal if loss exceeds MAX_DAILY_LOSS_PCT
6. THE Risk_Manager SHALL calculate current drawdown and reject signal if drawdown exceeds MAX_DRAWDOWN_PCT
7. THE Risk_Manager SHALL check time since last losing trade and reject signal if less than COOLDOWN_AFTER_LOSS_MIN minutes
8. THE Risk_Manager SHALL verify no existing position exists for same symbol
9. IF all checks pass, THEN THE Risk_Manager SHALL calculate position size using fixed fractional risk as (balance × risk_pct) / stop_distance
10. THE Risk_Manager SHALL return decision with approved flag, reason, position_size, exchange, and risk_usd

### Requirement 16: Order Execution on Bybit

**User Story:** As a trader, I want orders executed on Bybit, so that signals are traded automatically.

#### Acceptance Criteria

1. WHEN Risk_Manager approves signal, THE Trading_Executor SHALL set leverage on Bybit using /v5/position/set-leverage endpoint
2. THE Trading_Executor SHALL place order using Bybit V5 API /v5/order/create endpoint with category linear, symbol, side, order type, quantity, and client order ID
3. IF order type is LIMIT, THEN THE Trading_Executor SHALL set price to entry price minus configured offset percentage
4. THE Trading_Executor SHALL attach stop loss using stopLoss parameter with slTriggerBy set to MarkPrice
5. THE Trading_Executor SHALL attach take profit using takeProfit parameter with tpTriggerBy set to MarkPrice
6. THE Trading_Executor SHALL sign requests using HMAC-SHA256 with timestamp, API key, recv window, and payload
7. THE Trading_Executor SHALL store order result in orders_log table with exchange order ID, client order ID, filled quantity, average price, status, fee, and timestamp
8. IF order placement fails, THEN THE Trading_Executor SHALL log error and send alert to Telegram

### Requirement 17: Order Execution on OKX

**User Story:** As a trader, I want orders executed on OKX, so that I have exchange redundancy.

#### Acceptance Criteria

1. WHEN Risk_Manager approves signal and routing selects OKX, THE Trading_Executor SHALL set leverage using /api/v5/account/set-leverage endpoint
2. THE Trading_Executor SHALL convert symbol format from SOLUSDT to SOL-USDT-SWAP for OKX API
3. THE Trading_Executor SHALL place order using /api/v5/trade/order endpoint with instId, tdMode, side, ordType, size, and client order ID
4. THE Trading_Executor SHALL attach stop loss and take profit using /api/v5/trade/order-algo endpoint with OCO order type
5. THE Trading_Executor SHALL sign requests using HMAC-SHA256 with timestamp, method, request path, and body
6. THE Trading_Executor SHALL include x-simulated-trading header when testnet mode is enabled
7. THE Trading_Executor SHALL handle OKX response code and raise exception if code is not equal to 0
8. THE Trading_Executor SHALL store position record in positions table with signal reference, exchange, symbol, side, quantity, entry price, stop loss, take profit levels, and leverage

### Requirement 18: Position Management with Trailing Stop

**User Story:** As a trader, I want trailing stops activated, so that profits are protected.

#### Acceptance Criteria

1. THE Position_Manager SHALL monitor each open position every 15 seconds
2. THE Position_Manager SHALL calculate gain percentage as (mark_price - entry_price) / entry_price × 100
3. IF gain percentage is greater than or equal to TRAILING_STOP_ACTIVATION_PCT, THEN THE Position_Manager SHALL activate trailing stop
4. WHILE trailing stop is active, THE Position_Manager SHALL calculate trail price as mark_price × (1 - TRAILING_STOP_DISTANCE_PCT / 100)
5. IF trail price is greater than current stop loss, THEN THE Position_Manager SHALL update stop loss to trail price using exchange API
6. THE Position_Manager SHALL store updated stop loss in positions table
7. THE Position_Manager SHALL send Telegram notification when trailing stop is updated

### Requirement 19: Position Management with Breakeven and Partial Close

**User Story:** As a trader, I want stop moved to breakeven and partial profits taken, so that risk is reduced.

#### Acceptance Criteria

1. IF gain percentage is greater than or equal to BREAKEVEN_ACTIVATION_PCT AND breakeven not yet moved, THEN THE Position_Manager SHALL move stop loss to entry price plus 0.1 percent
2. THE Position_Manager SHALL set be_moved flag to true in positions table
3. THE Position_Manager SHALL send Telegram notification when breakeven is moved
4. IF mark price is greater than or equal to take_profit_1 AND tp1 not yet closed, THEN THE Position_Manager SHALL close configured percentage of position using exchange close position API
5. THE Position_Manager SHALL set tp1_closed flag to true in positions table
6. THE Position_Manager SHALL send Telegram notification with closed quantity and profit amount
7. THE Position_Manager SHALL update unrealised PnL in positions table every monitoring cycle

### Requirement 20: Trade Journal and PnL Tracking

**User Story:** As a trader, I want all trades logged, so that I can analyze performance.

#### Acceptance Criteria

1. WHEN position is closed, THE System SHALL calculate realised PnL as (exit_price - entry_price) × quantity × side_multiplier
2. THE System SHALL subtract fees from realised PnL to calculate net PnL
3. THE System SHALL update positions table with close_time, exit_price, realised_pnl, net_pnl, and exit_reason
4. THE System SHALL create daily PnL snapshot at end of each day with starting balance, ending balance, realised PnL, fees paid, trade count, win count, loss count, win rate, and max drawdown
5. THE System SHALL calculate win rate as win_count / (win_count + loss_count)
6. THE System SHALL track maximum drawdown as largest peak-to-trough decline in equity
7. THE System SHALL send daily report to Telegram at configured time with summary statistics

### Requirement 21: ML Model Training and Retraining

**User Story:** As a system operator, I want ML model retrained automatically, so that it adapts to changing market conditions.

#### Acceptance Criteria

1. THE ML_Service SHALL use XGBoost binary classifier with 500 estimators, max depth 6, learning rate 0.05, and early stopping after 50 rounds
2. THE ML_Service SHALL define target as 1 if price rises by 0.3 percent or more within next 5 candles, else 0
3. THE ML_Service SHALL extract 30 features including candle metrics, context metrics, pattern scores, lagged features, and market indicators
4. THE ML_Service SHALL split data chronologically with 70 percent training, 15 percent validation, and 15 percent test
5. THE ML_Service SHALL perform walk-forward optimization with 3-month training window, 2-week test window, and 1-week step over 24 iterations
6. THE ML_Service SHALL retrain model daily at 00:05 UTC when training pool contains 500 or more new labeled samples
7. THE ML_Service SHALL compare new model AUC against current model AUC on holdout set
8. IF new model AUC is greater than or equal to current model AUC minus 0.005, THEN THE ML_Service SHALL deploy new model
9. THE ML_Service SHALL store model version with timestamp and metrics in model registry

### Requirement 22: ML Model Performance Requirements

**User Story:** As a system operator, I want ML model to meet minimum performance thresholds, so that signal quality is maintained.

#### Acceptance Criteria

1. THE ML_Service SHALL achieve minimum AUC-ROC of 0.58 on out-of-sample test set
2. THE ML_Service SHALL achieve minimum precision of 0.55 at threshold 0.55 on out-of-sample test set
3. THE ML_Service SHALL achieve minimum recall of 0.45 on out-of-sample test set
4. THE ML_Service SHALL achieve minimum F1-score of 0.50 on out-of-sample test set
5. WHEN backtested, THE System SHALL achieve minimum Sharpe ratio of 1.0
6. THE ML_Service SHALL calculate SHAP values for feature importance and log top 10 features
7. IF model performance falls below minimum thresholds, THEN THE System SHALL send alert and continue using previous model version

### Requirement 23: System Monitoring and Alerting

**User Story:** As a system operator, I want system health monitored, so that issues are detected quickly.

#### Acceptance Criteria

1. THE System SHALL export Prometheus metrics including candle_processing_latency_ms, signals_generated_total, ml_prediction_latency_ms, ws_reconnect_count, and db_write_latency_ms
2. THE System SHALL expose metrics endpoint at /metrics for Prometheus scraping
3. IF WebSocket connection is disconnected for more than 60 seconds, THEN THE System SHALL send alert to Telegram and Prometheus
4. IF last candle timestamp is more than 20 minutes old, THEN THE System SHALL send database lag alert
5. IF ML model AUC drops by more than 0.05 over one week, THEN THE System SHALL send ML degradation alert via email and Telegram
6. IF CQS is greater than or equal to 85, THEN THE System SHALL send high-priority anomaly signal alert to Telegram
7. THE System SHALL maintain uptime of 99.5 percent or greater measured monthly

### Requirement 24: Data Retention and Recovery

**User Story:** As a system operator, I want data retained and system recoverable, so that historical analysis is possible and downtime is minimized.

#### Acceptance Criteria

1. THE System SHALL retain candle data for minimum 12 months in TimescaleDB
2. THE System SHALL retain signal data for minimum 12 months
3. THE System SHALL retain position and trade data indefinitely
4. THE System SHALL create automated daily backups of PostgreSQL database
5. IF system crashes, THEN THE System SHALL restart all services within 2 minutes
6. WHEN system restarts, THE Data_Ingestion_Service SHALL automatically backfill missing candles from Binance REST API
7. THE System SHALL verify data integrity after recovery by checking for gaps in candle timestamps

### Requirement 25: Configuration and Deployment

**User Story:** As a system operator, I want system deployed via Docker Compose, so that setup is reproducible.

#### Acceptance Criteria

1. THE System SHALL provide docker-compose.yml file defining all services including timescaledb, redis, data-ingestion, analysis-pipeline, ml-service, signal-dispatcher, trade-executor, dashboard-api, grafana, and prometheus
2. THE System SHALL load configuration from .env file including database credentials, API keys, risk parameters, and notification settings
3. THE System SHALL never store API keys or secrets in code or version control
4. THE System SHALL restrict Bybit API key permissions to Trade only with Withdraw and Transfer disabled
5. THE System SHALL restrict OKX API key permissions to Trade only with Withdraw and Transfer disabled
6. THE System SHALL bind API keys to server IP address using exchange IP whitelist feature
7. THE System SHALL support paper trading mode where PAPER_TRADING environment variable set to true simulates trades without real execution
8. THE System SHALL provide health check endpoints for all services with 30-second interval and 10-second timeout
