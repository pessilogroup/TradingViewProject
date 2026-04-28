import os
from dotenv import load_dotenv

load_dotenv()

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 5000))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Security — set this in .env and configure the same value in TradingView alert headers
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change_me_in_dotenv")

# Logging
LOG_FILE = os.getenv("LOG_FILE", "trades.log")

# Binance (optional — leave blank to skip order placement)
BINANCE_API_KEY    = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
BINANCE_TESTNET    = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
