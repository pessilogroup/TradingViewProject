import os
import re

extracted_path = r"c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\explorer_weex_1\weex_extracted_details.txt"

if not os.path.exists(extracted_path):
    print("Extracted file does not exist.")
    exit()

print(f"Extracted file size: {os.path.getsize(extracted_path)} bytes")

# Read file and look for main sections or topics
with open(extracted_path, "r", encoding="utf-8") as f:
    content = f.read()

# Let's see what keywords appear and how many times:
keywords = [
    "spot/introduction", "contract/intro", "changelog", "signature", "websocket", "V2", 
    "QuickStart", "IntegrationPreparation", "weex.com", "weex-api", "ws.weex.com", 
    "api-doc/spot", "api-doc/contract", "Request Headers", "Request Parameters",
    "Signature Algorithm", "GET /api/v1", "POST /api/v1", "GET /api/v2", "POST /api/v2"
]

print("Keyword occurrences in the extracted details:")
for kw in keywords:
    count = len(re.findall(re.escape(kw), content, re.IGNORECASE))
    print(f"  - '{kw}': {count}")

# Let's write a small script that splits the text by FILE: and Turn and reports summaries
blocks = content.split("=========================================\n")
print(f"\nNumber of file sections: {len(blocks) - 1}")
for block in blocks[1:]:
    lines = block.splitlines()
    if lines:
        filename = lines[0]
        # count turns
        turns = re.findall(r"--- Turn (\d+)", block)
        print(f"  File: {filename} has {len(turns)} turns mentioning 'weex'")
        
        # Print first few turns info
        for t in turns[:3]:
            # find turn content length
            turn_header = f"--- Turn {t}"
            t_idx = block.find(turn_header)
            if t_idx != -1:
                next_turn = block.find("--- Turn", t_idx + len(turn_header))
                if next_turn == -1:
                    next_turn = block.find("--------------------------------------------------\n", t_idx)
                turn_content = block[t_idx:next_turn]
                
                # Check what headings are in this turn
                headings = [line for line in turn_content.splitlines() if line.strip().startswith("#")]
                print(f"    - Turn {t}: Headings found: {headings[:5]}")

