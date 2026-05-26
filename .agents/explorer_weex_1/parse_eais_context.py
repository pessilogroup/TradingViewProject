import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

scan_output_path = r"c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\explorer_weex_1\eais_scan_output.txt"

if not os.path.exists(scan_output_path):
    print("Scan output file not found.")
    exit()

print("Reading scan output...")
with open(scan_output_path, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}")

# Let's group lines by file
current_file = None
file_matches = {}

for line in lines:
    if line.startswith("Found 'weex'"):
        current_file = line.strip()
        file_matches[current_file] = []
    elif current_file and line.strip() and not line.startswith("Scan completed") and not line.startswith("Scanning"):
        file_matches[current_file].append(line)

print(f"Number of files with matches: {len(file_matches)}")
for filename, matches in file_matches.items():
    print(f"\n=========================================")
    print(filename)
    print(f"Total context lines: {len(matches)}")
    # Print first 20 lines of context to see what they look like
    for m in matches[:30]:
        print(m.rstrip())
