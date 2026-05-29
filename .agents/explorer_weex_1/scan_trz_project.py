import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

trz_dir = r"C:\Users\pesil\EAIS\Legacy\all\workspace\TRZ_Project"
print(f"Scanning {trz_dir} recursively for 'weex'...")

found = False
for root, dirs, files in os.walk(trz_dir):
    for file in files:
        file_path = os.path.join(root, file)
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if "weex" in content.lower():
                    found = True
                    print(f"\nFound 'weex' in {os.path.relpath(file_path, trz_dir)}")
                    lines = content.splitlines()
                    for i, line in enumerate(lines):
                        if "weex" in line.lower():
                            print(f"  Line {i+1}: {line.strip()}")
        except Exception as e:
            pass

if not found:
    print("No occurrences of 'weex' found in TRZ_Project.")
