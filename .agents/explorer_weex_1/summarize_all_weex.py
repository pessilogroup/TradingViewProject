import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

extracted_path = r"c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\explorer_weex_1\all_weex_extracted.txt"

if not os.path.exists(extracted_path):
    print("Extracted file does not exist.")
    exit()

print(f"Extracted file size: {os.path.getsize(extracted_path)} bytes")

with open(extracted_path, "r", encoding="utf-8") as f:
    content = f.read()

# Let's count some key words:
keywords = [
    "spot", "contract", "signature", "websocket", "V2", "API", "endpoint", 
    "request", "response", "model", "changelog", "QuickStart", "IntegrationPreparation"
]

print("Keyword counts:")
for kw in keywords:
    matches = len(re.findall(re.escape(kw), content, re.IGNORECASE))
    print(f"  - '{kw}': {matches}")

# Let's find all headers:
headers = re.findall(r"^#+\s+(.*)$", content, re.MULTILINE)
print(f"\nTotal markdown headers in file: {len(headers)}")
for h in headers[:40]:
    print(f"  Header: {h}")

# Let's split by FILE: and report how many turns each file contributed and size:
blocks = content.split("=========================================\n")
print(f"\nSubsections by file:")
for block in blocks[1:]:
    lines = block.splitlines()
    if lines:
        filename = lines[0]
        turns = re.findall(r"--- Turn (\d+)", block)
        print(f"  File {filename} - {len(turns)} turns. Block size={len(block)} characters")
        # Print headings inside the block
        sub_headers = re.findall(r"^#+\s+(.*)$", block, re.MULTILINE)
        if sub_headers:
            print(f"    Headers found in block: {sub_headers[:10]}")
