# Implementation Plan: CandleScout Pro

## Overview

CandleScout Pro is an automated trading system that analyzes 15-minute SOL/USDT candles through a 5-layer pipeline (Classification → Morphology → Context → Patterns → ML Scoring), generates trading signals with CQS scores, and executes trades on Bybit/OKX exchanges with comprehensive risk management and position monitoring.

The implementation follows a microservices architecture with Python 3.11+, TimescaleDB for time-series data, Redis for pub/sub messaging, FastAPI for REST/WebSocket APIs, and XGBoost for ML scoring.

## Tasks

- [x] 1. Set up project structure and core infrastructure
  - Create directory structure for microservices (data_ingestion, analysis_pipeline, ml_service, signal_dispatcher, trade_executor, position_manager, api_service)
  - Set up Python 3.11+ virtual environment with requirements.txt
  - Configure TimescaleDB schema with hypertables and indexes
  - Configure Redis for pub/sub and caching
  - Create docker-compose.yml for all services
  - Set up .env configuration file template
  - _Requirements: 25.1, 25.2, 25.3_

- [ ] 2. Implement Data Ingestion Service
  - [ ] 2.1 Create Binance WebSocket manager for candle and tick streams
    - Implement WebSocketManager class with connect_candle_stream and connect_tick_stream methods
    - Add auto-reconnect logic with exponential backoff (1s, 2s, 5s, 10s, 30s)
    - Implement ping/pong keep-alive every 3 minutes
    - Parse Binance kline and aggTrade message formats
    - _Requirements: 1.1, 1.2_

  - [ ] 2.2 Create REST API fallback and backfill logic
    - Implement RESTFallback class with fetch_candles and poll_candles methods
    - Add backfill_missing_candles method to retrieve up to 1000 candles
    - Implement rate limiting (1200 requests/minute)
    - _Requirements: 1.3, 1.5_

  - [ ] 2.3 Implement tick aggregator for Delta Volume and OFI
    - Create TickAggregator class to process aggTrade messages
    - Calculate buy_volume and sell_volume from tick data
    - Compute delta and delta_ratio for each 15-minute window
    - Calculate OFI from orderbook snapshots
    - Store results in candle_tick_agg table
    - _Requirements: 1.6_

  - [ ] 2.4 Create Tortoise-ORM models and database persistence
    - Define Candle15m, CandleTickAgg async models
    - Implement database write with <100ms latency requirement
    - Add Redis cache for last 100 candles per symbol
    - Publish candle:closed:{symbol} event to Redis pub/sub
    - _Requirements: 1.4_

- [ ] 3. Implement Analysis Pipeline Layer 1: Basic Classification
  - [ ] 3.1 Create Layer1Classifier with BSS calculation
    - Implement calculate_bss method: (close - open) / (high - low) × 100
    - Add classify method with thresholds (>=70: STRONG, 40-69: MODERATE, 10-39: WEAK)
    - Implement DOJI detection (|body|/close < 0.0005)
    - Add BEARISH exclusion (close <= open)
    - Handle INVALID candles (range == 0)
    - Return L1Result dataclass with candle_class, bss, passed flag
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [ ]* 3.2 Write property test for BSS calculation correctness
    - **Property 1: BSS Calculation Correctness**
    - **Validates: Requirements 2.1**

  - [ ]* 3.3 Write property test for candle classification consistency
    - **Property 2: Candle Classification Consistency**
    - **Validates: Requirements 2.2, 2.3, 2.4**

  - [ ]* 3.4 Write property test for bearish and doji exclusion
    - **Property 3: Bearish and Doji Exclusion**
    - **Validates: Requirements 2.5, 2.6**

