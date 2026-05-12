import os
import sys
import logging

logging.basicConfig(level=logging.DEBUG)

os.environ["TELEGRAM_BOT_ENABLED"] = "false"
os.environ["BRIEF_ENABLED"] = "false"
os.environ["RAG_ENABLED"] = "false"
os.environ["MCP_ENABLED"] = "false"
os.environ["DASHBOARD_TOKEN"] = ""

from main import app
from fastapi.testclient import TestClient

print("Starting TestClient...")
try:
    client = TestClient(app)
    print("TestClient started successfully!")
except Exception as e:
    print(f"Exception during TestClient: {e}")
