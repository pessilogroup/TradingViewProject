import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

root_dir = r"c:\Users\pesil\working\mj_trading\TradingViewProject"
out_path = "workspace_scan_output.txt"

exclude_dirs = {
    '.git', '.pytest_cache', '.ruff_cache', '.vscode', '.agents', 
    '__pycache__', 'node_modules'
}

with open(out_path, "w", encoding="utf-8") as out:
    def write_log(msg):
        print(msg)
        out.write(msg + "\n")
        
    write_log(f"Scanning workspace {root_dir} for 'weex'...")
    
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            file_path = os.path.join(root, file)
            try:
                size = os.path.getsize(file_path)
                if size > 5 * 1024 * 1024:
                    continue
            except:
                continue
                
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if "weex" in content.lower():
                        rel_path = os.path.relpath(file_path, root_dir)
                        write_log(f"Found 'weex' in {rel_path} (size: {size} bytes)")
                        lines = content.splitlines()
                        for i, line in enumerate(lines):
                            if "weex" in line.lower():
                                write_log(f"  {i+1}: {line}")
                        write_log("-" * 30)
            except Exception as e:
                pass
                
    write_log("Scan completed.")