- [ ] 4. Implement Analysis Pipeline Layer 2: Morphology
  - [ ] 4.1 Create Layer2Morphology with Z-Score calculation
    - Implement calculate_z_score method using 50-candle history
    - Add Z-Score bonus logic (>3.0: +15, 2.0-3.0: +10, 1.5-2.0: +5)
    - Implement detect_single_patterns for MARUBOZU and HAMMER
    - Add detect_two_candle_patterns for BULLISH_ENGULFING
    - Calculate morphology score as sum of pattern bonus and Z-Score bonus
    - Return L2Result with morphology_type, z_score, total_l2_score
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ]* 4.2 Write property test for Z-Score calculation correctness
    - **Property 4: Z-Score Calculation Correctness**
    - **Validates: Requirements 3.1, 3.4, 3.5**

  - [ ]* 4.3 Write property test for pattern detection determinism
    - **Property 5: Pattern Detection Determinism**
    - **Validates: Requirements 3.2**

- [ ] 5. Implement Analysis Pipeline Layer 3: Context Filtering
  - [ ] 5.1 Create Layer3Context with volume analysis
    - Implement calculate_volume_metrics to compute volume_ratio (current_volume / avg_volume_20)
    - Add volume classification (>3.0: EXTREME +15, >2.0: HIGH +10, <0.5: LOW -10)
    - Calculate VPC as volume_ratio × (BSS / 100)
    - Implement calculate_atr using EWMA of true range over 14 periods
    - Add body/ATR14 check (<0.3: -15 penalty and rejection flag)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [ ] 5.2 Add VWAP and Delta analysis to Layer3Context
    - Implement calculate_vwap from session start: cumsum(typical_price × volume) / cumsum(volume)
    - Add VWAP positioning logic (>0.5% above: +10, >0.5% below: -8)
    - Integrate delta_ratio from TickAggregator
    - Implement SUSPICIOUS flag for delta_ratio < -0.2 on bullish candles
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [ ] 5.3 Add Fractal Dimension calculation to Layer3Context
    - Implement calculate_fractal_dimension using Higuchi method on 40 candles
    - Add market regime classification (1.0-1.3: TREND +10, 1.3-1.5: NEUTRAL +5, 1.7-2.0: CHAOS -10)
    - Calculate OFI from orderbook: (bid_size_top5 - ask_size_top5) / (bid_size_top5 + ask_size_top5)
    - Add OFI bonus (>0.3: +10)
    - Return L3Result with all metrics and total_l3_score
    - _Requirements: 5.7, 5.8, 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 5.4 Write property test for volume ratio calculation
    - **Property 6: Volume Ratio Calculation and Classification**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

  - [ ]* 5.5 Write property test for ATR calculation consistency
    - **Property 7: ATR Calculation Consistency**
    - **Validates: Requirements 4.5, 4.6**

  - [ ]* 5.6 Write property test for VPC formula correctness
    - **Property 8: VPC Formula Correctness**
    - **Validates: Requirements 4.7**

  - [ ]* 5.7 Write property test for VWAP calculation
    - **Property 9: VWAP Calculation Accumulation**
    - **Validates: Requirements 5.1, 5.2, 5.3**

  - [ ]* 5.8 Write property test for delta ratio bounds
    - **Property 10: Delta Volume and Ratio Calculation**
    - **Validates: Requirements 5.4, 5.5, 5.6**

  - [ ]* 5.9 Write property test for OFI calculation bounds
    - **Property 11: OFI Calculation Bounds**
    - **Validates: Requirements 5.7, 5.8**

  - [ ]* 5.10 Write property test for fractal dimension regime classification
    - **Property 12: Fractal Dimension Market Regime Classification**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**

