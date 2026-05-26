import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

dir_path = r"c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\explorer_weex_1"
files = [f for f in os.listdir(dir_path) if f.startswith("turn_") and f.endswith(".md")]

print(f"Searching {len(files)} turn files...")

for file_name in files:
    file_path = os.path.join(dir_path, file_name)
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    
    # Check for keywords
    keywords = ["/api/v", "signature", "websocket", "wss://", "endpoint", "contract", "spot", "changelog", "weex.com", "api-doc"]
    matches = {kw: len(re.findall(re.escape(kw), text, re.IGNORECASE)) for kw in keywords}
    total_matches = sum(matches.values())
    
    if total_matches > 0:
        print(f"\nFile: {file_name} (size: {len(text)} chars)")
        print(f"  Matches: { {k: v for k, v in matches.items() if v > 0} }")
        # Print lines that look like endpoints or signatures
        lines = text.splitlines()
        found_endpoints = []
        found_headers = []
        for line in lines:
            if line.strip().startswith("#"):
                found_headers.append(line.strip())
            # check for endpoints
            if any(term in line.lower() for term in ["/api/v", "wss://", "sign="]) or ("signature" in line.lower() and len(line) < 150):
                if len(line) < 200:
                    found_endpoints.append(line.strip())
        
        if found_headers:
            print(f"  Headers: {found_headers[:5]}")
        if found_endpoints:
            print(f"  Endpoints/Signatures Context ({len(found_endpoints)}):")
            for ep in found_endpoints[:10]:
                print(f"    {ep}")
