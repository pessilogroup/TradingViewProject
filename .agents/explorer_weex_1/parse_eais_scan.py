import os

out_path = r"c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\explorer_weex_1\eais_scan_output.txt"
if os.path.exists(out_path):
    with open(out_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("Found 'weex'"):
                print(line.strip())
else:
    print("Scan output file not found at " + out_path)