- [ ] 6. Implement Analysis Pipeline Layer 4: Pattern Recognition
  - [ ] 6.1 Create Layer4Patterns with multi-candle pattern detection
    - Implement detect_three_white_soldiers (3 consecutive bullish with specific conditions, +25 bonus)
    - Add detect_morning_star (red → doji → green pattern, +22 bonus)
    - Implement detect_bullish_flag (pole + consolidation + breakout, +20 bonus)
    - Add detect_ascending_triangle (horizontal resistance + rising support + breakout, +22 bonus)
    - Cap total Layer 4 score at 35 points maximum
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ] 6.2 Add wavelet decomposition to Layer4Patterns
    - Implement wavelet_decompose using PyWavelets with db4 wavelet at level 3
    - Zero out level 1 detail coefficients for noise removal
    - Reconstruct denoised price series
    - Calculate trend slope from last 5 points
    - Set wavelet_confirmed flag if slope > 0 and add +8 to CQS
    - Return L4Result with detected_patterns, pattern_weights, wavelet_slope, wavelet_confirmed, total_l4_score
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ]* 6.3 Write property test for Layer 4 score capping
    - **Property 13: Layer 4 Score Capping**
    - **Validates: Requirements 7.6**

  - [ ]* 6.4 Write property test for wavelet noise removal
    - **Property 14: Wavelet Decomposition Noise Removal**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**

- [ ] 7. Implement ML Service for Layer 5 Scoring
  - [ ] 7.1 Create FeatureExtractor for 30-dimensional feature vectors
    - Extract features: BSS, Z-Score, vol_ratio, vpc, delta_ratio, ofi, fractal_dimension, pattern_score, wavelet_slope
    - Add 5 lagged features from previous candles
    - Include market indicators (ATR, VWAP distance)
    - Return numpy array of 30 features
    - _Requirements: 9.2_

  - [ ] 7.2 Create XGBoostModel wrapper class
    - Implement __init__ to load model from file
    - Add predict_proba method for inference (<50ms requirement)
    - Implement get_feature_importance using SHAP values
    - _Requirements: 9.3, 9.4_

  - [ ] 7.3 Implement Layer 5 CQS calculation
    - Calculate CQS_base as sum(L1 + L2 + L3 + L4) - penalties, capped at 100
    - Call ML model to get ml_probability
    - Compute CQS_final as 0.7 × CQS_base + 0.3 × (ml_probability × 100)
    - Assign confidence level (>=80: HIGH, 60-79: MEDIUM, <60: no signal)
    - _Requirements: 9.1, 9.5, 9.6, 9.7, 9.8_

  - [ ]* 7.4 Write property test for CQS base calculation and capping
    - **Property 15: CQS Base Calculation and Capping**
    - **Validates: Requirements 9.1**

  - [ ]* 7.5 Write property test for CQS final weighted combination
    - **Property 16: CQS Final Weighted Combination**
    - **Validates: Requirements 9.5, 9.6, 9.7, 9.8**

  - [ ]* 7.6 Write property test for ML inference latency
    - **Property 17: ML Inference Latency**
    - **Validates: Requirements 9.4**

- [ ] 8. Implement ML Training Pipeline
  - [ ] 8.1 Create TrainingPipeline for model training
    - Implement prepare_dataset to fetch labeled data from TimescaleDB (target: 0.3% gain in 5 candles)
    - Add train_model with XGBoost parameters (500 estimators, max_depth 6, lr 0.05)
    - Implement walk_forward_optimize with 3-month training, 2-week test, 1-week step
    - Add evaluate_model to compute AUC, precision, recall, F1-score
    - Implement deploy_model to replace current model if AUC improvement >= -0.005
    - _Requirements: 21.1, 21.2, 21.3, 21.4, 21.5, 21.6, 21.7, 21.8, 21.9_

  - [ ] 8.2 Create ModelRegistry for version tracking
    - Implement save_model to store model file and metrics in ml_models table
    - Add load_latest_model to retrieve active model
    - Implement get_model_history for audit trail
    - _Requirements: 21.9_

  - [ ] 8.3 Add automated daily retraining scheduler
    - Schedule retraining at 00:05 UTC daily
    - Check for minimum 500 new labeled samples
    - Compare new model AUC against current model
    - Deploy if performance meets thresholds
    - Send alerts if model performance degrades
    - _Requirements: 21.6, 21.7, 21.8, 22.6, 22.7_

  - [ ]* 8.4 Write property test for ML model performance thresholds
    - **Property 31: ML Model Performance Thresholds**
    - **Validates: Requirements 22.1, 22.2, 22.3, 22.4**

