import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

paths_to_check = [
    r"C:\Users\pesil\EAIS\.agents\lobes\knowledge\weex",
    r"c:\Users\pesil\working\mj_trading\TradingViewProject\lobes\knowledge\weex",
    r"C:\Users\pesil\EAIS\.agents\lobes\knowledge",
    r"c:\Users\pesil\working\mj_trading\TradingViewProject\lobes\knowledge",
    r"C:\Users\pesil\EAIS\.agents",
    r"c:\Users\pesil\working\mj_trading\TradingViewProject\.agents"
]

for p in paths_to_check:
    exists = os.path.exists(p)
    is_dir = os.path.isdir(p) if exists else False
    print(f"Path: {p}")
    print(f"  Exists: {exists}, IsDir: {is_dir}")
    if exists and is_dir:
        files = os.listdir(p)
        print(f"  Contents (up to 15 items): {files[:15]}")
        # check subdirs recursively for weex
        for f in files:
            full = os.path.join(p, f)
            if os.path.isdir(full):
                print(f"    Subdir: {f} -> {os.listdir(full)[:10]}")
    print("-" * 50)
