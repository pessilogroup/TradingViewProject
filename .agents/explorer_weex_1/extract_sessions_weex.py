import os
import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

session_files = [
    r"C:\Users\pesil\EAIS\Legacy\all\agents\main\sessions\58fdb29e-0abd-4fd9-bb9e-e4ac262c70cf.jsonl.reset.2026-03-12T12-12-22.784Z",
    r"C:\Users\pesil\EAIS\Legacy\all\agents\main\sessions\64e5b894-71b1-49d6-a780-2562dfebf5bf-topic-14901.jsonl",
    r"C:\Users\pesil\EAIS\Legacy\all\agents\main\sessions\8ca46d71-c0fb-4ac8-8cba-6f5bd625d778-topic-14936.jsonl",
    r"C:\Users\pesil\EAIS\Legacy\all\agents\main\sessions\9480d728-395f-4f59-991d-5b667dc86866-topic-973.jsonl",
    r"C:\Users\pesil\EAIS\Legacy\all\agents\main\sessions\ca9aed13-36a3-4a17-aa3c-dadd11d25037.jsonl.reset.2026-03-11T14-29-32.233Z",
    r"C:\Users\pesil\EAIS\Legacy\all\agents\main\sessions\f00edb88-ac63-4782-8c3c-295576286226-topic-15573.jsonl"
]

out_dir = r"c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\explorer_weex_1"
out_path = os.path.join(out_dir, "weex_extracted_details.txt")

with open(out_path, "w", encoding="utf-8") as out:
    for s_file in session_files:
        if not os.path.exists(s_file):
            out.write(f"File not found: {s_file}\n")
            continue
        
        out.write(f"\n=========================================\n")
        out.write(f"FILE: {os.path.basename(s_file)}\n")
        out.write(f"=========================================\n")
        
        count = 0
        with open(s_file, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, 1):
                if "weex" in line.lower():
                    # Parse as JSON if possible
                    try:
                        data = json.loads(line)
                        # Extract message content
                        content = ""
                        if "message" in data:
                            msg = data["message"]
                            if isinstance(msg, dict) and "content" in msg:
                                c = msg["content"]
                                if isinstance(c, list):
                                    for item in c:
                                        if isinstance(item, dict) and "text" in item:
                                            content += item["text"] + "\n"
                                elif isinstance(c, str):
                                    content = c
                        elif "content" in data:
                            content = data["content"]
                        
                        if not content:
                            content = line[:500] # fallback
                        
                        # Write the file context
                        out.write(f"\n--- Turn {line_no} (length={len(content)}) ---\n")
                        # Let's clean up content or output specific portions
                        out.write(content)
                        out.write("\n" + "-"*50 + "\n")
                        count += 1
                    except Exception as e:
                        out.write(f"\n--- Turn {line_no} (JSON Parse Error: {e}) ---\n")
                        out.write(line[:1000] + "...\n")
                        count += 1
        
        out.write(f"Extracted {count} occurrences from {os.path.basename(s_file)}\n")

print(f"Extraction complete. Results written to {out_path}")
