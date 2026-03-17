# Design Document: CandleScout Pro

## Overview

CandleScout Pro is an automated trading system that detects, classifies, and trades bullish candle patterns on the 15-minute timeframe for SOL/USDT. The system implements a sophisticated 5-layer analysis pipeline combining classical technical analysis with modern machine learning techniques, followed by automated trade execution on Bybit and OKX exchanges.

### System Goals

- Collect real-time 15-minute OHLCV data from Binance with sub-2-second latency
- Analyze each candle through 5 progressive layers of filtering and scoring
- Generate high-quality trading signals (CQS ≥ 60) with entry, stop, and target prices
- Execute trades automatically on Bybit and OKX with comprehensive risk management
- Manage positions with trailing stops, breakeven moves, and partial profit-taking
- Continuously improve through ML model retraining with feedback loop
- Provide real-time monitoring via REST API, WebSocket streams, and Telegram notifications

### Key Design Principles

- **Layered Filtering**: Progressive elimination of low-quality signals through 5 analysis layers
- **Microservices Architecture**: Independent, scalable services communicating via Redis and TimescaleDB
- **Async-First**: All I/O operations use asyncio for maximum throughput
- **Data-Driven**: ML model continuously learns from signal outcomes
- **Risk-First**: Multiple validation gates before trade execution
- **Observable**: Comprehensive metrics, logging, and alerting at every layer

## Architecture

### High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL DATA SOURCES                         │
│  Binance WS (OHLCV) │ Binance WS (Ticks) │ Binance REST (Backfill) │
└──────────┬──────────────────────┬──────────────────────┬────────────┘
           │                      │                      │
           ↓                      ↓                      ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      DATA INGESTION SERVICE                          │
│    WebSocket Manager │ REST Fallback │ Tick Aggregator │ Cache      │
└──────────────────────────────┬──────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    TIMESCALEDB (PostgreSQL 17)                       │
│  candles_15m │ candle_tick_agg │ candle_analysis │ trading_signals │
│  signal_outcomes │ positions │ orders_log │ daily_pnl │ ml_models  │
└──────────────────────────────┬──────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      ANALYSIS PIPELINE (5 Layers)                    │
│  L1: Classifier → L2: Morphology → L3: Context → L4: Patterns →    │
│  L5: ML Scorer                                                       │
└──────────────────────────────┬──────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                           ML SERVICE                                 │
│  Feature Extractor │ XGBoost Model │ Training Pipeline │ Registry   │
└──────────────────────────────┬──────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        SIGNAL DISPATCHER                             │
│         Redis Pub/Sub → Telegram Bot │ WebSocket API                │
└──────────────────────────────┬──────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         TRADING EXECUTOR                             │
│  Risk Manager → Order Router → Bybit Connector │ OKX Connector      │
└──────────────────────────────┬──────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        POSITION MANAGER                              │
│  Trailing Stop │ Breakeven Move │ Partial Close │ PnL Tracker       │
└──────────────────────────────┬──────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      MONITORING & INTERFACES                         │
│  FastAPI (REST/WS) │ Django Admin │ Grafana │ Prometheus │ Telegram │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Ingestion**: Binance WebSocket streams OHLCV and tick data → Data Ingestion Service
2. **Storage**: Raw data persisted to TimescaleDB hypertables within 100ms
3. **Analysis**: On candle close, Analysis Pipeline processes through L1→L2→L3→L4→L5
4. **Scoring**: ML Service calculates final CQS combining rule-based and ML scores
5. **Signal Generation**: Signals with CQS ≥ 60 published to Redis pub/sub
6. **Dispatch**: Signal Dispatcher routes to Telegram and WebSocket clients
7. **Risk Validation**: Risk Manager validates signal against risk parameters
8. **Execution**: Order Router sends approved orders to Bybit/OKX connectors
9. **Position Management**: Position Manager monitors and adjusts open positions
10. **Feedback**: Signal outcomes stored for ML model retraining


### Component Interaction Diagram

```mermaid
sequenceDiagram
    participant Binance
    participant DataIngestion
    participant TimescaleDB
    participant AnalysisPipeline
    participant MLService
    participant Redis
    participant SignalDispatcher
    participant RiskManager
    participant TradingExecutor
    participant Exchange
    participant PositionManager

    Binance->>DataIngestion: WebSocket: New 15m candle
    DataIngestion->>TimescaleDB: Store candle + tick aggregates
    DataIngestion->>AnalysisPipeline: Trigger analysis
    AnalysisPipeline->>AnalysisPipeline: L1: Classify (BSS)
    AnalysisPipeline->>AnalysisPipeline: L2: Morphology (Z-Score, patterns)
    AnalysisPipeline->>AnalysisPipeline: L3: Context (Vol, ATR, VWAP, Delta, OFI, FD)
    AnalysisPipeline->>AnalysisPipeline: L4: Patterns (Multi-candle, Wavelet)
    AnalysisPipeline->>MLService: Request ML probability
    MLService->>MLService: Extract 30 features
    MLService->>MLService: XGBoost inference (<50ms)
    MLService-->>AnalysisPipeline: Return ml_probability
    AnalysisPipeline->>AnalysisPipeline: L5: Calculate CQS_final
    AnalysisPipeline->>TimescaleDB: Store analysis + signal
    AnalysisPipeline->>Redis: Publish signal (if CQS ≥ 60)
    Redis->>SignalDispatcher: Signal event
    SignalDispatcher->>Telegram: Send formatted alert
    SignalDispatcher->>RiskManager: Forward for execution
    RiskManager->>RiskManager: Validate CQS, R/R, limits, drawdown
    RiskManager->>TradingExecutor: Approved with position_size
    TradingExecutor->>Exchange: Place order with SL/TP
    Exchange-->>TradingExecutor: Order confirmation
    TradingExecutor->>TimescaleDB: Log order + position
    PositionManager->>Exchange: Monitor position (every 15s)
    PositionManager->>PositionManager: Check trailing stop, breakeven, TP1
    PositionManager->>Exchange: Update SL or close partial
    PositionManager->>TimescaleDB: Update position record
```


## Components and Interfaces

### 1. Data Ingestion Service

**Responsibility**: Collect real-time market data from Binance and persist to TimescaleDB.

**Technology**: Python 3.11+, asyncio, websockets, aiohttp, Tortoise-ORM

**Key Classes**:

```python
class WebSocketManager:
    """Manages WebSocket connections to Binance with auto-reconnect"""
    async def connect_candle_stream(symbol: str) -> None
    async def connect_tick_stream(symbol: str) -> None
    async def handle_reconnect(max_retries: int = 5) -> None
    async def backfill_missing_candles(from_time: datetime, to_time: datetime) -> None

class RESTFallback:
    """Fallback to REST API when WebSocket fails"""
    async def fetch_candles(symbol: str, interval: str, limit: int) -> List[Candle]
    async def poll_candles(symbol: str, interval_seconds: int = 30) -> None

class TickAggregator:
    """Aggregates tick data into 15-minute windows"""
    async def process_tick(tick: Tick) -> None
    async def calculate_delta_volume(candle_id: int) -> DeltaVolume
    async def calculate_ofi(candle_id: int) -> float

class CandleCache:
    """Redis cache for recent candles (last 100)"""
    async def get_recent_candles(symbol: str, count: int) -> List[Candle]
    async def update_cache(candle: Candle) -> None
```

**Interfaces**:

- **Input**: Binance WebSocket streams (`wss://stream.binance.com:9443/ws/{symbol}@kline_15m`, `{symbol}@aggTrade`)
- **Output**: TimescaleDB tables (`candles_15m`, `candle_tick_agg`), Redis cache, Redis pub/sub event `candle:closed:{symbol}`

**Configuration**:
```python
BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
BINANCE_REST_URL = "https://api.binance.com/api/v3"
SYMBOLS = ["SOLUSDT"]  # Expandable to 20 pairs
RECONNECT_DELAY_SECONDS = [1, 2, 5, 10, 30]
BACKFILL_LIMIT = 1000
```

**Performance Requirements**:
- Candle receipt latency: < 2 seconds from Binance close
- Database write latency: < 100ms
- Backfill rate: 1000 candles in < 10 seconds


### 2. Analysis Pipeline

**Responsibility**: Process each candle through 5 layers of analysis to calculate CQS.

**Technology**: Python 3.11+, pandas, numpy, pandas_ta, PyWavelets

**Key Classes**:

```python
class Layer1Classifier:
    """Basic candle classification by body strength"""
    def classify(candle: Candle) -> L1Result
    def calculate_bss(candle: Candle) -> float
    def is_valid(candle: Candle) -> bool

class Layer2Morphology:
    """Morphological analysis and pattern detection"""
    def analyze(candle: Candle, history: List[Candle]) -> L2Result
    def calculate_z_score(body: float, avg_body_50: float, std_body_50: float) -> float
    def detect_single_patterns(candle: Candle) -> str  # MARUBOZU, HAMMER, etc.
    def detect_two_candle_patterns(current: Candle, previous: Candle) -> str

class Layer3Context:
    """Context filtering with volume, ATR, VWAP, Delta, OFI, FD"""
    def analyze(candle: Candle, history: List[Candle], tick_agg: TickAgg) -> L3Result
    def calculate_volume_metrics(candle: Candle, history: List[Candle]) -> VolumeMetrics
    def calculate_atr(history: List[Candle], period: int = 14) -> float
    def calculate_vwap(candles_today: List[Candle]) -> float
    def calculate_fractal_dimension(prices: np.ndarray, n: int = 40) -> float

class Layer4Patterns:
    """Multi-candle pattern recognition and wavelet analysis"""
    def analyze(candles: List[Candle]) -> L4Result
    def detect_three_white_soldiers(candles: List[Candle]) -> bool
    def detect_morning_star(candles: List[Candle]) -> bool
    def detect_bullish_flag(candles: List[Candle]) -> bool
    def detect_ascending_triangle(candles: List[Candle]) -> bool
    def wavelet_decompose(prices: np.ndarray) -> WaveletResult

class AnalysisPipeline:
    """Orchestrates all 5 layers"""
    async def process_candle(candle_id: int) -> TradingSignal
    async def run_layer1(candle: Candle) -> L1Result
    async def run_layer2(candle: Candle, l1: L1Result) -> L2Result
    async def run_layer3(candle: Candle, l1: L1Result, l2: L2Result) -> L3Result
    async def run_layer4(candles: List[Candle], l3: L3Result) -> L4Result
    async def run_layer5(candle: Candle, l1-l4: Results) -> TradingSignal
```

**Interfaces**:

- **Input**: Redis event `candle:closed:{symbol}`, TimescaleDB candle data
- **Output**: TimescaleDB `candle_analysis` table, Redis pub/sub `signal:generated:{symbol}`

**Performance Requirements**:
- Total pipeline latency: < 500ms from candle close to signal generation
- Layer 1-4 combined: < 400ms
- Layer 5 (ML inference): < 50ms


### 3. ML Service

**Responsibility**: Train, deploy, and serve XGBoost model for signal probability prediction.

**Technology**: Python 3.11+, XGBoost, scikit-learn, SHAP, joblib

**Key Classes**:

```python
class FeatureExtractor:
    """Extract 30 features from candle and analysis results"""
    def extract(candle: Candle, l1: L1Result, l2: L2Result, l3: L3Result, 
                l4: L4Result, history: List[Candle]) -> np.ndarray
    def get_feature_names() -> List[str]

class XGBoostModel:
    """Wrapper for XGBoost binary classifier"""
    def __init__(self, model_path: str)
    def predict_proba(features: np.ndarray) -> float
    def get_feature_importance() -> Dict[str, float]

class TrainingPipeline:
    """Automated model training and evaluation"""
    async def prepare_dataset(min_samples: int = 10000) -> Tuple[X, y]
    async def train_model(X_train, y_train, X_val, y_val) -> XGBoostModel
    async def walk_forward_optimize(data: pd.DataFrame) -> List[ModelMetrics]
    async def evaluate_model(model: XGBoostModel, X_test, y_test) -> ModelMetrics
    async def deploy_model(model: XGBoostModel, metrics: ModelMetrics) -> bool

class ModelRegistry:
    """Track model versions and performance"""
    async def save_model(model: XGBoostModel, version: str, metrics: ModelMetrics) -> None
    async def load_latest_model() -> XGBoostModel
    async def get_model_history() -> List[ModelVersion]

class MLService:
    """Main service orchestrator"""
    async def predict(features: np.ndarray) -> float
    async def retrain_daily() -> None
    async def monitor_performance() -> ModelMetrics
```

**Interfaces**:

- **Input**: Feature vector (30 dimensions), training data from TimescaleDB
- **Output**: ML probability (0.0-1.0), model metrics to Prometheus

**Model Configuration**:
```python
XGBOOST_PARAMS = {
    'n_estimators': 500,
    'max_depth': 6,
    'learning_rate': 0.05,
    'subsample': 0.8,
    'colsample_bytree': 0.8,
    'min_child_weight': 10,
    'gamma': 0.1,
    'reg_alpha': 0.1,
    'reg_lambda': 1.0,
    'random_state': 42,
    'eval_metric': 'auc',
    'early_stopping_rounds': 50
}

TARGET_DEFINITION = {
    'horizon_candles': 5,  # 75 minutes
    'min_gain_pct': 0.3
}

RETRAINING_SCHEDULE = {
    'time': '00:05 UTC',
    'min_new_samples': 500,
    'min_auc_improvement': -0.005
}
```

**Performance Requirements**:
- Inference latency: < 50ms (p95)
- Minimum AUC-ROC: 0.58 (target: 0.65)
- Minimum Precision @ 0.55: 0.55 (target: 0.62)
- Minimum Recall: 0.45 (target: 0.55)


### 4. Signal Dispatcher

**Responsibility**: Route trading signals to Telegram, WebSocket clients, and Trading Executor.

**Technology**: Python 3.11+, aiogram (Telegram), aioredis, FastAPI WebSocket

**Key Classes**:

```python
class RedisSubscriber:
    """Subscribe to signal events from Redis pub/sub"""
    async def subscribe(channel: str) -> None
    async def handle_signal(signal: TradingSignal) -> None

class TelegramBot:
    """Send formatted signals to Telegram"""
    async def send_signal(signal: TradingSignal) -> None
    async def send_daily_report(stats: DailyStats) -> None
    async def handle_command(command: str, args: List[str]) -> str

class WebSocketBroadcaster:
    """Broadcast signals to connected WebSocket clients"""
    async def broadcast(signal: TradingSignal) -> None
    async def add_client(websocket: WebSocket) -> None
    async def remove_client(websocket: WebSocket) -> None

class SignalFormatter:
    """Format signals for different channels"""
    def format_telegram(signal: TradingSignal) -> str
    def format_websocket(signal: TradingSignal) -> dict
    def format_daily_report(stats: DailyStats) -> str

class SignalDispatcher:
    """Main dispatcher orchestrator"""
    async def start() -> None
    async def dispatch_signal(signal: TradingSignal) -> None
    async def filter_by_threshold(signal: TradingSignal, min_cqs: int) -> bool
```

**Telegram Message Format**:
```
🟢 BULLISH SIGNAL | SOL/USDT 15m

📊 Score: CQS 78 | ML 0.67
🎯 Entry: $142.50 | SL: $140.20 | TP1: $145.80 | TP2: $148.20
📈 R/R: 1:2.8 | Size: 0.5 SOL ($71.25)

🔍 Analysis:
• Pattern: THREE_WHITE_SOLDIERS
• Morphology: MARUBOZU (Z-Score: 2.4)
• Volume: HIGH_VOLUME (2.3x avg)
• Delta: +0.42 (strong buying)
• VWAP: +0.8% above
• Market: TREND (FD: 1.28)
• Wavelet: ✅ Confirmed

⏰ 2024-03-15 14:45:00 UTC
```

**Interfaces**:

- **Input**: Redis pub/sub `signal:generated:{symbol}`
- **Output**: Telegram messages, WebSocket broadcasts, forwarding to Risk Manager

**Performance Requirements**:
- Telegram delivery: < 2 seconds from signal generation
- WebSocket broadcast: < 100ms
- Support 100+ concurrent WebSocket connections


### 5. Trading Executor

**Responsibility**: Execute approved trades on Bybit and OKX exchanges.

**Technology**: Python 3.11+, aiohttp, hmac, Tortoise-ORM

**Key Classes**:

