import os
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

# List of files containing 'weex' from the scan
matching_files = [
    r"Legacy\all\agents\main\sessions\58fdb29e-0abd-4fd9-bb9e-e4ac262c70cf.jsonl.reset.2026-03-12T12-12-22.784Z",
    r"Legacy\all\agents\main\sessions\64e5b894-71b1-49d6-a780-2562dfebf5bf-topic-14901.jsonl",
    r"Legacy\all\agents\main\sessions\8ca46d71-c0fb-4ac8-8cba-6f5bd625d778-topic-14936.jsonl",
    r"Legacy\all\agents\main\sessions\9480d728-395f-4f59-991d-5b667dc86866-topic-973.jsonl",
    r"Legacy\all\agents\main\sessions\ca9aed13-36a3-4a17-aa3c-dadd11d25037.jsonl.reset.2026-03-11T14-29-32.233Z",
    r"Legacy\all\agents\main\sessions\f00edb88-ac63-4782-8c3c-295576286226-topic-15573.jsonl",
    r"Legacy\vps1_small\root\.openclaw\agents\main\sessions\029fbf66-12db-482d-a01b-4d989fd3ec5e.jsonl.deleted.2026-03-04T10-06-51.251Z",
    r"Legacy\vps1_small\root\.openclaw\agents\main\sessions\127ba3da-b33b-41ad-a0ca-3a291c83dbaf.jsonl.deleted.2026-03-04T06-26-48.890Z",
    r"Legacy\vps1_small\root\.openclaw\agents\main\sessions\3a67ffdd-73dc-48ba-938d-3dc3f42e5d28.jsonl.deleted.2026-03-05T22-23-09.044Z",
    r"Legacy\vps1_small\root\.openclaw\agents\main\sessions\430dba4a-5146-47e6-b057-e232656520f8.jsonl.deleted.2026-03-04T14-02-58.489Z",
    r"Legacy\vps1_small\root\.openclaw\agents\main\sessions\66221b29-cdcf-492c-b872-084449a1640a.jsonl",
    r"Legacy\vps1_small\root\.openclaw\agents\main\sessions\817e21ef-e698-42db-a78a-965959b5e054-topic-1.jsonl",
    r"Legacy\vps1_small\root\.openclaw\agents\main\sessions\8854c9ef-fc5d-4db1-b96c-4e8bf66091bb.jsonl.deleted.2026-03-05T01-02-12.149Z",
    r"Legacy\vps1_small\root\.openclaw\agents\main\sessions\8beb4642-8a6e-46a4-a99d-f48d959c6a6a.jsonl.reset.2026-02-23T03-11-33.729Z",
    r"Legacy\vps1_small\root\.openclaw\agents\main\sessions\a69a1206-3400-4924-9d89-2fe326de16bf.jsonl.deleted.2026-03-05T01-55-27.472Z",
    r"Legacy\vps1_small\root\.openclaw\agents\main\sessions\a9e0c70c-9091-4088-a011-f010d55dcdb2-topic-1.jsonl",
    r"Legacy\vps1_small\root\.openclaw\agents\main\sessions\b9e35475-ba48-4340-9b9a-7ff636a30461.jsonl",
    r"Legacy\vps1_small\root\.openclaw\agents\main\sessions\d3d7f8ea-7b33-498c-8bcf-f12124aca95a.jsonl",
    r"Legacy\vps1_small\root\.openclaw\agents\main\sessions\dd795db1-f197-4ee5-878c-7931e06d2830-topic-278.jsonl",
    r"Legacy\vps1_small\root\.openclaw\agents\main\sessions\e9be2f79-7a7d-43bd-bae1-d4b678ae3e15.jsonl.deleted.2026-03-04T04-32-55.924Z"
]

eais_root = r"C:\Users\pesil\EAIS"
out_file = r"c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\explorer_weex_1\all_weex_extracted.txt"

with open(out_file, "w", encoding="utf-8") as out:
    for rel_path in matching_files:
        full_path = os.path.join(eais_root, rel_path)
        if not os.path.exists(full_path):
            print(f"Skipping {rel_path} - not found")
            continue
            
        print(f"Parsing {rel_path}...")
        out.write(f"\n=========================================\n")
        out.write(f"FILE: {rel_path}\n")
        out.write(f"=========================================\n")
        
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f, 1):
                if "weex" in line.lower():
                    # Parse as JSON to extract text
                    try:
                        data = json.loads(line)
                        content = ""
                        # Try parsing message.content (like standard session JSONL)
                        if "message" in data and isinstance(data["message"], dict):
                            msg = data["message"]
                            if "content" in msg:
                                if isinstance(msg["content"], list):
                                    for part in msg["content"]:
                                        if isinstance(part, dict) and "text" in part:
                                            content += part["text"] + "\n"
                                elif isinstance(msg["content"], str):
                                    content = msg["content"]
                        elif "content" in data:
                            content = data["content"]
                            
                        # If content contains weex, write it out
                        if content and "weex" in content.lower():
                            out.write(f"\n--- Turn {i} (length={len(content)}) ---\n")
                            out.write(content)
                            out.write("\n" + "-"*50 + "\n")
                    except Exception as e:
                        # Fallback for plain lines
                        if len(line) < 5000:
                            out.write(f"\n--- Plain Line {i} ---\n")
                            out.write(line)
                            out.write("\n" + "-"*50 + "\n")

print(f"Extraction of all sessions complete. Output written to {out_file}")
