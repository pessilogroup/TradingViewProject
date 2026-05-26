import os

out_path = "eais_scan_output.txt"
if os.path.exists(out_path):
    with open(out_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    print(f"Total lines in output: {len(lines)}")
    found_lines = [line.strip() for line in lines if line.startswith("Found 'weex'")]
    print(f"Number of files found: {len(found_lines)}")
    print("\nFiles found:")
    for fl in found_lines:
        print(fl)
else:
    print("Scan output file not found.")
