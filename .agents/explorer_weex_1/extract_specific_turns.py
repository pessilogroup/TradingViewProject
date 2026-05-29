import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

extracted_path = r"c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\explorer_weex_1\all_weex_extracted.txt"

if not os.path.exists(extracted_path):
    print("Extracted file does not exist.")
    exit()

with open(extracted_path, "r", encoding="utf-8") as f:
    content = f.read()

# We can find each FILE: marker and extract content up to the next FILE: or end
sections = re.split(r"=========================================\nFILE: ", content)

print(f"Found {len(sections)-1} file sections.")

for sec in sections[1:]:
    lines = sec.splitlines()
    if not lines:
        continue
    file_path = lines[0].strip()
    file_name = os.path.basename(file_path)
    print(f"\nProcessing section for file: {file_name}")
    
    # Rest of section is the content of this file
    sec_content = "\n".join(lines[1:])
    
    # Find all turns: they start with "--- Turn {i} (length={len}) ---" and end with "--------------------------------------------------"
    # We can split by "--- Turn "
    turns = sec_content.split("--- Turn ")
    print(f"  Turns found: {len(turns)-1}")
    
    for turn in turns[1:]:
        # Parse the turn number and length
        header_match = re.match(r"^(\d+)\s*\(length=(\d+)\)\s*---", turn)
        if header_match:
            turn_no = header_match.group(1)
            turn_len = int(header_match.group(2))
            
            # Extract content after header line
            turn_lines = turn.splitlines()
            turn_text = "\n".join(turn_lines[1:])
            # Remove trailing separator lines
            turn_text = re.sub(r"-{30,}\s*$", "", turn_text)
            
            print(f"    - Turn {turn_no}: size {len(turn_text)} (reported: {turn_len})")
            
            # Save if it's large or has content
            if len(turn_text) > 500:
                safe_name = file_name.replace(".jsonl", "").replace(".reset", "").replace(".deleted", "").replace("-topic", "")
                safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", safe_name)
                out_name = f"turn_{safe_name}_turn_{turn_no}.md"
                out_path = os.path.join(r"c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\explorer_weex_1", out_name)
                with open(out_path, "w", encoding="utf-8") as out_f:
                    out_f.write(f"# File: {file_path}\n# Turn: {turn_no}\n\n" + turn_text)
                print(f"      Saved to {out_name}")

print("\nDone extracting turns.")