- [ ] 9. Checkpoint - Ensure analysis pipeline tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Implement AnalysisPipeline orchestrator
  - [ ] 10.1 Create AnalysisPipeline main class
    - Implement process_candle method to orchestrate L1→L2→L3→L4→L5
    - Add run_layer1, run_layer2, run_layer3, run_layer4, run_layer5 methods
    - Implement early exit if any layer fails validation
    - Store analysis results in candle_analysis table
    - _Requirements: 10.7_

  - [ ] 10.2 Implement signal generation logic
    - Generate TradingSignal if CQS_final >= 60 AND is_suspicious == false
    - Set entry_price to candle close
    - Calculate stop_loss as entry_price - 1.5 × ATR14
    - Identify nearest resistance for take_profit_1
    - Calculate risk_reward ratio
    - Store signal in trading_signals table
    - Publish signal:generated:{symbol} to Redis pub/sub
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [ ] 10.3 Add signal outcome tracking
    - Create background task to evaluate signals after 5 candles (75 minutes)
    - Calculate pnl_pct, hit_tp1, hit_tp2, hit_sl, MFE, MAE
    - Store results in signal_outcomes table
    - _Requirements: 11.3, 11.4_

  - [ ]* 10.4 Write property test for signal generation conditions
    - **Property 18: Signal Generation Conditions**
    - **Validates: Requirements 10.1**

  - [ ]* 10.5 Write property test for stop loss calculation
    - **Property 19: Stop Loss Calculation**
    - **Validates: Requirements 10.3**

  - [ ]* 10.6 Write property test for risk/reward ratio
    - **Property 20: Risk/Reward Ratio Calculation**
    - **Validates: Requirements 10.5, 15.2**

  - [ ]* 10.7 Write property test for pipeline latency
    - **Property 21: Pipeline Latency**
    - **Validates: Requirements 10.7**

  - [ ]* 10.8 Write property test for signal storage latency
    - **Property 22: Signal Storage Latency**
    - **Validates: Requirements 11.1**

  - [ ]* 10.9 Write property test for signal outcome tracking
    - **Property 23: Signal Outcome Tracking**
    - **Validates: Requirements 11.3, 11.4**

- [ ] 11. Implement Signal Dispatcher
  - [ ] 11.1 Create RedisSubscriber for signal events
    - Subscribe to signal:generated:{symbol} channel
    - Implement handle_signal to route to Telegram and WebSocket
    - _Requirements: 13.3_

  - [ ] 11.2 Create TelegramBot for notifications
    - Implement send_signal with formatted message (emoji, CQS, ML prob, patterns, etc.)
    - Add send_daily_report at 23:55 UTC with trade stats
    - Implement command handlers: /status, /signals, /setfilter, /stats, /current
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7_

  - [ ] 11.3 Create WebSocketBroadcaster for real-time streams
    - Implement broadcast method to send signals to all connected clients
    - Add add_client and remove_client for connection management
    - Support minimum 100 concurrent connections
    - _Requirements: 13.4, 13.6, 13.7_

  - [ ] 11.4 Create SignalFormatter for multi-channel formatting
    - Implement format_telegram for Telegram messages
    - Add format_websocket for WebSocket JSON
    - Implement format_daily_report for statistics
    - _Requirements: 14.2_

