import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

file_path = r"c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\explorer_weex_1\turn_e9be2f79-7a7d-43bd-bae1-d4b678ae3e15_2026-03-04T04-32-55_924Z_turn_111.md"

if not os.path.exists(file_path):
    print("Large turn file does not exist.")
    exit()

print(f"Reading file: {file_path}")
with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()

print(f"Total length: {len(text)} characters")

# Find markdown headers
headers = re.findall(r"^(#+\s+.*)$", text, re.MULTILINE)
print(f"Headers found ({len(headers)}):")
for h in headers[:50]:
    print(f"  {h}")

# Search for some terms
terms = ["signature", "websocket", "contract", "spot", "/api/v", "/api/v2", "changelog"]
print("\nTerm frequency:")
for term in terms:
    count = len(re.findall(re.escape(term), text, re.IGNORECASE))
    print(f"  '{term}': {count}")
    
# Print some segments near headers
print("\nFirst 1000 characters:")
print(text[:1000])

print("\n--- Summary complete ---")
