import os
import sys

print("Setting env vars...")
os.environ["TELEGRAM_BOT_ENABLED"] = "false"
os.environ["BRIEF_ENABLED"] = "false"
os.environ["RAG_ENABLED"] = "false"
os.environ["MCP_ENABLED"] = "false"
os.environ["DASHBOARD_TOKEN"] = ""

print("Importing config...")
import config
print("Importing notifier...")
import notifier
print("Importing database...")
import database
print("Importing rag...")
import rag
print("Importing mcp_client...")
import mcp_client
print("Importing watchlist...")
import watchlist
print("Importing analysis...")
import analysis
print("Importing brief...")
import brief
print("Importing scheduler...")
import scheduler
print("Importing telegram_bot...")
import telegram_bot
print("Importing vision...")
import vision
print("Importing binance_client...")
import binance_client

print("All dependencies imported successfully!")

# Ingest Weex L1 Memory
try:
    print("Running Weex L1 Ingestion...")
    import sys
    sys.path.insert(0, r"c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\worker_weex_3")
    import ingest_l1
    ingest_l1.main()
    print("Weex L1 Ingestion complete!")
except Exception as e:
    print(f"Weex L1 Ingestion failed: {e}")