- [ ] 12. Implement Risk Manager
  - [ ] 12.1 Create RiskManager validation class
    - Implement validate method to check all risk rules
    - Add check_cqs_threshold (>= MIN_CQS_TO_TRADE)
    - Implement check_risk_reward (>= MIN_RR_RATIO)
    - Add check_suspicious_flag (must be false)
    - Implement check_position_limits (< MAX_OPEN_POSITIONS)
    - Add check_daily_loss (< MAX_DAILY_LOSS_PCT)
    - Implement check_drawdown (< MAX_DRAWDOWN_PCT)
    - Add check_cooldown (time since last loss)
    - Implement check_duplicate_position (no existing position for symbol)
    - Return RiskDecision with approved flag, reason, position_size, exchange, risk_usd
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7, 15.8_

  - [ ] 12.2 Implement position sizing algorithm
    - Calculate stop_distance as entry_price - stop_loss
    - Compute risk_amount as balance × (RISK_PER_TRADE_PCT / 100)
    - Calculate position_size as risk_amount / stop_distance
    - Cap position_size_usd at balance × 0.2 (20% maximum)
    - _Requirements: 15.9, 15.10_

  - [ ]* 12.3 Write property test for risk manager validation gates
    - **Property 26: Risk Manager Validation Gates**
    - **Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.8**

  - [ ]* 12.4 Write property test for position sizing calculation
    - **Property 27: Position Sizing Calculation**
    - **Validates: Requirements 15.9**

- [ ] 13. Implement Trading Executor with Exchange Connectors
  - [ ] 13.1 Create BaseConnector abstract class
    - Define abstract methods: place_order, cancel_order, get_position, set_stop_loss, set_take_profit, close_position, get_balance, set_leverage
    - _Requirements: 16.1, 17.1_

  - [ ] 13.2 Implement BybitConnector for Bybit V5 API
    - Implement HMAC-SHA256 signature generation
    - Add set_leverage using /v5/position/set-leverage
    - Implement place_order using /v5/order/create with stopLoss and takeProfit
    - Add get_position, set_stop_loss (trading-stop), close_position methods
    - Implement get_balance from wallet-balance endpoint
    - Add retry logic with exponential backoff (max 3 retries)
    - Store order results in orders_log table
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7, 16.8_

  - [ ] 13.3 Implement OKXConnector for OKX V5 API
    - Implement HMAC-SHA256 signature with timestamp, method, path, body
    - Add symbol format conversion (SOLUSDT → SOL-USDT-SWAP)
    - Implement set_leverage using /api/v5/account/set-leverage
    - Add place_order using /api/v5/trade/order
    - Implement algo order for SL/TP using /api/v5/trade/order-algo with OCO type
    - Add get_position, close_position methods
    - Handle x-simulated-trading header for testnet
    - Store position records in positions table
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7, 17.8_

  - [ ] 13.4 Create OrderRouter and TradingExecutor
    - Implement route method to select exchange (Bybit or OKX)
    - Add execute_signal to orchestrate order placement
    - Implement place_order_with_sl_tp to attach stop loss and take profit
    - Add log_order to persist order details
    - _Requirements: 16.1, 16.7_

- [ ] 14. Implement Position Manager
  - [ ] 14.1 Create PositionManager monitoring class
    - Implement start_monitoring to run every 15 seconds
    - Add monitor_position to check each open position
    - Fetch mark_price from exchange
    - Calculate gain_pct as (mark_price - entry_price) / entry_price × 100
    - Update unrealised_pnl in positions table
    - _Requirements: 18.1, 18.2_

  - [ ] 14.2 Implement trailing stop logic
    - Add check_trailing_stop method
    - Activate trailing stop when gain_pct >= TRAILING_STOP_ACTIVATION_PCT (1.0%)
    - Calculate trail_price as mark_price × (1 - TRAILING_STOP_DISTANCE_PCT / 100)
    - Update stop_loss if trail_price > current_stop_loss
    - Send Telegram notification on update
    - _Requirements: 18.2, 18.3, 18.4, 18.5, 18.6, 18.7_

  - [ ] 14.3 Implement breakeven stop move
    - Add check_breakeven method
    - Move stop to entry_price × (1 + BREAKEVEN_OFFSET_PCT / 100) when gain_pct >= 0.5%
    - Set be_moved flag in positions table
    - Send Telegram notification
    - _Requirements: 19.1, 19.2, 19.3_

  - [ ] 14.4 Implement partial profit taking
    - Add check_take_profit_1 method
    - Close configured percentage (50%) when mark_price >= take_profit_1
    - Set tp1_closed flag in positions table
    - Send Telegram notification with closed quantity and profit
    - _Requirements: 19.4, 19.5, 19.6_

  - [ ]* 14.5 Write property test for trailing stop activation
    - **Property 28: Trailing Stop Activation and Update**
    - **Validates: Requirements 18.2, 18.3, 18.4, 18.5**

  - [ ]* 14.6 Write property test for breakeven stop move
    - **Property 29: Breakeven Stop Move**
    - **Validates: Requirements 19.1, 19.2**

