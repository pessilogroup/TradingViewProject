import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

eais_dir = r"C:\Users\pesil\EAIS"
archive_exts = (".zip", ".tar.gz", ".tgz", ".tar", ".gz", ".zip")

print(f"Searching {eais_dir} for archive files...")

found = False
for root, dirs, files in os.walk(eais_dir):
    for file in files:
        if file.lower().endswith(archive_exts):
            file_path = os.path.join(root, file)
            found = True
            print(f"Found archive: {os.path.relpath(file_path, eais_dir)} (size: {os.path.getsize(file_path)} bytes)")

if not found:
    print("No archive files found.")
