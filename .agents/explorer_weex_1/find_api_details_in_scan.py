import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

scan_output_path = r"c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\explorer_weex_1\eais_scan_output.txt"

if not os.path.exists(scan_output_path):
    print("Scan output file not found.")
    exit()

print("Searching scan output for API details...")

keywords = ["/api/v", "wss://", "signature", "endpoint", "contract", "spot", "sign=", "api-doc"]
matched_lines = []

with open(scan_output_path, "r", encoding="utf-8", errors="ignore") as f:
    for i, line in enumerate(f, 1):
        # We look for lines in the context that match these keywords
        # The context lines usually start with "    [line_number]: [content]"
        if line.strip().startswith("Found 'weex'"):
            matched_lines.append(f"--- {line.strip()} ---")
        else:
            for kw in keywords:
                if kw in line.lower():
                    # check if it's a context line
                    matched_lines.append(f"Line {i}: {line.strip()}")
                    break

print(f"Found {len(matched_lines)} relevant lines in scan output.")
for line in matched_lines[:150]:  # print first 150 matches
    print(line)