- [ ] 15. Implement Trade Journal and PnL Tracking
  - [ ] 15.1 Create PnL calculation logic
    - Calculate realised_pnl as (exit_price - entry_price) × quantity for long positions
    - Subtract fees to get net_pnl
    - Update positions table with close_time, exit_price, realised_pnl, net_pnl, exit_reason
    - _Requirements: 20.1, 20.2, 20.3_

  - [ ] 15.2 Implement daily PnL snapshots
    - Create daily_pnl records at end of each day
    - Calculate starting_balance, ending_balance, realised_pnl, fees_paid
    - Compute trade_count, win_count, loss_count, win_rate
    - Track max_drawdown as largest peak-to-trough decline
    - _Requirements: 20.4, 20.5, 20.6_

  - [ ] 15.3 Add daily report generation
    - Send Telegram report at configured time with summary statistics
    - Include trade count, win rate, PnL, max drawdown
    - _Requirements: 20.7_

  - [ ]* 15.4 Write property test for PnL calculation correctness
    - **Property 30: PnL Calculation Correctness**
    - **Validates: Requirements 20.1, 20.2**

- [ ] 16. Checkpoint - Ensure trading execution tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 17. Implement FastAPI REST and WebSocket API
  - [ ] 17.1 Create REST API endpoints
    - Implement GET /api/v1/candles with symbol, from, to, limit parameters
    - Add GET /api/v1/signals with symbol, min_cqs, from, to, limit parameters
    - Implement GET /api/v1/signals/{signal_id} with detailed analysis
    - Add GET /api/v1/analysis/latest with symbol parameter
    - Implement GET /api/v1/stats with symbol, days parameters
    - Add GET /api/v1/health for system status
    - Ensure <200ms response time at p95
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7_

  - [ ] 17.2 Create WebSocket endpoints
    - Implement WS /ws/signals for real-time signal stream
    - Add WS /ws/candles?symbol={symbol} for candle analysis stream
    - Implement WS /ws/positions for position updates
    - Support minimum 100 concurrent connections
    - Ensure <100ms message delivery
    - _Requirements: 13.1, 13.2, 13.4, 13.5, 13.6, 13.7_

  - [ ] 17.3 Create Pydantic response schemas
    - Define CandleResponse, SignalResponse, SignalDetailResponse models
    - Add AnalysisResponse, StatsResponse, HealthResponse models
    - Implement WebSocket message formats for signal, candle_analysis, position events
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

  - [ ]* 17.4 Write property test for REST API response latency
    - **Property 24: REST API Response Latency**
    - **Validates: Requirements 12.7**

  - [ ]* 17.5 Write property test for WebSocket message delivery latency
    - **Property 25: WebSocket Message Delivery Latency**
    - **Validates: Requirements 13.3, 13.4**