```python
class BaseConnector(ABC):
    """Abstract base for exchange connectors"""
    @abstractmethod
    async def place_order(request: PlaceOrderRequest) -> OrderResult
    @abstractmethod
    async def cancel_order(order_id: str) -> bool
    @abstractmethod
    async def get_position(symbol: str) -> PositionInfo
    @abstractmethod
    async def set_stop_loss(symbol: str, price: float) -> bool
    @abstractmethod
    async def set_take_profit(symbol: str, price: float) -> bool
    @abstractmethod
    async def close_position(symbol: str, qty: float) -> OrderResult
    @abstractmethod
    async def get_balance() -> float
    @abstractmethod
    async def set_leverage(symbol: str, leverage: int) -> bool

class BybitConnector(BaseConnector):
    """Bybit V5 API implementation"""
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False)
    async def _sign_request(self, params: dict) -> str
    async def _request(self, method: str, endpoint: str, params: dict) -> dict

class OKXConnector(BaseConnector):
    """OKX V5 API implementation"""
    def __init__(self, api_key: str, api_secret: str, passphrase: str, testnet: bool = False)
    async def _sign_request(self, timestamp: str, method: str, path: str, body: str) -> str
    async def _request(self, method: str, endpoint: str, params: dict) -> dict
    def _convert_symbol(self, symbol: str) -> str  # SOLUSDT -> SOL-USDT-SWAP

class OrderRouter:
    """Route orders to appropriate exchange"""
    async def route(self, signal: TradingSignal, decision: RiskDecision) -> OrderResult
    def select_exchange(self, symbol: str) -> str

class TradingExecutor:
    """Main executor orchestrator"""
    async def execute_signal(signal: TradingSignal, decision: RiskDecision) -> None
    async def place_order_with_sl_tp(connector: BaseConnector, request: PlaceOrderRequest) -> OrderResult
    async def log_order(order_result: OrderResult) -> None
```

**Data Models**:

```python
@dataclass
class PlaceOrderRequest:
    symbol: str
    side: str  # "Buy" or "Sell"
    order_type: str  # "Market" or "Limit"
    quantity: float
    price: Optional[float]
    stop_loss: float
    take_profit_1: float
    take_profit_2: Optional[float]
    leverage: int
    client_order_id: str

@dataclass
class OrderResult:
    exchange: str
    exchange_order_id: str
    client_order_id: str
    symbol: str
    side: str
    filled_qty: float
    avg_price: float
    status: str
    fee: float
    timestamp: datetime
```

**Interfaces**:

- **Input**: Risk-approved signals from Risk Manager
- **Output**: Order confirmations to TimescaleDB `orders_log`, position records to `positions`

**Exchange API Endpoints**:

**Bybit V5**:
- Set Leverage: `POST /v5/position/set-leverage`
- Place Order: `POST /v5/order/create`
- Get Position: `GET /v5/position/list`
- Set Stop Loss: `POST /v5/position/trading-stop`
- Close Position: `POST /v5/order/create` (reduce-only)

**OKX V5**:
- Set Leverage: `POST /api/v5/account/set-leverage`
- Place Order: `POST /api/v5/trade/order`
- Algo Order (SL/TP): `POST /api/v5/trade/order-algo`
- Get Position: `GET /api/v5/account/positions`
- Close Position: `POST /api/v5/trade/close-position`

**Performance Requirements**:
- Order placement latency: < 500ms
- Retry failed orders up to 3 times with exponential backoff


### 6. Risk Manager

**Responsibility**: Validate signals against risk parameters before execution.

**Technology**: Python 3.11+, Tortoise-ORM

**Key Classes**:

```python
class RiskManager:
    """Validate signals against risk rules"""
    async def validate(signal: TradingSignal) -> RiskDecision
    async def check_cqs_threshold(signal: TradingSignal) -> bool
    async def check_risk_reward(signal: TradingSignal) -> bool
    async def check_suspicious_flag(signal: TradingSignal) -> bool
    async def check_position_limits(symbol: str) -> bool
    async def check_daily_loss(current_pnl: float) -> bool
    async def check_drawdown(current_equity: float, peak_equity: float) -> bool
    async def check_cooldown(last_loss_time: datetime) -> bool
    async def check_duplicate_position(symbol: str) -> bool
    async def calculate_position_size(signal: TradingSignal, balance: float) -> float

@dataclass
class RiskDecision:
    approved: bool
    reason: str
    position_size: float
    exchange: str
    risk_usd: float
```

**Risk Rules**:

```python
RISK_PARAMS = {
    'MIN_CQS_TO_TRADE': 65,
    'MIN_RR_RATIO': 1.5,
    'MAX_OPEN_POSITIONS': 3,
    'MAX_DAILY_LOSS_PCT': 2.0,  # % of account balance
    'MAX_DRAWDOWN_PCT': 5.0,
    'COOLDOWN_AFTER_LOSS_MIN': 60,
    'RISK_PER_TRADE_PCT': 1.0,  # % of balance to risk per trade
    'MAX_LEVERAGE': 5
}
```

**Position Sizing Algorithm**:

```
stop_distance = entry_price - stop_loss
risk_amount = balance × (RISK_PER_TRADE_PCT / 100)
position_size = risk_amount / stop_distance
position_size_usd = position_size × entry_price

# Cap at maximum position size
max_position_usd = balance × 0.2  # 20% of balance
if position_size_usd > max_position_usd:
    position_size = max_position_usd / entry_price
```

**Interfaces**:

- **Input**: Trading signals from Signal Dispatcher
- **Output**: Risk decisions to Trading Executor, rejection logs to TimescaleDB

**Performance Requirements**:
- Validation latency: < 100ms
- All checks must pass for approval


### 7. Position Manager

**Responsibility**: Monitor and manage open positions with trailing stops, breakeven, and partial closes.

**Technology**: Python 3.11+, asyncio, Tortoise-ORM

**Key Classes**:

```python
class PositionManager:
    """Monitor and manage open positions"""
    async def start_monitoring() -> None
    async def monitor_position(position_id: int) -> None
    async def check_trailing_stop(position: Position, mark_price: float) -> None
    async def check_breakeven(position: Position, mark_price: float) -> None
    async def check_take_profit_1(position: Position, mark_price: float) -> None
    async def update_stop_loss(position: Position, new_sl: float) -> None
    async def close_partial(position: Position, pct: float) -> None
    async def calculate_unrealised_pnl(position: Position, mark_price: float) -> float

class TrailingStopCalculator:
    """Calculate trailing stop prices"""
    def calculate_trail_price(mark_price: float, distance_pct: float, side: str) -> float
    def should_activate(entry_price: float, mark_price: float, activation_pct: float) -> bool

class BreakevenManager:
    """Manage breakeven stop moves"""
    def should_move_to_breakeven(entry_price: float, mark_price: float, activation_pct: float) -> bool
    def calculate_breakeven_price(entry_price: float, offset_pct: float = 0.1) -> float
```

**Position Management Rules**:

```python
POSITION_MANAGEMENT = {
    'MONITORING_INTERVAL_SEC': 15,
    'TRAILING_STOP_ACTIVATION_PCT': 1.0,  # Activate after 1% gain
    'TRAILING_STOP_DISTANCE_PCT': 0.5,    # Trail 0.5% behind price
    'BREAKEVEN_ACTIVATION_PCT': 0.5,      # Move to BE after 0.5% gain
    'BREAKEVEN_OFFSET_PCT': 0.1,          # BE at entry + 0.1%
    'TP1_CLOSE_PCT': 50,                  # Close 50% at TP1
    'TP2_CLOSE_PCT': 100                  # Close remaining at TP2
}
```

**Trailing Stop Logic**:

```python
# Pseudocode
gain_pct = (mark_price - entry_price) / entry_price * 100

if gain_pct >= TRAILING_STOP_ACTIVATION_PCT and not trailing_active:
    trailing_active = True
    
if trailing_active:
    trail_price = mark_price * (1 - TRAILING_STOP_DISTANCE_PCT / 100)
    if trail_price > current_stop_loss:
        update_stop_loss(trail_price)
        send_telegram_notification(f"Trailing stop updated to {trail_price}")
```

**Breakeven Logic**:

```python
# Pseudocode
gain_pct = (mark_price - entry_price) / entry_price * 100

if gain_pct >= BREAKEVEN_ACTIVATION_PCT and not be_moved:
    be_price = entry_price * (1 + BREAKEVEN_OFFSET_PCT / 100)
    update_stop_loss(be_price)
    be_moved = True
    send_telegram_notification(f"Stop moved to breakeven at {be_price}")
```

**Partial Close Logic**:

```python
# Pseudocode
if mark_price >= take_profit_1 and not tp1_closed:
    close_qty = position_qty * (TP1_CLOSE_PCT / 100)
    close_partial(close_qty)
    tp1_closed = True
    send_telegram_notification(f"TP1 hit, closed {TP1_CLOSE_PCT}% at {mark_price}")
```

**Interfaces**:

- **Input**: Open positions from TimescaleDB, mark prices from exchange connectors
- **Output**: Updated positions in TimescaleDB, stop loss updates to exchanges, Telegram notifications

**Performance Requirements**:
- Monitoring cycle: every 15 seconds
- Stop loss update latency: < 1 second


### 8. FastAPI REST and WebSocket API

**Responsibility**: Provide REST and WebSocket interfaces for external access.

**Technology**: FastAPI 0.115, uvicorn, WebSockets

**Key Endpoints**:

```python
# REST Endpoints
@app.get("/api/v1/candles")
async def get_candles(symbol: str, from_time: datetime, to_time: datetime) -> List[CandleResponse]

@app.get("/api/v1/signals")
async def get_signals(symbol: str, min_cqs: int = 60, limit: int = 100) -> List[SignalResponse]

@app.get("/api/v1/signals/{signal_id}")
async def get_signal(signal_id: int) -> SignalDetailResponse

@app.get("/api/v1/analysis/latest")
async def get_latest_analysis(symbol: str) -> AnalysisResponse

@app.get("/api/v1/stats")
async def get_stats(symbol: str, days: int = 7) -> StatsResponse

@app.get("/api/v1/health")
async def health_check() -> HealthResponse

@app.get("/metrics")
async def prometheus_metrics() -> Response

# WebSocket Endpoints
@app.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket)

@app.websocket("/ws/candles")
async def websocket_candles(websocket: WebSocket, symbol: str)

@app.websocket("/ws/positions")
async def websocket_positions(websocket: WebSocket)
```

**Response Schemas**:

```python
class CandleResponse(BaseModel):
    symbol: str
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trades_count: int

class SignalResponse(BaseModel):
    signal_id: int
    symbol: str
    timestamp: datetime
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: Optional[float]
    risk_reward: float
    cqs_final: float
    ml_probability: float
    detected_patterns: List[str]
    morphology_type: str
    market_regime: str

class SignalDetailResponse(SignalResponse):
    outcome: Optional[SignalOutcome]
    l1_result: L1Result
    l2_result: L2Result
    l3_result: L3Result
    l4_result: L4Result

class AnalysisResponse(BaseModel):
    candle: CandleResponse
    l1_result: L1Result
    l2_result: L2Result
    l3_result: L3Result
    l4_result: L4Result
    cqs_final: float

class StatsResponse(BaseModel):
    symbol: str
    period_days: int
    total_signals: int
    avg_cqs: float
    signals_by_confidence: Dict[str, int]
    win_rate: float
    avg_pnl_pct: float
    sharpe_ratio: float

class HealthResponse(BaseModel):
    status: str
    last_candle_time: datetime
    db_lag_seconds: float
    ws_connected: bool
    services: Dict[str, str]
```

**WebSocket Message Format**:

```json
{
  "type": "signal",
  "data": {
    "signal_id": 12345,
    "symbol": "SOLUSDT",
    "timestamp": "2024-03-15T14:45:00Z",
    "entry_price": 142.50,
    "stop_loss": 140.20,
    "take_profit_1": 145.80,
    "cqs_final": 78.5,
    "ml_probability": 0.67,
    "detected_patterns": ["THREE_WHITE_SOLDIERS"],
    "morphology_type": "MARUBOZU"
  }
}
```

**Interfaces**:

- **Input**: HTTP requests, WebSocket connections
- **Output**: JSON responses, WebSocket messages

**Performance Requirements**:
- REST API response time: < 200ms (p95)
- WebSocket message delivery: < 100ms
- Support 100+ concurrent WebSocket connections


### 9. Django Models and Admin

**Responsibility**: Provide ORM models and admin interface for data management.

**Technology**: Django 6.0, PostgreSQL

**Key Models**:

```python
class Candle15m(models.Model):
    """15-minute candle data"""
    symbol = models.CharField(max_length=20, db_index=True)
    open_time = models.DateTimeField(db_index=True)
    open = models.DecimalField(max_digits=20, decimal_places=8)
    high = models.DecimalField(max_digits=20, decimal_places=8)
    low = models.DecimalField(max_digits=20, decimal_places=8)
    close = models.DecimalField(max_digits=20, decimal_places=8)
    volume = models.DecimalField(max_digits=20, decimal_places=8)
    quote_volume = models.DecimalField(max_digits=20, decimal_places=8)
    trades_count = models.IntegerField()
    
    class Meta:
        db_table = 'candles_15m'
        unique_together = [['symbol', 'open_time']]
        indexes = [
            models.Index(fields=['symbol', '-open_time'])
        ]

class CandleAnalysis(models.Model):
    """Analysis results for each candle"""
    candle = models.OneToOneField(Candle15m, on_delete=models.CASCADE, primary_key=True)
    candle_class = models.CharField(max_length=20)
    bss = models.FloatField()
    morphology_type = models.CharField(max_length=50)
    z_score = models.FloatField()
    vol_ratio = models.FloatField()
    vpc = models.FloatField()
    atr_14 = models.FloatField()
    vwap_distance_pct = models.FloatField()
    delta_ratio = models.FloatField()
    ofi = models.FloatField()
    fractal_dimension = models.FloatField()
    market_regime = models.CharField(max_length=20)
    detected_patterns = models.JSONField(default=list)
    wavelet_slope = models.FloatField()
    wavelet_confirmed = models.BooleanField()
    cqs_base = models.FloatField()
    cqs_final = models.FloatField()
    is_suspicious = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'candle_analysis'

class TradingSignal(models.Model):
    """Generated trading signals"""
    candle = models.ForeignKey(Candle15m, on_delete=models.CASCADE)
    signal_id = models.AutoField(primary_key=True)
    symbol = models.CharField(max_length=20, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8)
    take_profit_1 = models.DecimalField(max_digits=20, decimal_places=8)
    take_profit_2 = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    risk_reward = models.FloatField()
    cqs_final = models.FloatField(db_index=True)
    ml_probability = models.FloatField()
    confidence_level = models.CharField(max_length=10)
    
    class Meta:
        db_table = 'trading_signals'
        indexes = [
            models.Index(fields=['symbol', '-timestamp']),
            models.Index(fields=['-cqs_final'])
        ]

class SignalOutcome(models.Model):
    """Outcome tracking for signals"""
    signal = models.OneToOneField(TradingSignal, on_delete=models.CASCADE, primary_key=True)
    evaluation_time = models.DateTimeField()
    max_price_5candles = models.DecimalField(max_digits=20, decimal_places=8)
    pnl_pct = models.FloatField()
    hit_tp1 = models.BooleanField()
    hit_tp2 = models.BooleanField()
    hit_sl = models.BooleanField()
    max_favorable_excursion = models.FloatField()
    max_adverse_excursion = models.FloatField()
    
    class Meta:
        db_table = 'signal_outcomes'

class Position(models.Model):
    """Open and closed positions"""
    position_id = models.AutoField(primary_key=True)
    signal = models.ForeignKey(TradingSignal, on_delete=models.SET_NULL, null=True)
    exchange = models.CharField(max_length=20)
    symbol = models.CharField(max_length=20, db_index=True)
    side = models.CharField(max_length=10)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    entry_price = models.DecimalField(max_digits=20, decimal_places=8)
    stop_loss = models.DecimalField(max_digits=20, decimal_places=8)
    take_profit_1 = models.DecimalField(max_digits=20, decimal_places=8)
    take_profit_2 = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    leverage = models.IntegerField()
    open_time = models.DateTimeField(auto_now_add=True)
    close_time = models.DateTimeField(null=True)
    exit_price = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    realised_pnl = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    net_pnl = models.DecimalField(max_digits=20, decimal_places=8, null=True)
    exit_reason = models.CharField(max_length=50, null=True)
    trailing_active = models.BooleanField(default=False)
    be_moved = models.BooleanField(default=False)
    tp1_closed = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'positions'
        indexes = [
            models.Index(fields=['symbol', '-open_time']),
            models.Index(fields=['close_time'])
        ]

class OrderLog(models.Model):
    """Order execution log"""
    order_id = models.AutoField(primary_key=True)
    position = models.ForeignKey(Position, on_delete=models.CASCADE)
    exchange = models.CharField(max_length=20)
    exchange_order_id = models.CharField(max_length=100)
    client_order_id = models.CharField(max_length=100)
    symbol = models.CharField(max_length=20)
    side = models.CharField(max_length=10)
    order_type = models.CharField(max_length=20)
    quantity = models.DecimalField(max_digits=20, decimal_places=8)
    filled_qty = models.DecimalField(max_digits=20, decimal_places=8)
    avg_price = models.DecimalField(max_digits=20, decimal_places=8)
    status = models.CharField(max_length=20)
    fee = models.DecimalField(max_digits=20, decimal_places=8)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'orders_log'

class DailyPnL(models.Model):
    """Daily PnL snapshots"""
    date = models.DateField(primary_key=True)
    starting_balance = models.DecimalField(max_digits=20, decimal_places=8)
    ending_balance = models.DecimalField(max_digits=20, decimal_places=8)
    realised_pnl = models.DecimalField(max_digits=20, decimal_places=8)
    fees_paid = models.DecimalField(max_digits=20, decimal_places=8)
    trade_count = models.IntegerField()
    win_count = models.IntegerField()
    loss_count = models.IntegerField()
    win_rate = models.FloatField()
    max_drawdown = models.FloatField()
    
    class Meta:
        db_table = 'daily_pnl'

class MLModel(models.Model):
    """ML model registry"""
    version = models.CharField(max_length=50, primary_key=True)
    trained_at = models.DateTimeField(auto_now_add=True)
    auc_roc = models.FloatField()
    precision = models.FloatField()
    recall = models.FloatField()
    f1_score = models.FloatField()
    is_active = models.BooleanField(default=False)
    model_path = models.CharField(max_length=255)
    
    class Meta:
        db_table = 'ml_models'

class ExchangeAPIKey(models.Model):
    """Encrypted exchange API keys"""
    exchange = models.CharField(max_length=20, primary_key=True)
    api_key = models.CharField(max_length=255)
    api_secret_encrypted = models.BinaryField()
    passphrase_encrypted = models.BinaryField(null=True)
    testnet = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'exchange_api_keys'
```

