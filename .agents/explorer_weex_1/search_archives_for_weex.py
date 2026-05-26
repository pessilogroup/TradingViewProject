import os
import tarfile
import zipfile
import sys

sys.stdout.reconfigure(encoding='utf-8')

legacy_dir = r"C:\Users\pesil\EAIS\Legacy"
archives = [
    r"gateway_bunkerv1.tar.gz",
    r"gateway_bunkerv2.tar.gz",
    r"openclaw_all.tar.gz",
    r"vps1_20260307_000002.tar.gz",
    r"vps1_core_bunkerv2.tar.gz",
    r"vps1_openclaw_all_20260318_080653.tar.gz",
    r"vps1_full\home\node\.openclaw\workspace\archives\legacy_2026_03_17.tar.gz"
]

print("Searching files in archive lists for 'weex' or 'trade_guard'...")

for arc in archives:
    arc_path = os.path.join(legacy_dir, arc)
    if not os.path.exists(arc_path):
        print(f"Archive not found: {arc_path}")
        continue
        
    print(f"\nChecking archive: {arc} (size: {os.path.getsize(arc_path)} bytes)")
    try:
        if arc.endswith(".tar.gz") or arc.endswith(".tgz"):
            with tarfile.open(arc_path, "r:gz") as tar:
                names = tar.getnames()
                matches = [n for n in names if "weex" in n.lower() or "trade_guard" in n.lower()]
                if matches:
                    print(f"  Found {len(matches)} matches:")
                    for m in matches[:10]:
                        print(f"    {m}")
                    if len(matches) > 10:
                        print(f"    ... and {len(matches) - 10} more")
                else:
                    print("  No matches in file list.")
        elif arc.endswith(".zip"):
            with zipfile.ZipFile(arc_path, "r") as zip_ref:
                names = zip_ref.namelist()
                matches = [n for n in names if "weex" in n.lower() or "trade_guard" in n.lower()]
                if matches:
                    print(f"  Found {len(matches)} matches:")
                    for m in matches[:10]:
                        print(f"    {m}")
                    if len(matches) > 10:
                        print(f"    ... and {len(matches) - 10} more")
                else:
                    print("  No matches in file list.")
    except Exception as e:
        print(f"  Error reading archive: {e}")

print("\nArchive search complete.")
