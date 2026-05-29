import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

dir_path = r"c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\explorer_weex_1"
files = [f for f in os.listdir(dir_path) if f.startswith("turn_") and f.endswith(".md") and "turn_111" not in f]
out_path = os.path.join(dir_path, "all_turns_text_utf8.txt")

print(f"Reading through {len(files)} turn files and writing to {out_path}...")

with open(out_path, "w", encoding="utf-8") as out:
    for f_name in files:
        f_path = os.path.join(dir_path, f_name)
        with open(f_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        out.write(f"\n========================================================\n")
        out.write(f"FILE: {f_name}\n")
        out.write(f"========================================================\n")
        out.write(content)
        out.write("\n")

print("Done writing turns to UTF-8 file.")