**Django Admin Configuration**:

```python
@admin.register(TradingSignal)
class TradingSignalAdmin(admin.ModelAdmin):
    list_display = ['signal_id', 'symbol', 'timestamp', 'cqs_final', 'ml_probability', 'confidence_level']
    list_filter = ['symbol', 'confidence_level', 'timestamp']
    search_fields = ['signal_id', 'symbol']
    readonly_fields = ['signal_id', 'timestamp']

@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ['position_id', 'symbol', 'side', 'entry_price', 'realised_pnl', 'exit_reason', 'open_time']
    list_filter = ['exchange', 'symbol', 'exit_reason']
    search_fields = ['position_id', 'symbol']
```


## Data Models

### TimescaleDB Schema

**Hypertable: candles_15m**

```sql
CREATE TABLE candles_15m (
    id BIGSERIAL,
    symbol VARCHAR(20) NOT NULL,
    open_time TIMESTAMPTZ NOT NULL,
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

SELECT create_hypertable('candles_15m', 'open_time', chunk_time_interval => INTERVAL '7 days');
CREATE INDEX idx_candles_symbol_time ON candles_15m (symbol, open_time DESC);
```

**Table: candle_tick_agg**

```sql
CREATE TABLE candle_tick_agg (
    candle_id BIGINT PRIMARY KEY REFERENCES candles_15m(id) ON DELETE CASCADE,
    buy_volume NUMERIC(20, 8) NOT NULL,
    sell_volume NUMERIC(20, 8) NOT NULL,
    delta NUMERIC(20, 8) NOT NULL,
    delta_ratio NUMERIC(10, 6) NOT NULL,
    avg_ofi NUMERIC(10, 6) NOT NULL,
    tick_count INTEGER NOT NULL
);
```

**Table: candle_analysis**

```sql
CREATE TABLE candle_analysis (
    candle_id BIGINT PRIMARY KEY REFERENCES candles_15m(id) ON DELETE CASCADE,
    candle_class VARCHAR(20) NOT NULL,
    bss NUMERIC(10, 4) NOT NULL,
    morphology_type VARCHAR(50),
    z_score NUMERIC(10, 4),
    vol_ratio NUMERIC(10, 4),
    vpc NUMERIC(10, 4),
    atr_14 NUMERIC(20, 8),
    vwap_distance_pct NUMERIC(10, 4),
    delta_ratio NUMERIC(10, 6),
    ofi NUMERIC(10, 6),
    fractal_dimension NUMERIC(10, 6),
    market_regime VARCHAR(20),
    detected_patterns JSONB DEFAULT '[]',
    wavelet_slope NUMERIC(10, 6),
    wavelet_confirmed BOOLEAN DEFAULT FALSE,
    cqs_base NUMERIC(10, 4),
    cqs_final NUMERIC(10, 4),
    is_suspicious BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_analysis_cqs ON candle_analysis (cqs_final DESC);
CREATE INDEX idx_analysis_regime ON candle_analysis (market_regime);
```

**Table: trading_signals**

```sql
CREATE TABLE trading_signals (
    signal_id BIGSERIAL PRIMARY KEY,
    candle_id BIGINT REFERENCES candles_15m(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    entry_price NUMERIC(20, 8) NOT NULL,
    stop_loss NUMERIC(20, 8) NOT NULL,
    take_profit_1 NUMERIC(20, 8) NOT NULL,
    take_profit_2 NUMERIC(20, 8),
    risk_reward NUMERIC(10, 4) NOT NULL,
    cqs_final NUMERIC(10, 4) NOT NULL,
    ml_probability NUMERIC(10, 6) NOT NULL,
    confidence_level VARCHAR(10) NOT NULL,
    detected_patterns JSONB DEFAULT '[]',
    morphology_type VARCHAR(50),
    market_regime VARCHAR(20),
    vol_ratio NUMERIC(10, 4),
    delta_ratio NUMERIC(10, 6),
    vwap_distance_pct NUMERIC(10, 4),
    fractal_dimension NUMERIC(10, 6),
    wavelet_confirmed BOOLEAN
);

CREATE INDEX idx_signals_symbol_time ON trading_signals (symbol, timestamp DESC);
CREATE INDEX idx_signals_cqs ON trading_signals (cqs_final DESC);
CREATE INDEX idx_signals_timestamp ON trading_signals (timestamp DESC);
```

**Table: signal_outcomes**

```sql
CREATE TABLE signal_outcomes (
    signal_id BIGINT PRIMARY KEY REFERENCES trading_signals(signal_id) ON DELETE CASCADE,
    evaluation_time TIMESTAMPTZ NOT NULL,
    max_price_5candles NUMERIC(20, 8) NOT NULL,
    pnl_pct NUMERIC(10, 4) NOT NULL,
    hit_tp1 BOOLEAN NOT NULL,
    hit_tp2 BOOLEAN NOT NULL,
    hit_sl BOOLEAN NOT NULL,
    max_favorable_excursion NUMERIC(10, 4) NOT NULL,
    max_adverse_excursion NUMERIC(10, 4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Table: positions**

```sql
CREATE TABLE positions (
    position_id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT REFERENCES trading_signals(signal_id) ON DELETE SET NULL,
    exchange VARCHAR(20) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity NUMERIC(20, 8) NOT NULL,
    entry_price NUMERIC(20, 8) NOT NULL,
    stop_loss NUMERIC(20, 8) NOT NULL,
    take_profit_1 NUMERIC(20, 8) NOT NULL,
    take_profit_2 NUMERIC(20, 8),
    leverage INTEGER NOT NULL,
    open_time TIMESTAMPTZ DEFAULT NOW(),
    close_time TIMESTAMPTZ,
    exit_price NUMERIC(20, 8),
    realised_pnl NUMERIC(20, 8),
    net_pnl NUMERIC(20, 8),
    exit_reason VARCHAR(50),
    trailing_active BOOLEAN DEFAULT FALSE,
    be_moved BOOLEAN DEFAULT FALSE,
    tp1_closed BOOLEAN DEFAULT FALSE,
    unrealised_pnl NUMERIC(20, 8)
);

