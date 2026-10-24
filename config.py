"""Scanner settings. Everything here is safe to tweak."""

# Venues (ccxt ids). All of them expose public order books, no API keys needed.
EXCHANGES = ["binance", "coinbaseexchange", "kraken", "okx", "bybit"]

# Base assets to watch. Each one is matched against USDT, then USDC, then USD.
BASES = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "TON", "SUI"]
QUOTES = ["USDT", "USDC", "USD"]

# A gap is flagged when best bid on one venue beats best ask on another by this much.
MIN_SPREAD_BPS = 5.0  # 0.05%

# Fallback taker fee if an exchange doesn't report one (fraction, 0.001 = 0.10%).
DEFAULT_TAKER_FEE = 0.001

# Rough cost of rebalancing inventory between venues, in USD per trade.
# Real withdrawal fees vary by asset and network; this keeps the model honest.
TRANSFER_COST_USD = 0.50

# Paper trade size per leg, in USD, and starting paper balance.
TRADE_SIZE_USD = 500.0
PAPER_BALANCE_USD = 1_000.0

# How often to re-measure round-trip latency to each venue (seconds).
LATENCY_REFRESH_S = 30

# Order book depth to request. Some venues only accept specific values.
BOOK_LIMIT = 20
BOOK_LIMITS = {"kraken": 25, "bybit": 50, "okx": None}

# Venues whose public websocket needs an API key: poll their REST order book instead.
REST_ONLY = {"coinbaseexchange"}
REST_POLL_S = 1.0

# Where every gap and its fate gets written.
LOG_CSV = "gaps.csv"
