-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Performance settings for TimescaleDB
ALTER SYSTEM SET shared_preload_libraries = 'timescaledb,pg_stat_statements';

-- ═══════════════════════════════════════════════════════════════════════════
-- CANDLESCOUT PRO DATABASE SCHEMA
-- ═══════════════════════════════════════════════════════════════════════════

-- ── 1. CANDLES TABLE (15-minute OHLCV data) ──────────────────────────────
CREATE TABLE IF NOT EXISTS candles_15m (
    id BIGSERIAL,
    symbol VARCHAR(20) NOT NULL,
    open_time TIMESTAMPTZ NOT NULL,
    close_time TIMESTAMPTZ NOT NULL,
    open NUMERIC(20, 8) NOT NULL,
    high NUMERIC(20, 8) NOT NULL,
    low NUMERIC(20, 8) NOT NULL,
    close NUMERIC(20, 8) NOT NULL,
    volume NUMERIC(20, 8) NOT NULL,
    quote_volume NUMERIC(20, 8) NOT NULL,
    trades_count INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol, open_time)
);

-- Convert to hypertable (partitioned by time)
SELECT create_hypertable('candles_15m', 'open_time', if_not_exists => TRUE);

-- Create indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_candles_symbol_time ON candles_15m (symbol, open_time DESC);
CREATE INDEX IF NOT EXISTS idx_candles_close_time ON candles_15m (close_time);

-- Set retention policy: keep 12 months of data
SELECT add_retention_policy('candles_15m', INTERVAL '12 months', if_not_exists => TRUE);

-- Enable compression after 7 days
SELECT add_compression_policy('candles_15m', INTERVAL '7 days', if_not_exists => TRUE);


-- ── 2. CANDLE TICK AGGREGATES (Delta Volume, OFI) ────────────────────────
CREATE TABLE IF NOT EXISTS candle_tick_agg (
    candle_id BIGINT NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    open_time TIMESTAMPTZ NOT NULL,
    buy_volume NUMERIC(20, 8) NOT NULL DEFAULT 0,
    sell_volume NUMERIC(20, 8) NOT NULL DEFAULT 0,
    delta_volume NUMERIC(20, 8) NOT NULL DEFAULT 0,
    delta_ratio NUMERIC(10, 6) NOT NULL DEFAULT 0,
    ofi NUMERIC(10, 6) NOT NULL DEFAULT 0,
    bid_size_top5 NUMERIC(20, 8) NOT NULL DEFAULT 0,
    ask_size_top5 NUMERIC(20, 8) NOT NULL DEFAULT 0,
    tick_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol, open_time)
);