CREATE INDEX idx_positions_symbol_open ON positions (symbol, open_time DESC);
CREATE INDEX idx_positions_close ON positions (close_time DESC) WHERE close_time IS NOT NULL;
CREATE INDEX idx_positions_open ON positions (open_time DESC) WHERE close_time IS NULL;
```

**Table: orders_log**

```sql
CREATE TABLE orders_log (
    order_id BIGSERIAL PRIMARY KEY,
    position_id BIGINT REFERENCES positions(position_id) ON DELETE CASCADE,
    exchange VARCHAR(20) NOT NULL,
    exchange_order_id VARCHAR(100) NOT NULL,
    client_order_id VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    quantity NUMERIC(20, 8) NOT NULL,
    filled_qty NUMERIC(20, 8) NOT NULL,
    avg_price NUMERIC(20, 8) NOT NULL,
    status VARCHAR(20) NOT NULL,
    fee NUMERIC(20, 8) NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_orders_position ON orders_log (position_id);
CREATE INDEX idx_orders_timestamp ON orders_log (timestamp DESC);
```

**Table: daily_pnl**

```sql
CREATE TABLE daily_pnl (
    date DATE PRIMARY KEY,
    starting_balance NUMERIC(20, 8) NOT NULL,
    ending_balance NUMERIC(20, 8) NOT NULL,
    realised_pnl NUMERIC(20, 8) NOT NULL,
    fees_paid NUMERIC(20, 8) NOT NULL,
    trade_count INTEGER NOT NULL,
    win_count INTEGER NOT NULL,
    loss_count INTEGER NOT NULL,
    win_rate NUMERIC(10, 4) NOT NULL,
    max_drawdown NUMERIC(10, 4) NOT NULL
);
```

**Table: ml_models**

```sql
CREATE TABLE ml_models (
    version VARCHAR(50) PRIMARY KEY,
    trained_at TIMESTAMPTZ DEFAULT NOW(),
    auc_roc NUMERIC(10, 6) NOT NULL,
    precision NUMERIC(10, 6) NOT NULL,
    recall NUMERIC(10, 6) NOT NULL,
    f1_score NUMERIC(10, 6) NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    model_path VARCHAR(255) NOT NULL
);
```

**Table: exchange_api_keys**

```sql
CREATE TABLE exchange_api_keys (
    exchange VARCHAR(20) PRIMARY KEY,
    api_key VARCHAR(255) NOT NULL,
    api_secret_encrypted BYTEA NOT NULL,
    passphrase_encrypted BYTEA,
    testnet BOOLEAN DEFAULT FALSE
);
```


### Tortoise-ORM Async Models

**Purpose**: Async ORM for microservices (mirrors Django schema)

```python
from tortoise import fields
from tortoise.models import Model

class Candle15m(Model):
    id = fields.BigIntField(pk=True)
    symbol = fields.CharField(max_length=20, index=True)
    open_time = fields.DatetimeField(index=True)
    open = fields.DecimalField(max_digits=20, decimal_places=8)
    high = fields.DecimalField(max_digits=20, decimal_places=8)
    low = fields.DecimalField(max_digits=20, decimal_places=8)
    close = fields.DecimalField(max_digits=20, decimal_places=8)
    volume = fields.DecimalField(max_digits=20, decimal_places=8)
    quote_volume = fields.DecimalField(max_digits=20, decimal_places=8)
    trades_count = fields.IntField()
    created_at = fields.DatetimeField(auto_now_add=True)
    
    class Meta:
        table = "candles_15m"
        unique_together = (("symbol", "open_time"),)

class CandleAnalysis(Model):
    candle = fields.OneToOneField("models.Candle15m", pk=True, on_delete=fields.CASCADE)
    candle_class = fields.CharField(max_length=20)
    bss = fields.FloatField()
    morphology_type = fields.CharField(max_length=50, null=True)
    z_score = fields.FloatField(null=True)
    vol_ratio = fields.FloatField(null=True)
    vpc = fields.FloatField(null=True)
    atr_14 = fields.FloatField(null=True)
    vwap_distance_pct = fields.FloatField(null=True)
    delta_ratio = fields.FloatField(null=True)
    ofi = fields.FloatField(null=True)
    fractal_dimension = fields.FloatField(null=True)
    market_regime = fields.CharField(max_length=20, null=True)
    detected_patterns = fields.JSONField(default=list)
    wavelet_slope = fields.FloatField(null=True)
    wavelet_confirmed = fields.BooleanField(default=False)
    cqs_base = fields.FloatField(null=True)
    cqs_final = fields.FloatField(null=True)
    is_suspicious = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    
    class Meta:
        table = "candle_analysis"

class TradingSignal(Model):
    signal_id = fields.BigIntField(pk=True)
    candle = fields.ForeignKeyField("models.Candle15m", on_delete=fields.CASCADE)
    symbol = fields.CharField(max_length=20, index=True)
    timestamp = fields.DatetimeField(auto_now_add=True, index=True)
    entry_price = fields.DecimalField(max_digits=20, decimal_places=8)
    stop_loss = fields.DecimalField(max_digits=20, decimal_places=8)
    take_profit_1 = fields.DecimalField(max_digits=20, decimal_places=8)
    take_profit_2 = fields.DecimalField(max_digits=20, decimal_places=8, null=True)
    risk_reward = fields.FloatField()
    cqs_final = fields.FloatField(index=True)
    ml_probability = fields.FloatField()
    confidence_level = fields.CharField(max_length=10)
    detected_patterns = fields.JSONField(default=list)
    morphology_type = fields.CharField(max_length=50, null=True)
    market_regime = fields.CharField(max_length=20, null=True)
    
    class Meta:
        table = "trading_signals"

class Position(Model):
    position_id = fields.BigIntField(pk=True)
    signal = fields.ForeignKeyField("models.TradingSignal", on_delete=fields.SET_NULL, null=True)
    exchange = fields.CharField(max_length=20)
    symbol = fields.CharField(max_length=20, index=True)
    side = fields.CharField(max_length=10)
    quantity = fields.DecimalField(max_digits=20, decimal_places=8)
    entry_price = fields.DecimalField(max_digits=20, decimal_places=8)
    stop_loss = fields.DecimalField(max_digits=20, decimal_places=8)
    take_profit_1 = fields.DecimalField(max_digits=20, decimal_places=8)
    take_profit_2 = fields.DecimalField(max_digits=20, decimal_places=8, null=True)
    leverage = fields.IntField()
    open_time = fields.DatetimeField(auto_now_add=True)
    close_time = fields.DatetimeField(null=True)
    exit_price = fields.DecimalField(max_digits=20, decimal_places=8, null=True)
    realised_pnl = fields.DecimalField(max_digits=20, decimal_places=8, null=True)
    net_pnl = fields.DecimalField(max_digits=20, decimal_places=8, null=True)
    exit_reason = fields.CharField(max_length=50, null=True)
    trailing_active = fields.BooleanField(default=False)
    be_moved = fields.BooleanField(default=False)
    tp1_closed = fields.BooleanField(default=False)
    unrealised_pnl = fields.DecimalField(max_digits=20, decimal_places=8, null=True)
    
    class Meta:
        table = "positions"
```


## API Design

### REST API Specification

**Base URL**: `http://localhost:8000/api/v1`

**Authentication**: None (internal network only, add JWT for production)

#### GET /candles

Retrieve historical candle data.

**Query Parameters**:
- `symbol` (required): Trading pair (e.g., "SOLUSDT")
- `from` (required): Start time (ISO 8601 format)
- `to` (required): End time (ISO 8601 format)
- `limit` (optional): Max results (default: 1000)

**Response**:
```json
{
  "candles": [
    {
      "symbol": "SOLUSDT",
      "open_time": "2024-03-15T14:45:00Z",
      "open": 142.30,
      "high": 142.85,
      "low": 142.10,
      "close": 142.50,
      "volume": 1250.5,
      "quote_volume": 178125.75,
      "trades_count": 342
    }
  ],
  "count": 1
}
```

#### GET /signals

Retrieve trading signals.

**Query Parameters**:
- `symbol` (optional): Filter by trading pair
- `min_cqs` (optional): Minimum CQS score (default: 60)
- `from` (optional): Start time
- `to` (optional): End time
- `limit` (optional): Max results (default: 100)

**Response**:
```json
{
  "signals": [
    {
      "signal_id": 12345,
      "symbol": "SOLUSDT",
      "timestamp": "2024-03-15T14:45:00Z",
      "entry_price": 142.50,
      "stop_loss": 140.20,
      "take_profit_1": 145.80,
      "take_profit_2": 148.20,
      "risk_reward": 2.8,
      "cqs_final": 78.5,
      "ml_probability": 0.67,
      "confidence_level": "MEDIUM",
      "detected_patterns": ["THREE_WHITE_SOLDIERS"],
      "morphology_type": "MARUBOZU",
      "market_regime": "TREND"
    }
  ],
  "count": 1
}
```

#### GET /signals/{signal_id}

Retrieve detailed signal information including outcome.

**Response**:
```json
{
  "signal_id": 12345,
  "symbol": "SOLUSDT",
  "timestamp": "2024-03-15T14:45:00Z",
  "entry_price": 142.50,
  "stop_loss": 140.20,
  "take_profit_1": 145.80,
  "cqs_final": 78.5,
  "ml_probability": 0.67,
  "l1_result": {
    "candle_class": "STRONG_BULLISH",
    "bss": 85.2,
    "body": 2.20,
    "upper_shadow_ratio": 0.08,
    "lower_shadow_ratio": 0.07
  },
  "l2_result": {
    "morphology_type": "MARUBOZU",
    "z_score": 2.4,
    "z_score_bonus": 10,
    "pattern_bonus": 20,
    "total_l2_score": 30
  },
  "l3_result": {
    "vol_ratio": 2.3,
    "vpc": 1.96,
    "atr_14": 1.85,
    "vwap_distance_pct": 0.8,
    "delta_ratio": 0.42,
    "ofi": 0.35,
    "fractal_dimension": 1.28,
    "market_regime": "TREND",
    "is_suspicious": false,
    "total_l3_score": 42
  },
  "l4_result": {
    "detected_patterns": ["THREE_WHITE_SOLDIERS"],
    "pattern_weights": {"THREE_WHITE_SOLDIERS": 25},
    "wavelet_slope": 0.15,
    "wavelet_confirmed": true,
    "total_l4_score": 33
  },
  "outcome": {
    "evaluation_time": "2024-03-15T16:00:00Z",
    "max_price_5candles": 146.20,
    "pnl_pct": 2.6,
    "hit_tp1": true,
    "hit_tp2": false,
    "hit_sl": false,
    "max_favorable_excursion": 2.6,
    "max_adverse_excursion": -0.3
  }
}
```

#### GET /analysis/latest

Get latest candle analysis for a symbol.

**Query Parameters**:
- `symbol` (required): Trading pair

**Response**:
```json
{
  "candle": {
    "symbol": "SOLUSDT",
    "open_time": "2024-03-15T14:45:00Z",
    "open": 142.30,
    "high": 142.85,
    "low": 142.10,
    "close": 142.50,
    "volume": 1250.5
  },
  "analysis": {
    "candle_class": "STRONG_BULLISH",
    "bss": 85.2,
    "morphology_type": "MARUBOZU",
    "z_score": 2.4,
    "vol_ratio": 2.3,
    "cqs_final": 78.5,
    "market_regime": "TREND",
    "detected_patterns": ["THREE_WHITE_SOLDIERS"]
  }
}
```

#### GET /stats

Get aggregate statistics for a symbol.

**Query Parameters**:
- `symbol` (required): Trading pair
- `days` (optional): Number of days to analyze (default: 7)

**Response**:
```json
{
  "symbol": "SOLUSDT",
  "period_days": 7,
  "total_signals": 42,
  "avg_cqs": 72.3,
  "signals_by_confidence": {
    "HIGH": 8,
    "MEDIUM": 28,
    "LOW": 6
  },
  "win_rate": 0.62,
  "avg_pnl_pct": 1.4,
  "sharpe_ratio": 1.8,
  "max_drawdown": -3.2
}
```

#### GET /health

System health check.

**Response**:
```json
{
  "status": "healthy",
  "last_candle_time": "2024-03-15T14:45:00Z",
  "db_lag_seconds": 1.2,
  "ws_connected": true,
  "services": {
    "data_ingestion": "running",
    "analysis_pipeline": "running",
    "ml_service": "running",
    "signal_dispatcher": "running",
    "trade_executor": "running",
    "position_manager": "running"
  }
}
```


### WebSocket API Specification

**Base URL**: `ws://localhost:8000/ws`

#### WS /signals

Real-time trading signal stream.

**Connection**:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/signals');
```

**Message Format**:
```json
{
  "type": "signal",
  "data": {
    "signal_id": 12345,
    "symbol": "SOLUSDT",
    "timestamp": "2024-03-15T14:45:00Z",
    "entry_price": 142.50,
    "stop_loss": 140.20,
    "take_profit_1": 145.80,
    "take_profit_2": 148.20,
    "risk_reward": 2.8,
    "cqs_final": 78.5,
    "ml_probability": 0.67,
    "confidence_level": "MEDIUM",
    "detected_patterns": ["THREE_WHITE_SOLDIERS"],
    "morphology_type": "MARUBOZU",
    "market_regime": "TREND"
  }
}
```

#### WS /candles?symbol={symbol}

Real-time candle and analysis stream for a specific symbol.

**Connection**:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/candles?symbol=SOLUSDT');
```

**Message Format**:
```json
{
  "type": "candle_analysis",
  "data": {
    "candle": {
      "symbol": "SOLUSDT",
      "open_time": "2024-03-15T14:45:00Z",
      "open": 142.30,
      "high": 142.85,
      "low": 142.10,
      "close": 142.50,
      "volume": 1250.5
    },
    "l1_result": {
      "candle_class": "STRONG_BULLISH",
      "bss": 85.2
    },
    "l2_result": {
      "morphology_type": "MARUBOZU",
      "z_score": 2.4
    },
    "l3_result": {
      "vol_ratio": 2.3,
      "market_regime": "TREND"
    },
    "l4_result": {
      "detected_patterns": ["THREE_WHITE_SOLDIERS"]
    },
    "cqs_final": 78.5
  }
}
```

#### WS /positions

Real-time position updates stream.

**Connection**:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/positions');
```

**Message Types**:

**Position Opened**:
```json
{
  "type": "position_opened",
  "data": {
    "position_id": 567,
    "symbol": "SOLUSDT",
    "side": "Buy",
    "quantity": 0.5,
    "entry_price": 142.50,
    "stop_loss": 140.20,
    "take_profit_1": 145.80,
    "leverage": 3,
    "open_time": "2024-03-15T14:45:30Z"
  }
}
```

**Stop Loss Updated**:
```json
{
  "type": "stop_loss_updated",
  "data": {
    "position_id": 567,
    "old_stop_loss": 140.20,
    "new_stop_loss": 142.60,
    "reason": "trailing_stop",
    "timestamp": "2024-03-15T15:00:00Z"
  }
}
```

**Partial Close**:
```json
{
  "type": "partial_close",
  "data": {
    "position_id": 567,
    "closed_qty": 0.25,
    "remaining_qty": 0.25,
    "exit_price": 145.80,
    "pnl": 0.825,
    "reason": "tp1_hit",
    "timestamp": "2024-03-15T15:15:00Z"
  }
}
```

**Position Closed**:
```json
{
  "type": "position_closed",
  "data": {
    "position_id": 567,
    "exit_price": 148.20,
    "realised_pnl": 2.85,
    "net_pnl": 2.78,
    "exit_reason": "tp2_hit",
    "close_time": "2024-03-15T15:30:00Z"
  }
}
```


## Integration Points

### Binance WebSocket API

**Purpose**: Real-time OHLCV and tick data streaming

**Endpoints**:
- Kline/Candlestick Stream: `wss://stream.binance.com:9443/ws/{symbol}@kline_15m`
- Aggregate Trade Stream: `wss://stream.binance.com:9443/ws/{symbol}@aggTrade`

**Kline Message Format**:
```json
{
  "e": "kline",
  "E": 1710513900000,
  "s": "SOLUSDT",
  "k": {
    "t": 1710513000000,
    "T": 1710513899999,
    "s": "SOLUSDT",
    "i": "15m",
    "f": 100,
    "L": 200,
    "o": "142.30",
    "c": "142.50",
    "h": "142.85",
    "l": "142.10",
    "v": "1250.5",
    "n": 342,
    "x": true,
    "q": "178125.75",
    "V": "625.3",
    "Q": "89062.88"
  }
}
```

**Aggregate Trade Message Format**:
```json
{
  "e": "aggTrade",
  "E": 1710513123456,
  "s": "SOLUSDT",
  "a": 12345,
  "p": "142.45",
  "q": "10.5",
  "f": 100,
  "l": 105,
  "T": 1710513123450,
  "m": false
}
```

**Connection Management**:
- Auto-reconnect with exponential backoff: 1s, 2s, 5s, 10s, 30s
- Ping/pong every 3 minutes to keep connection alive
- On disconnect > 60s, trigger alert

### Binance REST API

**Purpose**: Backfill missing candles, fallback when WebSocket fails

**Endpoints**:
- Get Klines: `GET https://api.binance.com/api/v3/klines`

**Parameters**:
- `symbol`: Trading pair (e.g., "SOLUSDT")
- `interval`: Timeframe (e.g., "15m")
- `startTime`: Start timestamp (milliseconds)
- `endTime`: End timestamp (milliseconds)
- `limit`: Max 1000 candles per request

**Response Format**:
```json
[
  [
    1710513000000,      // Open time
    "142.30",           // Open
    "142.85",           // High
    "142.10",           // Low
    "142.50",           // Close
    "1250.5",           // Volume
    1710513899999,      // Close time
    "178125.75",        // Quote asset volume
    342,                // Number of trades
    "625.3",            // Taker buy base asset volume
    "89062.88",         // Taker buy quote asset volume
    "0"                 // Ignore
  ]
]
```

**Rate Limits**:
- Weight: 1 per request
- Limit: 1200 requests per minute
- Backfill strategy: Batch requests with 1s delay between


### Bybit V5 API

**Purpose**: Execute trades on Bybit exchange

**Base URL**: 
- Mainnet: `https://api.bybit.com`
- Testnet: `https://api-testnet.bybit.com`

**Authentication**: HMAC-SHA256 signature

**Signature Generation**:
```python
import hmac
import hashlib
import time

timestamp = str(int(time.time() * 1000))
recv_window = "5000"
param_str = f"{timestamp}{api_key}{recv_window}{params}"
signature = hmac.new(
    api_secret.encode('utf-8'),
    param_str.encode('utf-8'),
    hashlib.sha256
).hexdigest()

headers = {
    "X-BAPI-API-KEY": api_key,
    "X-BAPI-SIGN": signature,
    "X-BAPI-TIMESTAMP": timestamp,
    "X-BAPI-RECV-WINDOW": recv_window
}
```

**Key Endpoints**:

**Set Leverage**:
```
POST /v5/position/set-leverage
Body: {
  "category": "linear",
  "symbol": "SOLUSDT",
  "buyLeverage": "3",
  "sellLeverage": "3"
}
```

**Place Order**:
```
POST /v5/order/create
Body: {
  "category": "linear",
  "symbol": "SOLUSDT",
  "side": "Buy",
  "orderType": "Market",
  "qty": "0.5",
  "stopLoss": "140.20",
  "takeProfit": "145.80",
  "slTriggerBy": "MarkPrice",
  "tpTriggerBy": "MarkPrice",
  "orderLinkId": "candlescout_12345"
}
```

**Get Position**:
```
GET /v5/position/list?category=linear&symbol=SOLUSDT
```

**Set Trading Stop**:
```
POST /v5/position/trading-stop
Body: {
  "category": "linear",
  "symbol": "SOLUSDT",
  "stopLoss": "142.60",
  "slTriggerBy": "MarkPrice",
  "positionIdx": 0
}
```

**Close Position**:
```
POST /v5/order/create
Body: {
  "category": "linear",
  "symbol": "SOLUSDT",
  "side": "Sell",
  "orderType": "Market",
  "qty": "0.5",
  "reduceOnly": true
}
```

**Get Balance**:
```
GET /v5/account/wallet-balance?accountType=UNIFIED
```

**Response Format**:
```json
{
  "retCode": 0,
  "retMsg": "OK",
  "result": {
    "orderId": "1234567890",
    "orderLinkId": "candlescout_12345"
  },
  "time": 1710513123456
}
```

**Error Handling**:
- `retCode != 0`: Log error and retry up to 3 times
- Common errors: 10001 (parameter error), 10004 (sign error), 110001 (insufficient balance)


### OKX V5 API

**Purpose**: Execute trades on OKX exchange

**Base URL**:
- Mainnet: `https://www.okx.com`
- Testnet: `https://www.okx.com` (use `x-simulated-trading: 1` header)

**Authentication**: HMAC-SHA256 signature

**Signature Generation**:
```python
import hmac
import hashlib
import base64
from datetime import datetime

timestamp = datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'
method = "POST"
request_path = "/api/v5/trade/order"
body = '{"instId":"SOL-USDT-SWAP","tdMode":"cross","side":"buy","ordType":"market","sz":"0.5"}'

prehash = timestamp + method + request_path + body
signature = base64.b64encode(
    hmac.new(
        api_secret.encode('utf-8'),
        prehash.encode('utf-8'),
        hashlib.sha256
    ).digest()
).decode()

headers = {
    "OK-ACCESS-KEY": api_key,
    "OK-ACCESS-SIGN": signature,
    "OK-ACCESS-TIMESTAMP": timestamp,
    "OK-ACCESS-PASSPHRASE": passphrase,
    "Content-Type": "application/json"
}
```

**Symbol Format Conversion**:
```python
def convert_symbol(binance_symbol: str) -> str:
    # SOLUSDT -> SOL-USDT-SWAP
    base = binance_symbol[:-4]  # Remove "USDT"
    return f"{base}-USDT-SWAP"
```

**Key Endpoints**:

**Set Leverage**:
```
POST /api/v5/account/set-leverage
Body: {
  "instId": "SOL-USDT-SWAP",
  "lever": "3",
  "mgnMode": "cross"
}
```

**Place Order**:
```
POST /api/v5/trade/order
Body: {
  "instId": "SOL-USDT-SWAP",
  "tdMode": "cross",
  "side": "buy",
  "ordType": "market",
  "sz": "0.5",
  "clOrdId": "candlescout_12345"
}
```

**Place Algo Order (Stop Loss / Take Profit)**:
```
POST /api/v5/trade/order-algo
Body: {
  "instId": "SOL-USDT-SWAP",
  "tdMode": "cross",
  "side": "sell",
  "ordType": "oco",
  "sz": "0.5",
  "slTriggerPx": "140.20",
  "slOrdPx": "-1",
  "tpTriggerPx": "145.80",
  "tpOrdPx": "-1"
}
```

**Get Position**:
```
GET /api/v5/account/positions?instId=SOL-USDT-SWAP
```

**Close Position**:
```
POST /api/v5/trade/close-position
Body: {
  "instId": "SOL-USDT-SWAP",
  "mgnMode": "cross"
}
```

**Get Balance**:
```
GET /api/v5/account/balance
```

**Response Format**:
```json
{
  "code": "0",
  "msg": "",
  "data": [
    {
      "ordId": "1234567890",
      "clOrdId": "candlescout_12345",
      "sCode": "0",
      "sMsg": ""
    }
  ]
}
```

**Error Handling**:
- `code != "0"`: Log error and retry up to 3 times
- Common errors: 50000 (system error), 51000 (parameter error), 51008 (insufficient balance)


### Telegram Bot API

**Purpose**: Send trading signals and system notifications to Telegram

**Base URL**: `https://api.telegram.org/bot{token}`

**Key Methods**:

**Send Message**:
```
POST /sendMessage
Body: {
  "chat_id": "{chat_id}",
  "text": "🟢 BULLISH SIGNAL | SOL/USDT 15m\n\n📊 Score: CQS 78 | ML 0.67\n...",
  "parse_mode": "HTML"
}
```

**Send Photo** (for charts):
```
POST /sendPhoto
Body: {
  "chat_id": "{chat_id}",
  "photo": "{file_id or URL}",
  "caption": "Signal #12345 chart"
}
```

**Bot Commands**:

```python
COMMANDS = {
    "/status": "Show system status and last candle time",
    "/signals": "Show last N signals (default: 10)",
    "/setfilter": "Set minimum CQS threshold (e.g., /setfilter cqs=70)",
    "/stats": "Show statistics for last N days (default: 7)",
    "/current": "Show current candle analysis for SOL/USDT"
}
```

**Command Handlers**:

```python
@bot.message_handler(commands=['status'])
async def handle_status(message):
    health = await get_health_status()
    response = f"""
🟢 System Status: {health['status']}
⏰ Last Candle: {health['last_candle_time']}
📊 DB Lag: {health['db_lag_seconds']}s
🔌 WebSocket: {'Connected' if health['ws_connected'] else 'Disconnected'}
    """
    await bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['signals'])
async def handle_signals(message):
    args = message.text.split()
    limit = int(args[1]) if len(args) > 1 else 10
    signals = await get_recent_signals(limit)
    response = format_signals_list(signals)
    await bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['setfilter'])
async def handle_setfilter(message):
    # Parse: /setfilter cqs=70
    args = message.text.split()
    if len(args) < 2:
        await bot.send_message(message.chat.id, "Usage: /setfilter cqs=70")
        return
    
    param = args[1].split('=')
    if param[0] == 'cqs':
        min_cqs = int(param[1])
        await update_user_filter(message.chat.id, min_cqs)
        await bot.send_message(message.chat.id, f"✅ Filter updated: CQS ≥ {min_cqs}")
```

**Daily Report Format**:
```
📊 Daily Report - 2024-03-15

💰 PnL: +$125.50 (+2.1%)
📈 Trades: 8 (5W / 3L)
🎯 Win Rate: 62.5%
📉 Max Drawdown: -1.2%

🔝 Best Trade: +$45.20 (Signal #12345)
📉 Worst Trade: -$18.30 (Signal #12340)

⚡ Signals Generated: 12
✅ Signals Traded: 8
🚫 Signals Rejected: 4 (Risk limits)
```


### Redis Pub/Sub and Streams

**Purpose**: Event-driven communication between microservices

**Channels**:

```python
REDIS_CHANNELS = {
    'candle:closed:{symbol}': 'Published when 15m candle closes',
    'signal:generated:{symbol}': 'Published when trading signal is generated',
    'position:opened:{position_id}': 'Published when position is opened',
    'position:updated:{position_id}': 'Published when position is modified',
    'position:closed:{position_id}': 'Published when position is closed',
    'alert:system': 'Published for system alerts'
}
```

**Message Formats**:

**Candle Closed Event**:
```json
{
  "event": "candle_closed",
  "symbol": "SOLUSDT",
  "candle_id": 123456,
  "open_time": "2024-03-15T14:45:00Z",
  "close": 142.50,
  "volume": 1250.5
}
```

**Signal Generated Event**:
```json
{
  "event": "signal_generated",
  "signal_id": 12345,
  "symbol": "SOLUSDT",
  "cqs_final": 78.5,
  "entry_price": 142.50,
  "confidence_level": "MEDIUM"
}
```

**Redis Streams** (for position updates):

```python
# Add to stream
await redis.xadd(
    'positions:updates',
    {
        'position_id': '567',
        'event': 'stop_loss_updated',
        'old_sl': '140.20',
        'new_sl': '142.60',
        'timestamp': '2024-03-15T15:00:00Z'
    }
)

# Read from stream
messages = await redis.xread(
    {'positions:updates': '$'},
    count=10,
    block=1000
)
```

**Redis Cache Keys**:

```python
CACHE_KEYS = {
    'candles:{symbol}:recent': 'Last 100 candles (TTL: 1 hour)',
    'analysis:{candle_id}': 'Candle analysis result (TTL: 24 hours)',
    'ml:model:current': 'Current ML model version (no TTL)',
    'stats:{symbol}:daily': 'Daily statistics (TTL: 1 day)',
    'health:last_candle': 'Last candle timestamp (TTL: 5 minutes)'
}
```

**Cache Strategy**:
- Write-through: Update cache when writing to database
- Read-through: Check cache first, fallback to database
- TTL: Set appropriate expiration for each key type
- Invalidation: Clear cache on model retraining or system restart


### Prometheus Metrics Export

**Purpose**: Export system metrics for monitoring and alerting

**Metrics Endpoint**: `GET /metrics`

**Key Metrics**:

```python
from prometheus_client import Counter, Histogram, Gauge, Info

# Candle processing
candle_processing_latency_ms = Histogram(
    'candle_processing_latency_milliseconds',
    'Time to process candle through all 5 layers',
    buckets=[50, 100, 200, 300, 500, 1000, 2000]
)

candles_processed_total = Counter(
    'candles_processed_total',
    'Total number of candles processed',
    ['symbol', 'candle_class']
)

# Signal generation
signals_generated_total = Counter(
    'signals_generated_total',
    'Total number of trading signals generated',
    ['symbol', 'confidence_level']
)

signals_cqs_distribution = Histogram(
    'signals_cqs_score',
    'Distribution of CQS scores',
    buckets=[60, 65, 70, 75, 80, 85, 90, 95, 100]
)

# ML inference
ml_prediction_latency_ms = Histogram(
    'ml_prediction_latency_milliseconds',
    'ML model inference time',
    buckets=[10, 20, 30, 40, 50, 75, 100]
)

ml_model_auc = Gauge(
    'ml_model_auc_roc',
    'Current ML model AUC-ROC score'
)

# Trading execution
orders_placed_total = Counter(
    'orders_placed_total',
    'Total orders placed',
    ['exchange', 'side', 'status']
)

order_placement_latency_ms = Histogram(
    'order_placement_latency_milliseconds',
    'Time to place order on exchange',
    buckets=[100, 200, 300, 500, 1000, 2000]
)

positions_open = Gauge(
    'positions_open_count',
    'Number of currently open positions',
    ['symbol']
)

# Risk management
signals_rejected_total = Counter(
    'signals_rejected_total',
    'Total signals rejected by risk manager',
    ['reason']
)

daily_pnl_usd = Gauge(
    'daily_pnl_usd',
    'Daily profit/loss in USD'
)

account_balance_usd = Gauge(
    'account_balance_usd',
    'Current account balance in USD',
    ['exchange']
)

# System health
ws_reconnect_count = Counter(
    'websocket_reconnect_total',
    'Total WebSocket reconnections',
    ['source']
)

db_write_latency_ms = Histogram(
    'database_write_latency_milliseconds',
    'Database write operation latency',
    buckets=[10, 25, 50, 100, 200, 500]
)

last_candle_timestamp = Gauge(
    'last_candle_timestamp_seconds',
    'Timestamp of last processed candle'
)

service_up = Gauge(
    'service_up',
    'Service health status (1=up, 0=down)',
    ['service']
)
```

**Grafana Dashboard Panels**:

1. **Signal Quality**: CQS distribution histogram, signals by confidence level
2. **Performance**: Processing latency p50/p95/p99, ML inference latency
3. **Trading**: Orders placed, positions open, daily PnL chart
4. **Risk**: Rejection reasons pie chart, drawdown gauge
5. **System Health**: WebSocket reconnects, DB lag, service status


## Algorithms and Formulas

### Layer 1: Basic Classification Formulas

**Body Strength Score (BSS)**:
```
BSS = (close - open) / (high - low) × 100

Where:
- close: Closing price of candle
- open: Opening price of candle
- high: Highest price during candle
- low: Lowest price during candle
- Result: 0-100 score (higher = stronger bullish body)
```

**Body and Shadow Calculations**:
```
body = close - open
body_abs = |body|
candle_range = high - low
upper_shadow = high - max(open, close)
lower_shadow = min(open, close) - low
body_pct = (body_abs / close) × 100
range_pct = (candle_range / close) × 100
```

**Classification Rules**:
```
IF body_abs / candle_range ≥ 0.70:
    class = STRONG_BULLISH
    base_score = 20
ELSE IF body_abs / candle_range ≥ 0.40:
    class = MODERATE_BULLISH
    base_score = 15
ELSE IF body_abs / candle_range ≥ 0.10:
    class = WEAK_BULLISH
    base_score = 10
ELSE IF body_abs / close < 0.0005:
    class = DOJI
    base_score = 0
    passed = False
ELSE IF body < 0:
    class = BEARISH
    base_score = 0
    passed = False
```

### Layer 2: Morphological Analysis Formulas

**Z-Score Calculation**:
```
z_score = (body_abs - μ_body_50) / σ_body_50

Where:
- body_abs: Absolute body size of current candle
- μ_body_50: Mean of body sizes over last 50 candles
- σ_body_50: Standard deviation of body sizes over last 50 candles

Z-Score Bonuses:
z > 3.0:     +15 points
2.0 ≤ z ≤ 3.0: +10 points
1.5 ≤ z < 2.0: +5 points
0.5 ≤ z < 1.5: 0 points
z < 0.5:     -5 points
```

**Morphology Pattern Detection**:

**MARUBOZU**:
```
Conditions:
  upper_shadow / candle_range < 0.05
  AND lower_shadow / candle_range < 0.05
  AND BSS ≥ 90
Bonus: +20 points
```

**HAMMER**:
```
Conditions:
  lower_shadow ≥ 2 × body_abs
  AND upper_shadow ≤ 0.3 × body_abs
  AND 20 ≤ BSS ≤ 60
  AND previous_3_candles_bearish = True
Bonus: +15 points
```

**BULLISH ENGULFING**:
```
Conditions:
  candle[i-1].body < 0  (previous is bearish)
  AND candle[i].open ≤ candle[i-1].close
  AND candle[i].close ≥ candle[i-1].open
  AND candle[i].body_abs ≥ 1.1 × candle[i-1].body_abs
Bonus: +18 points
```


### Layer 3: Context Filtering Formulas

**Volume Analysis**:
```
avg_vol_20 = (1/20) × Σ(volume[i-19] to volume[i])
avg_vol_50 = (1/50) × Σ(volume[i-49] to volume[i])
vol_ratio = volume[i] / avg_vol_20

Volume Classification:
vol_ratio > 3.0:  EXTREME_VOLUME   (+15 points)
vol_ratio > 2.0:  HIGH_VOLUME      (+10 points)
vol_ratio > 1.5:  ABOVE_AVERAGE    (+7 points)
vol_ratio > 0.8:  NORMAL           (+3 points)
vol_ratio < 0.5:  LOW_VOLUME       (-10 points, flag low_confidence)
```

**Volume-Price Confirmation (VPC)**:
```
VPC = vol_ratio × (BSS / 100)

Interpretation:
VPC > 1.5: High-quality confirmation
VPC > 1.0: Good confirmation
VPC < 0.5: Weak confirmation
```

**Average True Range (ATR)**:
```
TR[i] = max(
    high[i] - low[i],
    |high[i] - close[i-1]|,
    |low[i] - close[i-1]|
)

ATR14 = EWMA(TR, span=14)

Where EWMA is exponential weighted moving average:
EWMA[i] = α × TR[i] + (1 - α) × EWMA[i-1]
α = 2 / (span + 1) = 2 / 15 ≈ 0.133

body_atr_ratio = body_abs / ATR14

Body/ATR Classification:
ratio ≥ 1.0:   Very large movement  (+10 points)
0.5 ≤ ratio < 1.0: Significant movement (+7 points)
0.3 ≤ ratio < 0.5: Moderate movement   (+3 points)
ratio < 0.3:   Noise               (-15 points, reject)
```

**VWAP Calculation**:
```
typical_price[i] = (high[i] + low[i] + close[i]) / 3

VWAP = Σ(typical_price[i] × volume[i]) / Σ(volume[i])
       for all candles from session start (00:00 UTC)

vwap_distance_pct = ((close - VWAP) / VWAP) × 100

VWAP Positioning:
distance > 0.5%:   Strong bullish    (+10 points)
0 < distance ≤ 0.5%: Moderate bullish (+5 points)
-0.5% ≤ distance ≤ 0: Neutral        (0 points)
distance < -0.5%:  Bearish           (-8 points)
```

**Delta Volume Analysis**:
```
For each tick in candle:
  IF tick.price ≥ ask_price:
    buy_volume += tick.volume
  ELSE IF tick.price ≤ bid_price:
    sell_volume += tick.volume

delta = buy_volume - sell_volume
delta_ratio = delta / (buy_volume + sell_volume)

Delta Classification:
delta_ratio > 0.5:   Strong buying    (+15 points)
0.2 ≤ delta_ratio ≤ 0.5: Active buying (+8 points)
-0.2 < delta_ratio < 0.2: Balanced    (0 points)
delta_ratio ≤ -0.2:  Hidden selling   (-15 points, flag SUSPICIOUS)
```

**Order Flow Imbalance (OFI)**:
```
For each orderbook snapshot (every 30 seconds):
  bid_size_top5 = Σ(bid_size for top 5 bid levels)
  ask_size_top5 = Σ(ask_size for top 5 ask levels)
  
  OFI_snapshot = (bid_size_top5 - ask_size_top5) / (bid_size_top5 + ask_size_top5)

OFI_candle = mean(OFI_snapshots in 15-minute window)

OFI Classification:
OFI > 0.3:   High demand      (+10 points)
0.1 ≤ OFI ≤ 0.3: Moderate demand (+5 points)
-0.1 < OFI < 0.1: Neutral       (0 points)
OFI ≤ -0.1:  Supply pressure  (-8 points)
```

**Fractal Dimension (Higuchi Method)**:
```
Given price series P = [p₁, p₂, ..., pₙ] with n = 40 candles:

For each time interval k ∈ {1, 2, 3, 4}:
  For each starting point m ∈ {1, 2, ..., k}:
    Construct subsequence: P_m^k = [p_m, p_{m+k}, p_{m+2k}, ...]
    
    Length of curve:
    L_m(k) = (1/k) × [(Σ|p_{m+ik} - p_{m+(i-1)k}|) × (n-1) / floor((n-m)/k)]
  
  Average length for interval k:
  L(k) = mean(L_m(k) for m = 1 to k)

Fractal Dimension:
FD = -slope of log(L(k)) vs log(1/k)

Approximation:
FD ≈ log(Σ L(k)) / log(1/mean(k))

Market Regime Classification:
1.0 ≤ FD < 1.3: Strong trend    (+10 points)
1.3 ≤ FD < 1.5: Moderate trend  (+5 points)
1.5 ≤ FD < 1.7: Transitional   (0 points)
1.7 ≤ FD ≤ 2.0: Chaos/noise    (-10 points)
```


### Layer 4: Pattern Recognition and Wavelet Analysis

**THREE WHITE SOLDIERS**:
```
For candles [i-2, i-1, i]:
  Conditions:
    ∀j ∈ {i-2, i-1, i}:
      candle[j].body > 0
      AND candle[j].close > candle[j-1].close
      AND candle[j-1].open ≤ candle[j].open ≤ candle[j-1].close
      AND BSS[j] > 60
      AND upper_shadow[j] < 0.2 × body_abs[j]
  
  Bonus: +25 points (highest pattern weight)
```

**MORNING STAR**:
```
Conditions:
  candle[i-2].body < 0 AND BSS[i-2] > 50  (strong bearish)
  AND candle[i-1].body_abs / candle[i-1].range < 0.30  (doji/small body)
  AND candle[i-1].close < candle[i-2].close  (gap down)
  AND candle[i].body > 0  (bullish)
  AND candle[i].close > (candle[i-2].open + candle[i-2].close) / 2
  AND volume[i] > avg_vol_20

Bonus: +22 points
```

**BULLISH FLAG**:
```
Phase 1 - Pole Detection (3-6 candles):
  price_change = (close[i-pole_length] - close[i-pole_length-3]) / close[i-pole_length-3]
  IF price_change > 0.03 AND mean(BSS[pole_candles]) > 65:
    pole_detected = True
    pole_height = close[i-pole_length] - close[i-pole_length-3]

Phase 2 - Flag Detection (5-12 candles):
  flag_range = max(high[flag_candles]) - min(low[flag_candles])
  IF flag_range / close < 0.015:  (consolidation < 1.5%)
    AND mean(volume[flag_candles]) < avg_vol_20:  (declining volume)
    AND linear_regression_slope(close[flag_candles]) ∈ [-0.002, -0.0001]:
      flag_detected = True

Phase 3 - Breakout:
  IF close[i] > max(high[flag_candles]) × 1.002
    AND volume[i] > 1.5 × avg_vol_20:
    breakout_confirmed = True
    target = close[i] + pole_height × 0.618  (Fibonacci projection)

Bonus: +20 points
```

**ASCENDING TRIANGLE**:
```
Window: 10-30 candles

Resistance Line (horizontal):
  resistance_touches = [high[j] for j where |high[j] - resistance_level| < 0.003 × resistance_level]
  IF len(resistance_touches) ≥ 3:
    resistance_confirmed = True

Support Line (ascending):
  support_points = [low[j] for j where candle[j] is local minimum]
  IF len(support_points) ≥ 3:
    slope = linear_regression_slope(support_points)
    IF slope > 0:
      support_confirmed = True

Breakout:
  IF close[i] > resistance_level × 1.002
    AND volume[i] > 2.0 × avg_vol_20:
    breakout_confirmed = True

Bonus: +22 points
```

**Wavelet Decomposition (Daubechies db4)**:
```python
import pywt
import numpy as np

def wavelet_trend_filter(prices: np.ndarray, wavelet='db4', level=3) -> tuple:
    """
    Decompose price series into trend and noise components
    
    Args:
        prices: Array of close prices (last 40 candles)
        wavelet: Wavelet type (db4 = Daubechies 4)
        level: Decomposition level (3 = 3 layers)
    
    Returns:
        (trend_slope, denoised_prices)
    """
    # Decompose signal
    coeffs = pywt.wavedec(prices, wavelet, level=level)
    
    # coeffs structure:
    # [cA3, cD3, cD2, cD1]
    # cA3: Approximation (trend) at level 3
    # cD3: Detail (medium-frequency) at level 3
    # cD2: Detail (higher-frequency) at level 2
    # cD1: Detail (noise) at level 1
    
    # Zero out high-frequency noise (cD1)
    coeffs[1] = np.zeros_like(coeffs[1])
    
    # Reconstruct denoised signal
    denoised = pywt.waverec(coeffs, wavelet)
    
    # Calculate trend slope from last 5 points
    trend_slope = (denoised[-1] - denoised[-5]) / 5
    
    return trend_slope, denoised

# Usage in Layer 4:
prices = np.array([candle.close for candle in last_40_candles])
trend_slope, denoised = wavelet_trend_filter(prices)

IF trend_slope > 0:
    wavelet_confirmed = True
    bonus = +8 points
ELSE:
    wavelet_confirmed = False
    bonus = 0 points
```

**Layer 4 Score Capping**:
```
total_l4_score = sum(pattern_bonuses) + wavelet_bonus
IF total_l4_score > 35:
    total_l4_score = 35  # Cap at maximum
```


### Layer 5: ML Scoring and Final CQS

**CQS Base Calculation**:
```
CQS_base = L1_score + L2_score + L3_score + L4_score - penalties

Where:
  L1_score ∈ [0, 20]  (candle classification)
  L2_score ∈ [0, 20]  (morphology + Z-Score)
  L3_score ∈ [0, 25]  (volume + ATR + VWAP + Delta + OFI + FD)
  L4_score ∈ [0, 35]  (patterns + wavelet)
  penalties = suspicious_penalty + low_confidence_penalty + chaos_penalty

Maximum CQS_base = 100
```

**Penalties**:
```
IF is_suspicious (delta_ratio < -0.2):
    suspicious_penalty = 30

IF low_confidence (vol_ratio < 0.5):
    low_confidence_penalty = 10

IF market_regime == "CHAOS" (FD > 1.7):
    chaos_penalty = 10
```

**ML Probability Prediction**:
```python
# Feature vector (30 dimensions)
features = [
    # Candle metrics (5)
    bss, z_score, upper_shadow_ratio, lower_shadow_ratio, morphology_encoded,
    
    # Context metrics (7)
    vol_ratio, vpc, body_atr_ratio, vwap_distance_pct, delta_ratio, ofi, fractal_dimension,
    
    # Pattern metrics (2)
    pattern_score, wavelet_slope,
    
    # Lagged features (7)
    bss_lag1, bss_lag2, bss_lag3, bss_lag4, bss_lag5, vol_ratio_lag1, vol_ratio_lag2,
    
    # Market indicators (9)
    rsi_14, macd_histogram, atr_pct, bb_position, 
    funding_rate, oi_delta_pct, body_direction_lag1,
    close_to_high_ratio, close_to_low_ratio
]

# XGBoost prediction
ml_probability = xgb_model.predict_proba(features)[0][1]
# Returns probability of 0.3% gain within next 5 candles
```

**Final CQS Calculation**:
```
CQS_final = 0.7 × CQS_base + 0.3 × (ml_probability × 100)

Confidence Level Assignment:
IF CQS_final ≥ 80:
    confidence_level = "HIGH"
ELSE IF CQS_final ≥ 60:
    confidence_level = "MEDIUM"
ELSE:
    confidence_level = "LOW"
    # Do not generate trading signal
```

**Example Calculation**:
```
Given:
  L1_score = 20 (STRONG_BULLISH)
  L2_score = 30 (MARUBOZU + Z-Score 2.4)
  L3_score = 42 (HIGH_VOLUME + good ATR + VWAP + Delta + OFI + TREND)
  L4_score = 33 (THREE_WHITE_SOLDIERS + wavelet confirmed)
  penalties = 0 (no flags)
  
  CQS_base = 20 + 30 + 42 + 33 - 0 = 125
  # Cap at 100
  CQS_base = 100
  
  ml_probability = 0.67
  
  CQS_final = 0.7 × 100 + 0.3 × (0.67 × 100)
            = 70 + 20.1
            = 90.1
  
  confidence_level = "HIGH"
```


### Position Sizing and Risk Calculations

**Fixed Fractional Risk Position Sizing**:
```
Given:
  account_balance: Current account balance in USD
  risk_pct: Percentage of balance to risk per trade (default: 1.0%)
  entry_price: Signal entry price
  stop_loss: Signal stop loss price
  
Calculate:
  stop_distance = entry_price - stop_loss
  risk_amount = account_balance × (risk_pct / 100)
  position_size = risk_amount / stop_distance
  position_size_usd = position_size × entry_price
  
Cap at maximum position size:
  max_position_usd = account_balance × 0.2  # 20% of balance
  IF position_size_usd > max_position_usd:
      position_size = max_position_usd / entry_price

Example:
  account_balance = $10,000
  risk_pct = 1.0%
  entry_price = $142.50
  stop_loss = $140.20
  
  stop_distance = 142.50 - 140.20 = $2.30
  risk_amount = 10,000 × 0.01 = $100
  position_size = 100 / 2.30 = 43.48 units
  position_size_usd = 43.48 × 142.50 = $6,195.90
  
  max_position_usd = 10,000 × 0.2 = $2,000
  # Position exceeds max, cap it
  position_size = 2,000 / 142.50 = 14.04 units
```

**Risk/Reward Ratio**:
```
risk_reward = (take_profit_1 - entry_price) / (entry_price - stop_loss)

Example:
  entry_price = $142.50
  stop_loss = $140.20
  take_profit_1 = $145.80
  
  risk = 142.50 - 140.20 = $2.30
  reward = 145.80 - 142.50 = $3.30
  risk_reward = 3.30 / 2.30 = 1.43
```

**Trailing Stop Calculation**:
```
Given:
  entry_price: Position entry price
  mark_price: Current market price
  trailing_distance_pct: Trail distance (default: 0.5%)
  
Calculate gain:
  gain_pct = ((mark_price - entry_price) / entry_price) × 100
  
IF gain_pct ≥ TRAILING_STOP_ACTIVATION_PCT (1.0%):
    trailing_active = True
    
IF trailing_active:
    trail_price = mark_price × (1 - trailing_distance_pct / 100)
    
    IF trail_price > current_stop_loss:
        new_stop_loss = trail_price
        update_stop_loss(new_stop_loss)

Example:
  entry_price = $142.50
  mark_price = $145.00
  current_stop_loss = $140.20
  
  gain_pct = (145.00 - 142.50) / 142.50 × 100 = 1.75%
  # Gain exceeds 1.0%, activate trailing
  
  trail_price = 145.00 × (1 - 0.5 / 100) = 145.00 × 0.995 = $144.28
  
  # trail_price ($144.28) > current_stop_loss ($140.20)
  new_stop_loss = $144.28
```

**Breakeven Calculation**:
```
Given:
  entry_price: Position entry price
  mark_price: Current market price
  breakeven_offset_pct: Offset above entry (default: 0.1%)
  
Calculate gain:
  gain_pct = ((mark_price - entry_price) / entry_price) × 100
  
IF gain_pct ≥ BREAKEVEN_ACTIVATION_PCT (0.5%) AND NOT be_moved:
    breakeven_price = entry_price × (1 + breakeven_offset_pct / 100)
    update_stop_loss(breakeven_price)
    be_moved = True

Example:
  entry_price = $142.50
  mark_price = $143.25
  
  gain_pct = (143.25 - 142.50) / 142.50 × 100 = 0.53%
  # Gain exceeds 0.5%, move to breakeven
  
  breakeven_price = 142.50 × (1 + 0.1 / 100) = 142.50 × 1.001 = $142.64
```

**PnL Calculation**:
```
For Long Position:
  unrealised_pnl = (mark_price - entry_price) × quantity
  realised_pnl = (exit_price - entry_price) × quantity
  net_pnl = realised_pnl - fees

For Short Position:
  unrealised_pnl = (entry_price - mark_price) × quantity
  realised_pnl = (entry_price - exit_price) × quantity
  net_pnl = realised_pnl - fees

PnL Percentage:
  pnl_pct = (net_pnl / (entry_price × quantity)) × 100

Example (Long):
  entry_price = $142.50
  exit_price = $145.80
  quantity = 10 units
  fees = $0.50
  
  realised_pnl = (145.80 - 142.50) × 10 = $33.00
  net_pnl = 33.00 - 0.50 = $32.50
  pnl_pct = (32.50 / (142.50 × 10)) × 100 = 2.28%
```


## Technology Stack

### Core Technologies

**Programming Language**:
- Python 3.11+ (all services)
- Async-first with asyncio for I/O operations

**Web Frameworks**:
- FastAPI 0.115+ (REST API and WebSocket server)
- Django 6.0 (ORM models and admin interface)
- uvicorn (ASGI server)

**Database**:
- PostgreSQL 17 (relational database)
- TimescaleDB 2.x (time-series extension for PostgreSQL)
- Connection pooling via asyncpg

**Cache and Message Broker**:
- Redis 7.4 (caching, pub/sub, streams)
- aioredis (async Redis client)

**ORM**:
- Django ORM (synchronous, for admin and migrations)
- Tortoise-ORM (asynchronous, for microservices)

**Task Queue**:
- Celery 6 (background tasks, scheduled jobs)
- Redis as broker and result backend

**Data Processing**:
- pandas 2.x (data manipulation)
- numpy 1.26+ (numerical computations)
- pandas_ta (technical indicators)
- PyWavelets (wavelet decomposition)

**Machine Learning**:
- XGBoost 2.x (gradient boosting classifier)
- scikit-learn 1.4+ (preprocessing, metrics)
- SHAP (model interpretability)
- joblib (model serialization)

**API Clients**:
- aiohttp (async HTTP client for exchange APIs)
- websockets (WebSocket client for Binance)
- aiogram 3.x (Telegram bot framework)

**Monitoring and Observability**:
- prometheus-client (metrics export)
- Grafana (visualization)
- Prometheus (metrics storage and alerting)

**Testing**:
- pytest (unit and integration tests)
- pytest-asyncio (async test support)
- hypothesis (property-based testing)
- pytest-cov (coverage reporting)

**Containerization**:
- Docker / Podman (container runtime)
- Docker Compose / Podman Compose (orchestration)

**Security**:
- cryptography (Fernet encryption for API keys)
- python-dotenv (environment variable management)


## Deployment Architecture

### Docker Compose Configuration

**Services**:

```yaml
version: '3.8'

services:
  timescaledb:
    image: timescale/timescaledb:latest-pg17
    environment:
      POSTGRES_DB: candlescout
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - timescaledb_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7.4-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  django-migrate:
    build: ./django_app
    command: python manage.py migrate
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@timescaledb:5432/candlescout
    depends_on:
      timescaledb:
        condition: service_healthy

  data-ingestion:
    build: ./services/data_ingestion
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@timescaledb:5432/candlescout
      REDIS_URL: redis://redis:6379
      BINANCE_WS_URL: ${BINANCE_WS_URL}
      BINANCE_REST_URL: ${BINANCE_REST_URL}
      SYMBOLS: ${SYMBOLS}
    depends_on:
      - timescaledb
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 10s
      retries: 3

  analysis-pipeline:
    build: ./services/analysis_pipeline
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@timescaledb:5432/candlescout
      REDIS_URL: redis://redis:6379
      ML_SERVICE_URL: http://ml-service:8001
    depends_on:
      - timescaledb
      - redis
      - ml-service
    restart: unless-stopped

  ml-service:
    build: ./services/ml_service
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@timescaledb:5432/candlescout
      MODEL_PATH: /models
    volumes:
      - ml_models:/models
    ports:
      - "8001:8001"
    restart: unless-stopped

  signal-dispatcher:
    build: ./services/signal_dispatcher
    environment:
      REDIS_URL: redis://redis:6379
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      TELEGRAM_CHAT_ID: ${TELEGRAM_CHAT_ID}
      MIN_CQS_THRESHOLD: ${MIN_CQS_THRESHOLD}
    depends_on:
      - redis
    restart: unless-stopped

  trade-executor:
    build: ./services/trade_executor
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@timescaledb:5432/candlescout
      REDIS_URL: redis://redis:6379
      BYBIT_API_KEY: ${BYBIT_API_KEY}
      BYBIT_API_SECRET: ${BYBIT_API_SECRET}
      OKX_API_KEY: ${OKX_API_KEY}
      OKX_API_SECRET: ${OKX_API_SECRET}
      OKX_PASSPHRASE: ${OKX_PASSPHRASE}
      PAPER_TRADING: ${PAPER_TRADING}
      MIN_CQS_TO_TRADE: ${MIN_CQS_TO_TRADE}
      MIN_RR_RATIO: ${MIN_RR_RATIO}
      MAX_OPEN_POSITIONS: ${MAX_OPEN_POSITIONS}
      MAX_DAILY_LOSS_PCT: ${MAX_DAILY_LOSS_PCT}
      RISK_PER_TRADE_PCT: ${RISK_PER_TRADE_PCT}
    depends_on:
      - timescaledb
      - redis
    restart: unless-stopped

  position-manager:
    build: ./services/position_manager
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@timescaledb:5432/candlescout
      BYBIT_API_KEY: ${BYBIT_API_KEY}
      BYBIT_API_SECRET: ${BYBIT_API_SECRET}
      OKX_API_KEY: ${OKX_API_KEY}
      OKX_API_SECRET: ${OKX_API_SECRET}
      OKX_PASSPHRASE: ${OKX_PASSPHRASE}
      TRAILING_STOP_ACTIVATION_PCT: ${TRAILING_STOP_ACTIVATION_PCT}
      TRAILING_STOP_DISTANCE_PCT: ${TRAILING_STOP_DISTANCE_PCT}
      BREAKEVEN_ACTIVATION_PCT: ${BREAKEVEN_ACTIVATION_PCT}
    depends_on:
      - timescaledb
    restart: unless-stopped

  fastapi:
    build: ./services/api
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@timescaledb:5432/candlescout
      REDIS_URL: redis://redis:6379
    ports:
      - "8000:8000"
    depends_on:
      - timescaledb
      - redis
    restart: unless-stopped

  celery-worker:
    build: ./services/celery_app
    command: celery -A tasks worker --loglevel=info
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@timescaledb:5432/candlescout
      REDIS_URL: redis://redis:6379
    depends_on:
      - timescaledb
      - redis
    restart: unless-stopped

  celery-beat:
    build: ./services/celery_app
    command: celery -A tasks beat --loglevel=info
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@timescaledb:5432/candlescout
      REDIS_URL: redis://redis:6379
    depends_on:
      - timescaledb
      - redis
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  grafana:
    image: grafana/grafana:latest
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
    ports:
      - "3000:3000"
    depends_on:
      - prometheus

volumes:
  timescaledb_data:
  redis_data:
  ml_models:
  prometheus_data:
  grafana_data:
```

### Environment Configuration (.env)

```bash
# Database
DB_USER=candlescout
DB_PASSWORD=<secure_password>

# Binance
BINANCE_WS_URL=wss://stream.binance.com:9443/ws
BINANCE_REST_URL=https://api.binance.com/api/v3
SYMBOLS=SOLUSDT

# Bybit
BYBIT_API_KEY=<your_api_key>
BYBIT_API_SECRET=<your_api_secret>
BYBIT_TESTNET=false

# OKX
OKX_API_KEY=<your_api_key>
OKX_API_SECRET=<your_api_secret>
OKX_PASSPHRASE=<your_passphrase>
OKX_TESTNET=false

# Telegram
TELEGRAM_BOT_TOKEN=<your_bot_token>
TELEGRAM_CHAT_ID=<your_chat_id>

# Trading Configuration
PAPER_TRADING=false
MIN_CQS_TO_TRADE=65
MIN_CQS_THRESHOLD=60
MIN_RR_RATIO=1.5
MAX_OPEN_POSITIONS=3
MAX_DAILY_LOSS_PCT=2.0
MAX_DRAWDOWN_PCT=5.0
RISK_PER_TRADE_PCT=1.0
COOLDOWN_AFTER_LOSS_MIN=60

# Position Management
TRAILING_STOP_ACTIVATION_PCT=1.0
TRAILING_STOP_DISTANCE_PCT=0.5
BREAKEVEN_ACTIVATION_PCT=0.5
BREAKEVEN_OFFSET_PCT=0.1
TP1_CLOSE_PCT=50

# Grafana
GRAFANA_PASSWORD=<secure_password>
```

### Health Checks

All services implement health check endpoints:

```python
# Example health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "data-ingestion",
        "timestamp": datetime.utcnow().isoformat()
    }
```

Health check configuration:
- Interval: 30 seconds
- Timeout: 10 seconds
- Retries: 3
- Start period: 40 seconds


## Security Design

### API Key Encryption

**Encryption Method**: Fernet (symmetric encryption using AES-128-CBC)

```python
from cryptography.fernet import Fernet
import os

class APIKeyManager:
    """Secure storage and retrieval of exchange API keys"""
    
    def __init__(self):
        # Load or generate encryption key
        key_file = os.getenv('ENCRYPTION_KEY_FILE', '.encryption_key')
        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                self.key = f.read()
        else:
            self.key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(self.key)
        
        self.cipher = Fernet(self.key)
    
    def encrypt_secret(self, secret: str) -> bytes:
        """Encrypt API secret"""
        return self.cipher.encrypt(secret.encode())
    
    def decrypt_secret(self, encrypted: bytes) -> str:
        """Decrypt API secret"""
        return self.cipher.decrypt(encrypted).decode()
    
    async def store_api_key(self, exchange: str, api_key: str, 
                           api_secret: str, passphrase: str = None):
        """Store encrypted API credentials in database"""
        encrypted_secret = self.encrypt_secret(api_secret)
        encrypted_passphrase = self.encrypt_secret(passphrase) if passphrase else None
        
        await ExchangeAPIKey.update_or_create(
            exchange=exchange,
            defaults={
                'api_key': api_key,
                'api_secret_encrypted': encrypted_secret,
                'passphrase_encrypted': encrypted_passphrase
            }
        )
    
    async def get_api_credentials(self, exchange: str) -> dict:
        """Retrieve and decrypt API credentials"""
        record = await ExchangeAPIKey.get(exchange=exchange)
        return {
            'api_key': record.api_key,
            'api_secret': self.decrypt_secret(record.api_secret_encrypted),
            'passphrase': self.decrypt_secret(record.passphrase_encrypted) 
                         if record.passphrase_encrypted else None
        }
```

### Exchange API Request Signing

**Bybit HMAC-SHA256**:

```python
import hmac
import hashlib
import time

def sign_bybit_request(api_secret: str, params: dict) -> str:
    """Generate HMAC-SHA256 signature for Bybit API"""
    timestamp = str(int(time.time() * 1000))
    recv_window = "5000"
    
    # Sort parameters
    param_str = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
    
    # Create signature string
    sign_str = f"{timestamp}{api_key}{recv_window}{param_str}"
    
    # Generate signature
    signature = hmac.new(
        api_secret.encode('utf-8'),
        sign_str.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return signature
```

**OKX HMAC-SHA256**:

```python
import hmac
import hashlib
import base64
from datetime import datetime

def sign_okx_request(api_secret: str, timestamp: str, method: str, 
                     request_path: str, body: str = '') -> str:
    """Generate HMAC-SHA256 signature for OKX API"""
    # Create prehash string
    prehash = timestamp + method + request_path + body
    
    # Generate signature
    signature = base64.b64encode(
        hmac.new(
            api_secret.encode('utf-8'),
            prehash.encode('utf-8'),
            hashlib.sha256
        ).digest()
    ).decode()
    
    return signature
```

### Security Best Practices

**API Key Permissions**:
- Bybit: Enable "Trade" only, disable "Withdraw" and "Transfer"
- OKX: Enable "Trade" only, disable "Withdraw" and "Transfer"
- IP Whitelist: Bind API keys to server IP address

**Secrets Management**:
- Never commit API keys or secrets to version control
- Store all secrets in `.env` file (add to `.gitignore`)
- Use environment variables for all sensitive configuration
- Rotate API keys every 90 days

**Database Security**:
- Use strong passwords (minimum 16 characters)
- Restrict database access to localhost or private network
- Enable SSL/TLS for database connections in production
- Regular automated backups with encryption

**Network Security**:
- Run services in private Docker network
- Expose only necessary ports (8000 for API, 3000 for Grafana)
- Use reverse proxy (nginx) with SSL/TLS in production
- Implement rate limiting on public API endpoints

**Monitoring and Alerting**:
- Log all API key usage and authentication attempts
- Alert on failed authentication attempts (> 5 in 5 minutes)
- Monitor for unusual trading activity
- Alert on large position sizes or losses


## Performance and Scalability

### Performance Requirements

**Latency Targets**:

| Operation | Target (p95) | Maximum |
|-----------|--------------|---------|
| Candle receipt from Binance | < 2s | 5s |
| Database write | < 100ms | 200ms |
| Layer 1-4 analysis | < 400ms | 600ms |
| ML inference (Layer 5) | < 50ms | 100ms |
| Total pipeline (candle → signal) | < 500ms | 1000ms |
| REST API response | < 200ms | 500ms |
| WebSocket message delivery | < 100ms | 200ms |
| Order placement | < 500ms | 1000ms |
| Position monitoring cycle | 15s | 30s |

**Throughput Targets**:

| Metric | Target |
|--------|--------|
| Concurrent trading pairs | 20 |
| Candles processed per minute | 20 (1 per pair) |
| Signals generated per hour | 10-50 |
| Concurrent WebSocket connections | 100+ |
| REST API requests per second | 100+ |
| Database writes per second | 50+ |

### Optimization Strategies

**Database Optimization**:

```sql
-- TimescaleDB hypertable for automatic partitioning
SELECT create_hypertable('candles_15m', 'open_time', 
                         chunk_time_interval => INTERVAL '7 days');

-- Compression for old data (> 30 days)
ALTER TABLE candles_15m SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol'
);

SELECT add_compression_policy('candles_15m', INTERVAL '30 days');

-- Retention policy (keep 12 months)
SELECT add_retention_policy('candles_15m', INTERVAL '12 months');

-- Continuous aggregates for statistics
CREATE MATERIALIZED VIEW candle_stats_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', open_time) AS bucket,
    symbol,
    COUNT(*) as candle_count,
    AVG(volume) as avg_volume,
    AVG(close) as avg_price
FROM candles_15m
GROUP BY bucket, symbol;

-- Refresh policy
SELECT add_continuous_aggregate_policy('candle_stats_hourly',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');
```

**Connection Pooling**:

```python
from asyncpg import create_pool

# Database connection pool
db_pool = await create_pool(
    dsn=DATABASE_URL,
    min_size=5,
    max_size=20,
    max_queries=50000,
    max_inactive_connection_lifetime=300
)

# Redis connection pool
redis_pool = aioredis.ConnectionPool.from_url(
    REDIS_URL,
    max_connections=50,
    decode_responses=True
)
```

**Caching Strategy**:

```python
# Cache recent candles (last 100)
async def get_recent_candles(symbol: str, count: int = 100) -> List[Candle]:
    cache_key = f"candles:{symbol}:recent"
    
    # Try cache first
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Fallback to database
    candles = await Candle15m.filter(symbol=symbol).order_by('-open_time').limit(count)
    
    # Update cache
    await redis.setex(cache_key, 3600, json.dumps([c.dict() for c in candles]))
    
    return candles

# Cache ML model in memory
class MLService:
    def __init__(self):
        self._model = None
        self._model_version = None
    
    async def get_model(self) -> XGBoostModel:
        current_version = await redis.get('ml:model:current')
        
        if self._model is None or self._model_version != current_version:
            model_path = await redis.get(f'ml:model:{current_version}:path')
            self._model = joblib.load(model_path)
            self._model_version = current_version
        
        return self._model
```

**Async I/O Throughout**:

```python
# All I/O operations use asyncio
async def process_candle_pipeline(candle_id: int):
    # Parallel database queries
    candle, history, tick_agg = await asyncio.gather(
        Candle15m.get(id=candle_id),
        get_recent_candles(symbol, 100),
        CandleTickAgg.get(candle_id=candle_id)
    )
    
    # Sequential analysis layers (dependencies)
    l1 = await run_layer1(candle)
    l2 = await run_layer2(candle, l1, history)
    l3 = await run_layer3(candle, l1, l2, history, tick_agg)
    l4 = await run_layer4(history, l3)
    
    # Parallel ML inference and database write
    signal, _ = await asyncio.gather(
        run_layer5(candle, l1, l2, l3, l4),
        store_analysis(candle_id, l1, l2, l3, l4)
    )
    
    return signal
```

### Scalability Design

**Horizontal Scaling**:

```yaml
# Scale analysis pipeline workers
docker-compose up --scale analysis-pipeline=3

# Scale API servers
docker-compose up --scale fastapi=2

# Load balancer (nginx)
upstream fastapi_backend {
    server fastapi_1:8000;
    server fastapi_2:8000;
}
```

**Multi-Symbol Support**:

```python
# Each symbol processed independently
SYMBOLS = ["SOLUSDT", "BTCUSDT", "ETHUSDT", ...]

for symbol in SYMBOLS:
    asyncio.create_task(data_ingestion_worker(symbol))
    asyncio.create_task(analysis_pipeline_worker(symbol))
```

**Resource Limits**:

```yaml
services:
  analysis-pipeline:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

**Monitoring Resource Usage**:

```python
import psutil

# CPU usage
cpu_percent = psutil.cpu_percent(interval=1)
cpu_usage_gauge.set(cpu_percent)

# Memory usage
memory = psutil.virtual_memory()
memory_usage_gauge.set(memory.percent)

# Disk usage
disk = psutil.disk_usage('/')
disk_usage_gauge.set(disk.percent)
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: BSS Calculation Correctness

*For any* candle with non-zero range, calculating BSS as (close - open) / (high - low) × 100 should produce a value between -100 and 100, and recalculating from the same candle data should produce the same result.

**Validates: Requirements 2.1**

### Property 2: Candle Classification Consistency

*For any* candle, if BSS >= 70 then classification is STRONG_BULLISH, if 40 <= BSS < 70 then MODERATE_BULLISH, if 10 <= BSS < 40 then WEAK_BULLISH, and classification should be deterministic for the same candle.

**Validates: Requirements 2.2, 2.3, 2.4**

### Property 3: Bearish and Doji Exclusion

*For any* candle where close <= open OR (|body| / close < 0.0005), the candle should be excluded from further pipeline processing and no trading signal should be generated.

**Validates: Requirements 2.5, 2.6**

### Property 4: Z-Score Calculation Correctness

*For any* candle with at least 50 historical candles, Z-Score calculated as (current_body - mean_body_50) / std_body_50 should be consistent with statistical definition, and Z-Score bonuses should be applied according to thresholds (>3.0: +15, 2.0-3.0: +10, 1.5-2.0: +5).

**Validates: Requirements 3.1, 3.4, 3.5**

### Property 5: Pattern Detection Determinism

*For any* candle meeting MARUBOZU conditions (upper_shadow/range < 0.05 AND lower_shadow/range < 0.05 AND BSS >= 90), the morphology should be classified as MARUBOZU with +20 CQS bonus, and the same candle data should always produce the same classification.

**Validates: Requirements 3.2**

### Property 6: Volume Ratio Calculation and Classification

*For any* candle with at least 20 historical candles, volume_ratio calculated as current_volume / avg_volume_20 should correctly classify volume (>3.0: EXTREME, >2.0: HIGH, <0.5: LOW) and apply corresponding CQS adjustments.

**Validates: Requirements 4.1, 4.2, 4.3, 4.4**

### Property 7: ATR Calculation Consistency

*For any* sequence of at least 14 candles, ATR14 calculated using EWMA of true range should be non-negative, and candles with body/ATR14 < 0.3 should receive -15 CQS penalty and rejection flag.

**Validates: Requirements 4.5, 4.6**

### Property 8: VPC Formula Correctness

*For any* candle, VPC calculated as volume_ratio × (BSS / 100) should equal the product of these two values, verifying the volume-price confirmation metric.

**Validates: Requirements 4.7**

### Property 9: VWAP Calculation Accumulation

*For any* sequence of candles from session start, VWAP calculated as cumsum(typical_price × volume) / cumsum(volume) should be monotonically bounded by the min and max prices in the sequence, and VWAP positioning should correctly adjust CQS (+10 if close > VWAP * 1.005, -8 if close < VWAP * 0.995).

**Validates: Requirements 5.1, 5.2, 5.3**

### Property 10: Delta Volume and Ratio Calculation

*For any* candle with tick data, delta calculated as buy_volume - sell_volume and delta_ratio as delta / (buy_volume + sell_volume) should satisfy -1 <= delta_ratio <= 1, and bullish candles with delta_ratio < -0.2 should have SUSPICIOUS flag set and signal generation blocked.

**Validates: Requirements 5.4, 5.5, 5.6**

### Property 11: OFI Calculation Bounds

*For any* orderbook snapshot, OFI calculated as (bid_size_top5 - ask_size_top5) / (bid_size_top5 + ask_size_top5) should satisfy -1 <= OFI <= 1, and OFI > 0.3 should add +10 to CQS.

**Validates: Requirements 5.7, 5.8**

### Property 12: Fractal Dimension Market Regime Classification

*For any* sequence of 40 candles, Fractal Dimension calculated using Higuchi method should be between 1.0 and 2.0, and market regime should be correctly classified (1.0-1.3: TREND +10, 1.3-1.5: NEUTRAL +5, 1.7-2.0: CHAOS -10).

**Validates: Requirements 6.1, 6.2, 6.3, 6.4**

### Property 13: Layer 4 Score Capping

*For any* candle analysis, the total Layer 4 score (sum of all pattern bonuses + wavelet bonus) should never exceed 35 points, enforcing the maximum cap.

**Validates: Requirements 7.6**

### Property 14: Wavelet Decomposition Noise Removal

*For any* price series of 40 candles, applying DWT with db4 wavelet at level 3, zeroing level 1 coefficients, and reconstructing should produce a denoised series with reduced high-frequency components, and positive trend slope should set wavelet_confirmed flag and add +8 to CQS.

**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**

### Property 15: CQS Base Calculation and Capping

*For any* candle completing all 4 layers, CQS_base calculated as sum(L1_score + L2_score + L3_score + L4_score) - penalties should never exceed 100, enforcing the maximum cap.

**Validates: Requirements 9.1**

### Property 16: CQS Final Weighted Combination

*For any* candle with CQS_base and ml_probability, CQS_final calculated as 0.7 × CQS_base + 0.3 × (ml_probability × 100) should be between 0 and 100, and confidence level should be correctly assigned (>=80: HIGH, 60-79: MEDIUM, <60: no signal).

**Validates: Requirements 9.5, 9.6, 9.7, 9.8**

### Property 17: ML Inference Latency

*For any* feature vector of 30 dimensions, ML inference using XGBoost should complete within 50 milliseconds at p95, ensuring real-time performance.

**Validates: Requirements 9.4**

### Property 18: Signal Generation Conditions

*For any* candle analysis, a trading signal should be generated if and only if CQS_final >= 60 AND is_suspicious flag is false, ensuring only high-quality signals are produced.

**Validates: Requirements 10.1**

### Property 19: Stop Loss Calculation

*For any* trading signal, stop_loss calculated as entry_price - 1.5 × ATR14 should be less than entry_price, ensuring stop loss is below entry for long positions.

**Validates: Requirements 10.3**

### Property 20: Risk/Reward Ratio Calculation

*For any* trading signal, risk_reward calculated as (take_profit_1 - entry_price) / (entry_price - stop_loss) should be positive, and signals with R/R < MIN_RR_RATIO should be rejected by Risk Manager.

**Validates: Requirements 10.5, 15.2**

### Property 21: Pipeline Latency

*For any* candle, the complete pipeline from candle close to signal generation should complete within 500 milliseconds, ensuring timely signal delivery.

**Validates: Requirements 10.7**

### Property 22: Signal Storage Latency

*For any* generated trading signal, storage to TimescaleDB should complete within 100 milliseconds, ensuring data persistence doesn't block the pipeline.

**Validates: Requirements 11.1**

### Property 23: Signal Outcome Tracking

*For any* trading signal, after 5 candles (75 minutes), an outcome record should be created with metrics (pnl_pct, hit_tp1, hit_tp2, hit_sl, MFE, MAE) calculated from actual price movement.

**Validates: Requirements 11.3, 11.4**

### Property 24: REST API Response Latency

*For any* REST API request to /api/v1/* endpoints, response time should be under 200 milliseconds at p95, ensuring responsive API access.

**Validates: Requirements 12.7**

### Property 25: WebSocket Message Delivery Latency

*For any* generated signal, publishing to Redis pub/sub should complete within 50ms, and delivery to all connected WebSocket clients should complete within 100ms of Redis publication.

**Validates: Requirements 13.3, 13.4**

### Property 26: Risk Manager Validation Gates

*For any* trading signal, Risk Manager should reject if ANY of these conditions fail: CQS >= MIN_CQS_TO_TRADE, R/R >= MIN_RR_RATIO, is_suspicious == false, open_positions < MAX_OPEN_POSITIONS, daily_loss < MAX_DAILY_LOSS_PCT, drawdown < MAX_DRAWDOWN_PCT, no duplicate position for symbol.

**Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.8**

### Property 27: Position Sizing Calculation

*For any* approved signal, position_size calculated as (balance × risk_pct) / stop_distance should result in risk_usd approximately equal to balance × risk_pct, and position_size_usd should not exceed balance × 0.2 (20% cap).

**Validates: Requirements 15.9**

### Property 28: Trailing Stop Activation and Update

*For any* open position, when gain_pct >= TRAILING_STOP_ACTIVATION_PCT (1.0%), trailing stop should activate, and trail_price calculated as mark_price × (1 - TRAILING_STOP_DISTANCE_PCT / 100) should only update stop_loss when trail_price > current_stop_loss.

**Validates: Requirements 18.2, 18.3, 18.4, 18.5**

### Property 29: Breakeven Stop Move

*For any* open position, when gain_pct >= BREAKEVEN_ACTIVATION_PCT (0.5%) and breakeven not yet moved, stop_loss should be updated to entry_price × (1 + BREAKEVEN_OFFSET_PCT / 100), protecting capital.

**Validates: Requirements 19.1, 19.2**

### Property 30: PnL Calculation Correctness

*For any* closed position, realised_pnl calculated as (exit_price - entry_price) × quantity for long positions should equal the actual profit/loss, and net_pnl should equal realised_pnl - fees.

**Validates: Requirements 20.1, 20.2**

### Property 31: ML Model Performance Thresholds

*For any* trained ML model deployed to production, it should meet minimum thresholds: AUC-ROC >= 0.58, Precision >= 0.55, Recall >= 0.45, F1-Score >= 0.50, ensuring model quality.

**Validates: Requirements 22.1, 22.2, 22.3, 22.4**

### Property 32: Data Retention Period

*For any* candle, signal, or position record, it should be retained in TimescaleDB for at least 12 months, ensuring historical data availability for analysis and model retraining.

**Validates: Requirements 11.5, 24.1, 24.2**

### Property 33: WebSocket Connection Fallback

*For any* WebSocket connection failure lasting more than 60 seconds, the system should fall back to REST API polling every 30 seconds and automatically backfill up to 1000 missing candles upon reconnection.

**Validates: Requirements 1.3, 1.5**

### Property 34: System Uptime

*For any* monthly measurement period, system uptime should be >= 99.5%, ensuring high availability for trading operations.

**Validates: Requirements 23.7**


## Error Handling

### Error Categories

**1. Data Ingestion Errors**:

```python
class DataIngestionError(Exception):
    """Base exception for data ingestion errors"""
    pass

class WebSocketConnectionError(DataIngestionError):
    """WebSocket connection failed"""
    def handle(self):
        logger.error("WebSocket connection failed, falling back to REST API")
        await self.activate_rest_fallback()
        await self.send_alert("WebSocket disconnected", severity="warning")

class BackfillError(DataIngestionError):
    """Backfill operation failed"""
    def handle(self):
        logger.error(f"Backfill failed: {self.message}")
        await self.retry_with_exponential_backoff(max_retries=3)

class DatabaseWriteError(DataIngestionError):
    """Failed to write candle to database"""
    def handle(self):
        logger.critical(f"Database write failed: {self.message}")
        await self.buffer_to_redis()  # Temporary buffer
        await self.send_alert("Database write failure", severity="critical")
```

**2. Analysis Pipeline Errors**:

```python
class AnalysisError(Exception):
    """Base exception for analysis errors"""
    pass

class InvalidCandleError(AnalysisError):
    """Candle data is invalid (zero range, missing fields)"""
    def handle(self):
        logger.warning(f"Invalid candle: {self.candle_id}")
        await self.mark_candle_invalid()
        # Do not propagate - skip this candle

class CalculationError(AnalysisError):
    """Calculation failed (division by zero, NaN result)"""
    def handle(self):
        logger.error(f"Calculation error in {self.layer}: {self.message}")
        await self.use_default_value()
        await self.flag_for_review()

class MLInferenceError(AnalysisError):
    """ML model inference failed"""
    def handle(self):
        logger.error(f"ML inference failed: {self.message}")
        # Fall back to CQS_base only
        cqs_final = cqs_base
        await self.send_alert("ML inference failure", severity="warning")
```

**3. Trading Execution Errors**:

```python
class TradingError(Exception):
    """Base exception for trading errors"""
    pass

class OrderPlacementError(TradingError):
    """Failed to place order on exchange"""
    def handle(self):
        logger.error(f"Order placement failed: {self.exchange} - {self.message}")
        await self.retry_order(max_retries=3, delay=1.0)
        if not self.success:
            await self.log_failed_order()
            await self.send_telegram_alert(f"❌ Order failed: {self.message}")

class InsufficientBalanceError(TradingError):
    """Insufficient balance for trade"""
    def handle(self):
        logger.warning(f"Insufficient balance: {self.required} > {self.available}")
        await self.reject_signal("Insufficient balance")
        # Do not retry

class ExchangeAPIError(TradingError):
    """Exchange API returned error"""
    def handle(self):
        if self.is_retryable():
            await self.retry_with_backoff()
        else:
            logger.error(f"Non-retryable API error: {self.code} - {self.message}")
            await self.log_error()
```

**4. Position Management Errors**:

```python
class PositionError(Exception):
    """Base exception for position management errors"""
    pass

class StopLossUpdateError(PositionError):
    """Failed to update stop loss"""
    def handle(self):
        logger.error(f"Stop loss update failed: {self.position_id}")
        await self.retry_update(max_retries=3)
        if not self.success:
            await self.send_telegram_alert(f"⚠️ Failed to update SL for position {self.position_id}")

class PositionNotFoundError(PositionError):
    """Position not found on exchange"""
    def handle(self):
        logger.warning(f"Position not found: {self.position_id}")
        await self.mark_position_closed("Position not found on exchange")
```

### Error Handling Strategy

**Retry Logic**:

```python
async def retry_with_exponential_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0
) -> Any:
    """Retry function with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            
            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.warning(f"Attempt {attempt + 1} failed, retrying in {delay}s: {e}")
            await asyncio.sleep(delay)
```

**Circuit Breaker**:

```python
class CircuitBreaker:
    """Prevent cascading failures"""
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func: Callable) -> Any:
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenError("Circuit breaker is OPEN")
        
        try:
            result = await func()
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.error(f"Circuit breaker opened after {self.failure_count} failures")
            
            raise
```

**Graceful Degradation**:

```python
# If ML service is down, use CQS_base only
try:
    ml_probability = await ml_service.predict(features)
    cqs_final = 0.7 * cqs_base + 0.3 * (ml_probability * 100)
except MLInferenceError:
    logger.warning("ML service unavailable, using CQS_base only")
    cqs_final = cqs_base

# If Redis is down, skip caching but continue processing
try:
    await redis.setex(cache_key, ttl, value)
except RedisError:
    logger.warning("Redis unavailable, skipping cache")
    # Continue without caching
```

**Dead Letter Queue**:

```python
# Failed signals go to DLQ for manual review
async def handle_failed_signal(signal: TradingSignal, error: Exception):
    await redis.lpush("dlq:signals", json.dumps({
        "signal": signal.dict(),
        "error": str(error),
        "timestamp": datetime.utcnow().isoformat()
    }))
    logger.error(f"Signal {signal.signal_id} moved to DLQ: {error}")
```


## Testing Strategy

### Dual Testing Approach

The system employs both unit testing and property-based testing to ensure comprehensive coverage:

- **Unit tests**: Verify specific examples, edge cases, and error conditions
- **Property tests**: Verify universal properties across all inputs through randomization

Together, these approaches provide comprehensive coverage where unit tests catch concrete bugs and property tests verify general correctness.

### Unit Testing

**Framework**: pytest with pytest-asyncio for async support

**Test Organization**:

```
tests/
├── unit/
│   ├── test_layer1_classifier.py
│   ├── test_layer2_morphology.py
│   ├── test_layer3_context.py
│   ├── test_layer4_patterns.py
│   ├── test_layer5_ml.py
│   ├── test_risk_manager.py
│   ├── test_position_manager.py
│   └── test_connectors.py
├── integration/
│   ├── test_pipeline_e2e.py
│   ├── test_api_endpoints.py
│   └── test_websocket_streams.py
└── property/
    ├── test_properties_layer1.py
    ├── test_properties_layer2.py
    ├── test_properties_layer3.py
    ├── test_properties_calculations.py
    └── test_properties_risk.py
```

**Example Unit Tests**:

```python
import pytest
from decimal import Decimal
from analysis.layer1 import Layer1Classifier

class TestLayer1Classifier:
    """Unit tests for Layer 1 candle classification"""
    
    def test_strong_bullish_classification(self):
        """Test STRONG_BULLISH classification for BSS >= 70"""
        candle = Candle(
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("99.50"),
            close=Decimal("104.50"),
            volume=Decimal("1000")
        )
        
        classifier = Layer1Classifier()
        result = classifier.classify(candle)
        
        assert result.candle_class == "STRONG_BULLISH"
        assert result.bss >= 70
        assert result.passed is True
    
    def test_doji_exclusion(self):
        """Test DOJI classification and exclusion"""
        candle = Candle(
            open=Decimal("100.00"),
            high=Decimal("100.10"),
            low=Decimal("99.90"),
            close=Decimal("100.01"),  # Very small body
            volume=Decimal("1000")
        )
        
        classifier = Layer1Classifier()
        result = classifier.classify(candle)
        
        assert result.candle_class == "DOJI"
        assert result.passed is False
    
    def test_zero_range_invalid(self):
        """Test zero range candle marked as INVALID"""
        candle = Candle(
            open=Decimal("100.00"),
            high=Decimal("100.00"),
            low=Decimal("100.00"),
            close=Decimal("100.00"),
            volume=Decimal("1000")
        )
        
        classifier = Layer1Classifier()
        result = classifier.classify(candle)
        
        assert result.candle_class == "INVALID"
        assert result.passed is False
```

**Integration Tests**:

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
class TestAPIEndpoints:
    """Integration tests for REST API"""
    
    async def test_get_signals_endpoint(self, client: AsyncClient):
        """Test /api/v1/signals endpoint"""
        response = await client.get(
            "/api/v1/signals",
            params={"symbol": "SOLUSDT", "min_cqs": 60, "limit": 10}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "signals" in data
        assert len(data["signals"]) <= 10
        assert all(s["cqs_final"] >= 60 for s in data["signals"])
    
    async def test_health_endpoint(self, client: AsyncClient):
        """Test /api/v1/health endpoint"""
        response = await client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "last_candle_time" in data
        assert "ws_connected" in data
```

### Property-Based Testing

**Framework**: hypothesis for property-based testing

**Configuration**: Minimum 100 iterations per property test

**Property Test Examples**:

```python
from hypothesis import given, strategies as st
from hypothesis import settings
import pytest

# Feature: candlescout-pro, Property 1: BSS Calculation Correctness
@given(
    open_price=st.decimals(min_value=1, max_value=1000, places=2),
    high_price=st.decimals(min_value=1, max_value=1000, places=2),
    low_price=st.decimals(min_value=1, max_value=1000, places=2),
    close_price=st.decimals(min_value=1, max_value=1000, places=2)
)
@settings(max_examples=100)
def test_property_bss_calculation_correctness(open_price, high_price, low_price, close_price):
    """
    Feature: candlescout-pro, Property 1: BSS Calculation Correctness
    
    For any candle with non-zero range, calculating BSS as (close - open) / (high - low) × 100
    should produce a value between -100 and 100, and recalculating from the same candle data
    should produce the same result.
    """
    # Ensure valid candle (high >= max(open, close), low <= min(open, close))
    actual_high = max(high_price, open_price, close_price)
    actual_low = min(low_price, open_price, close_price)
    
    # Skip zero-range candles
    if actual_high == actual_low:
        return
    
    candle = Candle(
        open=open_price,
        high=actual_high,
        low=actual_low,
        close=close_price,
        volume=Decimal("1000")
    )
    
    classifier = Layer1Classifier()
    
    # Calculate BSS twice
    bss1 = classifier.calculate_bss(candle)
    bss2 = classifier.calculate_bss(candle)
    
    # Property 1: BSS should be between -100 and 100
    assert -100 <= bss1 <= 100
    
    # Property 2: BSS calculation should be deterministic
    assert bss1 == bss2

# Feature: candlescout-pro, Property 6: Volume Ratio Calculation and Classification
@given(
    current_volume=st.decimals(min_value=1, max_value=10000, places=2),
    avg_volume=st.decimals(min_value=1, max_value=10000, places=2)
)
@settings(max_examples=100)
def test_property_volume_ratio_classification(current_volume, avg_volume):
    """
    Feature: candlescout-pro, Property 6: Volume Ratio Calculation and Classification
    
    For any candle with at least 20 historical candles, volume_ratio calculated as
    current_volume / avg_volume_20 should correctly classify volume and apply
    corresponding CQS adjustments.
    """
    vol_ratio = float(current_volume / avg_volume)
    
    layer3 = Layer3Context()
    vol_class, cqs_bonus = layer3.classify_volume(vol_ratio)
    
    # Verify classification thresholds
    if vol_ratio > 3.0:
        assert vol_class == "EXTREME_VOLUME"
        assert cqs_bonus == 15
    elif vol_ratio > 2.0:
        assert vol_class == "HIGH_VOLUME"
        assert cqs_bonus == 10
    elif vol_ratio > 1.5:
        assert vol_class == "ABOVE_AVERAGE"
        assert cqs_bonus == 7
    elif vol_ratio > 0.8:
        assert vol_class == "NORMAL"
        assert cqs_bonus == 3
    elif vol_ratio < 0.5:
        assert vol_class == "LOW_VOLUME"
        assert cqs_bonus == -10

# Feature: candlescout-pro, Property 10: Delta Volume and Ratio Calculation
@given(
    buy_volume=st.decimals(min_value=0, max_value=10000, places=2),
    sell_volume=st.decimals(min_value=0, max_value=10000, places=2)
)
@settings(max_examples=100)
def test_property_delta_ratio_bounds(buy_volume, sell_volume):
    """
    Feature: candlescout-pro, Property 10: Delta Volume and Ratio Calculation
    
    For any candle with tick data, delta calculated as buy_volume - sell_volume and
    delta_ratio as delta / (buy_volume + sell_volume) should satisfy -1 <= delta_ratio <= 1.
    """
    # Skip case where both volumes are zero
    if buy_volume == 0 and sell_volume == 0:
        return
    
    delta = buy_volume - sell_volume
    total_volume = buy_volume + sell_volume
    delta_ratio = float(delta / total_volume)
    
    # Property: delta_ratio must be bounded
    assert -1 <= delta_ratio <= 1
    
    # Property: suspicious flag for bullish candles with negative delta
    if delta_ratio < -0.2:
        # This should trigger SUSPICIOUS flag
        layer3 = Layer3Context()
        is_suspicious = layer3.check_delta_divergence(delta_ratio, is_bullish=True)
        assert is_suspicious is True

# Feature: candlescout-pro, Property 20: Risk/Reward Ratio Calculation
@given(
    entry_price=st.decimals(min_value=10, max_value=1000, places=2),
    stop_distance=st.decimals(min_value=0.1, max_value=50, places=2),
    target_distance=st.decimals(min_value=0.1, max_value=100, places=2)
)
@settings(max_examples=100)
def test_property_risk_reward_positive(entry_price, stop_distance, target_distance):
    """
    Feature: candlescout-pro, Property 20: Risk/Reward Ratio Calculation
    
    For any trading signal, risk_reward calculated as (take_profit_1 - entry_price) /
    (entry_price - stop_loss) should be positive.
    """
    stop_loss = entry_price - stop_distance
    take_profit_1 = entry_price + target_distance
    
    risk_reward = float((take_profit_1 - entry_price) / (entry_price - stop_loss))
    
    # Property: R/R must be positive
    assert risk_reward > 0
    
    # Property: R/R should equal target_distance / stop_distance
    expected_rr = float(target_distance / stop_distance)
    assert abs(risk_reward - expected_rr) < 0.01  # Allow small floating point error
```

### Test Coverage Requirements

**Minimum Coverage Targets**:
- Overall code coverage: 80%
- Critical paths (analysis pipeline, risk management): 95%
- API endpoints: 90%
- Error handling paths: 70%

**Coverage Measurement**:

```bash
# Run tests with coverage
pytest --cov=src --cov-report=html --cov-report=term

# Generate coverage report
coverage report -m
coverage html
```

### Performance Testing

**Load Testing**:

```python
import asyncio
import time
from locust import HttpUser, task, between

class CandleScoutUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def get_signals(self):
        self.client.get("/api/v1/signals?symbol=SOLUSDT&limit=10")
    
    @task(2)
    def get_latest_analysis(self):
        self.client.get("/api/v1/analysis/latest?symbol=SOLUSDT")
    
    @task(1)
    def get_stats(self):
        self.client.get("/api/v1/stats?symbol=SOLUSDT&days=7")

# Run: locust -f tests/load/locustfile.py --host=http://localhost:8000
```

**Latency Testing**:

```python
@pytest.mark.asyncio
async def test_pipeline_latency():
    """Test full pipeline completes within 500ms"""
    candle = create_test_candle()
    
    start_time = time.time()
    signal = await analysis_pipeline.process_candle(candle.id)
    end_time = time.time()
    
    latency_ms = (end_time - start_time) * 1000
    assert latency_ms < 500, f"Pipeline latency {latency_ms}ms exceeds 500ms"
```

### Continuous Integration

**CI Pipeline** (GitHub Actions):

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: timescale/timescaledb:latest-pg17
        env:
          POSTGRES_PASSWORD: test
      redis:
        image: redis:7.4-alpine
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Run unit tests
        run: pytest tests/unit -v
      
      - name: Run property tests
        run: pytest tests/property -v --hypothesis-show-statistics
      
      - name: Run integration tests
        run: pytest tests/integration -v
      
      - name: Check coverage
        run: pytest --cov=src --cov-fail-under=80
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

