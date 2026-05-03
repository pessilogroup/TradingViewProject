import os
from dotenv import load_dotenv

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