-- Convert to hypertable
SELECT create_hypertable('candle_tick_agg', 'open_time', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_tick_agg_symbol_time ON candle_tick_agg (symbol, open_time DESC);

-- Set retention policy
SELECT add_retention_policy('candle_tick_agg', INTERVAL '12 months', if_not_exists => TRUE);


-- ── 3. CANDLE ANALYSIS (Layer 1-4 results) ───────────────────────────────
CREATE TABLE IF NOT EXISTS candle_analysis (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    candle_open_time TIMESTAMPTZ NOT NULL,
    
    -- Layer 1: Basic Classification
    candle_class VARCHAR(20) NOT NULL,
    bss NUMERIC(10, 4) NOT NULL,
    
    -- Layer 2: Morphology
    morphology_type VARCHAR(50),
    z_score NUMERIC(10, 4),
    l2_score INTEGER DEFAULT 0,
    
    -- Layer 3: Context
    vol_ratio NUMERIC(10, 4),
    vpc NUMERIC(10, 4),
    atr_14 NUMERIC(20, 8),
    vwap_distance_pct NUMERIC(10, 4),
    delta_ratio NUMERIC(10, 6),
    ofi NUMERIC(10, 6),
    fractal_dimension NUMERIC(10, 6),
    market_regime VARCHAR(20),
    is_suspicious BOOLEAN DEFAULT FALSE,
    l3_score INTEGER DEFAULT 0,
    
    -- Layer 4: Patterns
    detected_patterns TEXT[],
    pattern_weights JSONB,
    wavelet_slope NUMERIC(10, 6),
    wavelet_confirmed BOOLEAN DEFAULT FALSE,
    l4_score INTEGER DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (symbol, candle_open_time)
);

-- Convert to hypertable
SELECT create_hypertable('candle_analysis', 'candle_open_time', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_analysis_symbol_time ON candle_analysis (symbol, candle_open_time DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_class ON candle_analysis (candle_class);
CREATE INDEX IF NOT EXISTS idx_analysis_morphology ON candle_analysis (morphology_type);
CREATE INDEX IF NOT EXISTS idx_analysis_suspicious ON candle_analysis (is_suspicious);

-- Set retention policy
SELECT add_retention_policy('candle_analysis', INTERVAL '12 months', if_not_exists => TRUE);


-- ── 4. TRADING SIGNALS ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trading_signals (
    id BIGSERIAL PRIMARY KEY,
    signal_id VARCHAR(50) UNIQUE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    
    -- Price levels
    entry_price NUMERIC(20, 8) NOT NULL,
    stop_loss NUMERIC(20, 8) NOT NULL,
    take_profit_1 NUMERIC(20, 8) NOT NULL,
    take_profit_2 NUMERIC(20, 8),
    risk_reward NUMERIC(10, 4) NOT NULL,
    
    -- Scores
    cqs_base INTEGER NOT NULL,
    cqs_final NUMERIC(10, 4) NOT NULL,
    ml_probability NUMERIC(10, 6) NOT NULL,
    confidence_level VARCHAR(20) NOT NULL,
    
    -- Analysis details
    detected_patterns TEXT[],
    morphology_type VARCHAR(50),
    market_regime VARCHAR(20),
    vol_ratio NUMERIC(10, 4),
    delta_ratio NUMERIC(10, 6),
    vwap_distance_pct NUMERIC(10, 4),
    fractal_dimension NUMERIC(10, 6),
    wavelet_confirmed BOOLEAN,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable
SELECT create_hypertable('trading_signals', 'timestamp', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_signals_symbol_time ON trading_signals (symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signals_cqs ON trading_signals (cqs_final DESC);
CREATE INDEX IF NOT EXISTS idx_signals_confidence ON trading_signals (confidence_level);
CREATE INDEX IF NOT EXISTS idx_signals_signal_id ON trading_signals (signal_id);

-- Set retention policy
SELECT add_retention_policy('trading_signals', INTERVAL '12 months', if_not_exists => TRUE);


-- ── 5. SIGNAL OUTCOMES (Feedback for ML) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS signal_outcomes (
    id BIGSERIAL PRIMARY KEY,
    signal_id VARCHAR(50) NOT NULL REFERENCES trading_signals(signal_id),
    symbol VARCHAR(20) NOT NULL,
    signal_timestamp TIMESTAMPTZ NOT NULL,
    evaluation_timestamp TIMESTAMPTZ NOT NULL,
    
    -- Outcome metrics
    pnl_pct NUMERIC(10, 4),
    hit_tp1 BOOLEAN DEFAULT FALSE,
    hit_tp2 BOOLEAN DEFAULT FALSE,
    hit_sl BOOLEAN DEFAULT FALSE,
    max_favorable_excursion NUMERIC(10, 4),
    max_adverse_excursion NUMERIC(10, 4),
    candles_to_target INTEGER,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (signal_id)
);

-- Convert to hypertable
SELECT create_hypertable('signal_outcomes', 'signal_timestamp', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_outcomes_signal_id ON signal_outcomes (signal_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_symbol_time ON signal_outcomes (symbol, signal_timestamp DESC);

-- Set retention policy
SELECT add_retention_policy('signal_outcomes', INTERVAL '12 months', if_not_exists => TRUE);


-- ── 6. POSITIONS ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS positions (
    id BIGSERIAL PRIMARY KEY,
    position_id VARCHAR(50) UNIQUE NOT NULL,
    signal_id VARCHAR(50) REFERENCES trading_signals(signal_id),
    exchange VARCHAR(20) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    
    -- Position details
    quantity NUMERIC(20, 8) NOT NULL,
    entry_price NUMERIC(20, 8) NOT NULL,
    current_price NUMERIC(20, 8),
    stop_loss NUMERIC(20, 8) NOT NULL,
    take_profit_1 NUMERIC(20, 8) NOT NULL,
    take_profit_2 NUMERIC(20, 8),
    leverage INTEGER NOT NULL,
    
    -- Status flags
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
    trailing_active BOOLEAN DEFAULT FALSE,
    be_moved BOOLEAN DEFAULT FALSE,
    tp1_closed BOOLEAN DEFAULT FALSE,
    tp2_closed BOOLEAN DEFAULT FALSE,
    
    -- PnL tracking
    unrealised_pnl NUMERIC(20, 8) DEFAULT 0,
    realised_pnl NUMERIC(20, 8) DEFAULT 0,
    net_pnl NUMERIC(20, 8) DEFAULT 0,
    fees_paid NUMERIC(20, 8) DEFAULT 0,
    
    -- Timestamps
    open_time TIMESTAMPTZ NOT NULL,
    close_time TIMESTAMPTZ,
    exit_price NUMERIC(20, 8),
    exit_reason VARCHAR(50),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions (status);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions (symbol);
CREATE INDEX IF NOT EXISTS idx_positions_exchange ON positions (exchange);
CREATE INDEX IF NOT EXISTS idx_positions_open_time ON positions (open_time DESC);
CREATE INDEX IF NOT EXISTS idx_positions_signal_id ON positions (signal_id);


-- ── 7. ORDERS LOG ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS orders_log (
    id BIGSERIAL PRIMARY KEY,
    order_id VARCHAR(100) UNIQUE NOT NULL,
    exchange_order_id VARCHAR(100),
    client_order_id VARCHAR(100),
    position_id VARCHAR(50) REFERENCES positions(position_id),
    exchange VARCHAR(20) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    
    -- Order details
    quantity NUMERIC(20, 8) NOT NULL,
    price NUMERIC(20, 8),
    filled_qty NUMERIC(20, 8) DEFAULT 0,
    avg_price NUMERIC(20, 8),
    status VARCHAR(20) NOT NULL,
    
    -- Fees and costs
    fee NUMERIC(20, 8) DEFAULT 0,
    fee_currency VARCHAR(10),
    
    -- Timestamps
    timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable
SELECT create_hypertable('orders_log', 'timestamp', if_not_exists => TRUE);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_orders_exchange_order_id ON orders_log (exchange_order_id);
CREATE INDEX IF NOT EXISTS idx_orders_position_id ON orders_log (position_id);
CREATE INDEX IF NOT EXISTS idx_orders_symbol_time ON orders_log (symbol, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders_log (status);

-- Set retention policy: keep orders indefinitely
-- SELECT add_retention_policy('orders_log', INTERVAL '24 months', if_not_exists => TRUE);


-- ── 8. DAILY PNL SNAPSHOTS ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS daily_pnl (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    
    -- Balance tracking
    starting_balance NUMERIC(20, 8) NOT NULL,
    ending_balance NUMERIC(20, 8) NOT NULL,
    realised_pnl NUMERIC(20, 8) NOT NULL,
    fees_paid NUMERIC(20, 8) NOT NULL,
    
    -- Trade statistics
    trade_count INTEGER NOT NULL DEFAULT 0,
    win_count INTEGER NOT NULL DEFAULT 0,
    loss_count INTEGER NOT NULL DEFAULT 0,
    win_rate NUMERIC(10, 4),
    
    -- Risk metrics
    max_drawdown NUMERIC(10, 4),
    sharpe_ratio NUMERIC(10, 4),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_daily_pnl_date ON daily_pnl (date DESC);


-- ── 9. ML MODELS REGISTRY ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ml_models (
    id BIGSERIAL PRIMARY KEY,
    version VARCHAR(50) UNIQUE NOT NULL,
    model_path VARCHAR(255) NOT NULL,
    
    -- Performance metrics
    auc_roc NUMERIC(10, 6),
    precision_at_55 NUMERIC(10, 6),
    recall NUMERIC(10, 6),
    f1_score NUMERIC(10, 6),
    
    -- Training details
    training_samples INTEGER,
    validation_samples INTEGER,
    test_samples INTEGER,
    feature_importance JSONB,
    
    -- Status
    is_active BOOLEAN DEFAULT FALSE,
    deployed_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_ml_models_version ON ml_models (version);
CREATE INDEX IF NOT EXISTS idx_ml_models_active ON ml_models (is_active);
CREATE INDEX IF NOT EXISTS idx_ml_models_created ON ml_models (created_at DESC);


-- ═══════════════════════════════════════════════════════════════════════════
-- CONTINUOUS AGGREGATES (Materialized Views)
-- ═══════════════════════════════════════════════════════════════════════════

-- Hourly signal statistics
CREATE MATERIALIZED VIEW IF NOT EXISTS signals_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', timestamp) AS hour,
    symbol,
    COUNT(*) AS signal_count,
    AVG(cqs_final) AS avg_cqs,
    MAX(cqs_final) AS max_cqs,
    COUNT(*) FILTER (WHERE confidence_level = 'HIGH') AS high_confidence_count,
    COUNT(*) FILTER (WHERE confidence_level = 'MEDIUM') AS medium_confidence_count
FROM trading_signals
GROUP BY hour, symbol;

-- Add refresh policy
SELECT add_continuous_aggregate_policy('signals_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);


-- ═══════════════════════════════════════════════════════════════════════════
-- FUNCTIONS AND TRIGGERS
-- ═══════════════════════════════════════════════════════════════════════════

-- Update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_positions_updated_at
    BEFORE UPDATE ON positions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- ═══════════════════════════════════════════════════════════════════════════
-- GRANTS (for application user)
-- ═══════════════════════════════════════════════════════════════════════════

-- Grant all privileges to the application user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO candlescout;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO candlescout;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO candlescout;
