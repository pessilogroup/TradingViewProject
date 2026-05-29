import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

extracted_path = r"c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\explorer_weex_1\all_weex_extracted.txt"

if not os.path.exists(extracted_path):
    print("Extracted file does not exist.")
    exit()

with open(extracted_path, "r", encoding="utf-8") as f:
    content = f.read()

# Let's split by file block
blocks = content.split("=========================================\n")

for block in blocks[1:]:
    lines = block.splitlines()
    if not lines:
        continue
    filename = lines[0]
    
    # We are interested in e9be2f79-7a7d-43bd-bae1-d4b678ae3e15
    if "e9be2f79-7a7d-43bd-bae1-d4b678ae3e15" in filename:
        print(f"Found large file block: {filename}")
        turns = block.split("--- Turn ")
        print(f"Number of turns in block: {len(turns) - 1}")
        for t_idx, turn in enumerate(turns[1:], 1):
            turn_lines = turn.splitlines()
            header = turn_lines[0] if turn_lines else ""
            print(f"  Turn {t_idx} header: {header}, length: {len(turn)} characters")
            
            # Print the first 500 characters of the turn content
            print("  --- Start of Turn Content ---")
            print(turn[:1000])
            print("  --- End of Turn Content ---")
            
            # Write this turn to a separate file for easy reading
            out_turn_path = f"c:\\Users\\pesil\\working\\mj_trading\\TradingViewProject\\.agents\\explorer_weex_1\\large_turn_{t_idx}.txt"
            with open(out_turn_path, "w", encoding="utf-8") as tf:
                tf.write(turn)
            print(f"  Saved turn to {out_turn_path}")
            
    # Also inspect d3d7f8ea-7b33-498c-8bcf-f12124aca95a
    if "d3d7f8ea" in filename:
        print(f"Found medium file block: {filename}")
        turns = block.split("--- Turn ")
        for t_idx, turn in enumerate(turns[1:], 1):
            out_turn_path = f"c:\\Users\\pesil\\working\\mj_trading\\TradingViewProject\\.agents\\explorer_weex_1\\med_turn_{t_idx}.txt"
            with open(out_turn_path, "w", encoding="utf-8") as tf:
                tf.write(turn)
            print(f"  Saved medium turn to {out_turn_path}")