- [ ] 18. Implement Monitoring and Alerting
  - [ ] 18.1 Add Prometheus metrics export
    - Implement candle_processing_latency_ms histogram
    - Add signals_generated_total counter by confidence level
    - Implement ml_prediction_latency_ms histogram
    - Add ws_reconnect_count counter
    - Implement db_write_latency_ms histogram
    - Add orders_placed_total counter by exchange and status
    - Implement positions_open gauge by symbol
    - Add daily_pnl_usd and account_balance_usd gauges
    - Expose /metrics endpoint for Prometheus scraping
    - _Requirements: 23.1, 23.2_

  - [ ] 18.2 Implement health monitoring and alerts
    - Add WebSocket disconnect alert (>60s)
    - Implement database lag alert (last_candle > 20 minutes old)
    - Add ML model degradation alert (AUC drop > 0.05)
    - Implement high-priority signal alert (CQS >= 85)
    - Send alerts to Telegram and Prometheus
    - _Requirements: 23.3, 23.4, 23.5, 23.6_

- [ ] 19. Implement Data Retention and Recovery
  - [ ] 19.1 Add data retention policies
    - Configure TimescaleDB retention for candles (12 months minimum)
    - Set retention for signals (12 months minimum)
    - Keep positions and trades indefinitely
    - _Requirements: 24.1, 24.2, 24.3_

  - [ ] 19.2 Implement automated backups
    - Create daily PostgreSQL database backups
    - _Requirements: 24.4_

  - [ ] 19.3 Add system recovery logic
    - Implement auto-restart for all services within 2 minutes
    - Add automatic backfill on reconnection
    - Implement data integrity verification (check for gaps in candle timestamps)
    - _Requirements: 24.5, 24.6, 24.7_

  - [ ]* 19.4 Write property test for data retention period
    - **Property 32: Data Retention Period**
    - **Validates: Requirements 11.5, 24.1, 24.2**

  - [ ]* 19.5 Write property test for WebSocket connection fallback
    - **Property 33: WebSocket Connection Fallback**
    - **Validates: Requirements 1.3, 1.5**

- [ ] 20. Implement Configuration and Deployment
  - [ ] 20.1 Create configuration management
    - Load all settings from .env file
    - Include database credentials, API keys, risk parameters, notification settings
    - Never store secrets in code or version control
    - _Requirements: 25.2, 25.3_

  - [ ] 20.2 Configure exchange API security
    - Restrict Bybit API key to Trade only (no Withdraw/Transfer)
    - Restrict OKX API key to Trade only (no Withdraw/Transfer)
    - Bind API keys to server IP using exchange whitelist
    - _Requirements: 25.4, 25.5, 25.6_

  - [ ] 20.3 Add paper trading mode
    - Support PAPER_TRADING=true environment variable
    - Simulate trades without real execution
    - _Requirements: 25.7_

  - [ ] 20.4 Finalize docker-compose.yml
    - Define services: timescaledb, redis, data-ingestion, analysis-pipeline, ml-service, signal-dispatcher, trade-executor, position-manager, dashboard-api, grafana, prometheus
    - Add health check endpoints for all services (30s interval, 10s timeout)
    - Configure service dependencies and restart policies
    - _Requirements: 25.1, 25.8_

- [ ] 21. Integration Testing and System Validation
  - [ ]* 21.1 Write integration test for end-to-end pipeline
    - Test candle ingestion → analysis → signal generation → risk validation → order placement
    - Verify all components communicate correctly via Redis pub/sub
    - _Requirements: 1.1 through 17.8_

  - [ ]* 21.2 Write integration test for position management flow
    - Test position opening → trailing stop → breakeven → partial close → full close
    - Verify PnL calculations and database updates
    - _Requirements: 18.1 through 20.7_

  - [ ]* 21.3 Write integration test for API endpoints
    - Test all REST endpoints with various parameters
    - Test WebSocket connections and message delivery
    - Verify response times meet requirements
    - _Requirements: 12.1 through 13.7_

- [ ] 22. Final Checkpoint - System Integration
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional property-based tests and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties using hypothesis library
- The system uses Python 3.11+ with asyncio for all I/O operations
- All services communicate via Redis pub/sub and TimescaleDB
- Exchange connectors support both Bybit and OKX with proper authentication
- ML model uses XGBoost for binary classification with daily retraining
- Position management includes trailing stops, breakeven moves, and partial profit-taking
