import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 5000))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Security
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change_me_in_dotenv")

# Logging
LOG_FILE = os.getenv("LOG_FILE", "trades.log")

# Database (Sprint 4)
DB_PATH = os.getenv("DB_PATH", "trades.db")

# Binance (optional)
BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
BINANCE_TESTNET    = os.getenv("BINANCE_TESTNET", "true").lower() == "true"

# Notifications
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")
DISCORD_WEBHOOK_URL= os.getenv("DISCORD_WEBHOOK_URL", "")

# TradingView Whitelist IPs
TV_WHITELIST_IPS = {
    "52.89.214.238",
    "34.212.75.30",
    "54.218.53.128",
    "52.32.178.7"
}
ENABLE_IP_WHITELIST = os.getenv("ENABLE_IP_WHITELIST", "false").lower() == "true"

# ── RAG / Knowledge Base ──────────────────────────────────────────────────
# Đường dẫn tới thư mục chứa các file chunk Markdown của Minervini
KNOWLEDGE_DIR = os.getenv(
    "KNOWLEDGE_DIR",
    str(Path(__file__).parent.parent / "docs" / "knowledge" / "trading_wizard" / "chunks")
)

# Đường dẫn lưu ChromaDB vector database (persistent trên disk)
CHROMA_DB_PATH = os.getenv(
    "CHROMA_DB_PATH",
    str(Path(__file__).parent / "chroma_db")
)

# Anthropic (Claude) API Key — dùng cho bước Generation trong RAG
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Số chunks tối đa trả về cho mỗi query (2-3 là tối ưu)
RAG_TOP_K = int(os.getenv("RAG_TOP_K", 3))

# Bật/tắt tính năng RAG (để không bắt buộc phải có API key)
RAG_ENABLED = os.getenv("RAG_ENABLED", "true").lower() == "true"

# ── P6: MCP / Morning Brief ───────────────────────────────────────────────────────────────
# Kích hoạt TradingView MCP (CDP) integration
MCP_ENABLED = os.getenv("MCP_ENABLED", "false").lower() == "true"

# Chrome DevTools Protocol port (TradingView Desktop phải chạy với --remote-debugging-port=9222)
MCP_CDP_PORT = int(os.getenv("MCP_CDP_PORT", 9222))

# Path tới Node.js executable (để trống = tự detect từ PATH)
MCP_NODE_PATH = os.getenv("MCP_NODE_PATH", "node")

# Bật/tắt Morning Brief scheduler
BRIEF_ENABLED = os.getenv("BRIEF_ENABLED", "false").lower() == "true"

# Giờ chạy Morning Brief (HH:MM, timezone ICT = UTC+7)
BRIEF_CRON_TIME = os.getenv("BRIEF_CRON_TIME", "07:00")

# Watchlist symbols mặc định (comma-separated, override bởi server/watchlist.json)
WATCHLIST_DEFAULT = [
    s.strip().upper()
    for s in os.getenv("WATCHLIST_SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT").split(",")
    if s.strip()
]
