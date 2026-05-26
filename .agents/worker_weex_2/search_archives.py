import tarfile
import os
import re

archive_paths = [
    r"C:\Users\pesil\EAIS\Legacy\openclaw_all.tar.gz",
    r"C:\Users\pesil\EAIS\Legacy\vps1_openclaw_all_20260318_080653.tar.gz"
]

dest_dir = r"c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\worker_weex_2\extracted"
os.makedirs(dest_dir, exist_ok=True)

keywords = ['weex', 'trade_guard', 'API_INTEGRATION_PLAN', 'docs']
# Create a compiled regex for speed
pattern = re.compile('|'.join(keywords), re.IGNORECASE)

for archive_path in archive_paths:
    print(f"Inspecting archive: {archive_path}")
    if not os.path.exists(archive_path):
        print(f"Archive not found: {archive_path}")
        continue
    
    try:
        with tarfile.open(archive_path, 'r:gz') as tar:
            count = 0
            matched_members = []
            for member in tar:
                # We search for keywords in the file name/path
                if pattern.search(member.name):
                    matched_members.append(member)
                    print(f"Match: {member.name} ({member.size} bytes)")
                    count += 1
            
            print(f"Found {count} matched files in {os.path.basename(archive_path)}")
            
            # Extract matched files
            for member in matched_members:
                # To avoid directory traversal and extract cleanly
                # We can extract it under dest_dir
                print(f"Extracting: {member.name}")
                try:
                    tar.extract(member, path=dest_dir)
                except Exception as e:
                    print(f"Error extracting {member.name}: {e}")
                    
    except Exception as e:
        print(f"Error reading archive {archive_path}: {e}")

print("Done scanning archives.")
