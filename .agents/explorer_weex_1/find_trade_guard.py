import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

root_dir = r"C:\Users\pesil\EAIS"
found_files = []

for root, dirs, files in os.walk(root_dir):
    for f in files:
        if "trade_guard" in f.lower() or "weex" in f.lower():
            full = os.path.join(root, f)
            found_files.append(full)
            print(f"Found file: {full} ({os.path.getsize(full)} bytes)")

if not found_files:
    print("No files with 'trade_guard' or 'weex' in filename found.")
else:
    # Print content of the first few files if they are small
    for path in found_files:
        if os.path.getsize(path) < 200000:
            print(f"\n--- Content of {path} ---")
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as file:
                    print(file.read()[:5000]) # print first 5k characters
            except Exception as e:
                print(f"Error reading: {e}")
            print("-" * 50)
