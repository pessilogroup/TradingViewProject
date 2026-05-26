import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

root_dir = r"C:\Users\pesil\EAIS"
out_path = "eais_scan_output.txt"

exclude_dirs = {
    '.git', '.gocache', '.pytest_cache', '.vscode', '.agents', 
    'clean_room_test', 'eais-backend', 'eais-client', 'eais-infrastructure', 
    'openclaw-gateway-core', 'openclaw-worker', 'trz-research-agent', 'tmp',
    'workspaces', 'node_modules', '__pycache__'
}

exclude_files = {
    'Angati_EdgeNode_ARM64.zip'
}

with open(out_path, "w", encoding="utf-8") as out:
    def write_log(msg):
        print(msg)
        out.write(msg + "\n")
        
    write_log(f"Scanning {root_dir} for 'weex'...")
    
    for root, dirs, files in os.walk(root_dir):
        # Modify dirs in-place to avoid traversing excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if file in exclude_files:
                continue
            file_path = os.path.join(root, file)
            # Skip very large files
            try:
                size = os.path.getsize(file_path)
                if size > 5 * 1024 * 1024: # skip files > 5MB
                    continue
            except:
                continue
                
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if "weex" in content.lower():
                        rel_path = os.path.relpath(file_path, root_dir)
                        write_log(f"Found 'weex' in {rel_path} (size: {size} bytes)")
                        # Print some lines around the match
                        lines = content.splitlines()
                        for i, line in enumerate(lines):
                            if "weex" in line.lower():
                                start = max(0, i - 2)
                                end = min(len(lines), i + 3)
                                write_log(f"  Context (lines {start+1}-{end}):")
                                for j in range(start, end):
                                    write_log(f"    {j+1}: {lines[j]}")
                                write_log("-" * 30)
            except Exception as e:
                pass
                
    write_log("Scan completed.")
