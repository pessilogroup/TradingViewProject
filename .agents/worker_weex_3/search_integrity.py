import os

search_dir = r"C:\Users\pesil\EAIS"
keywords = ["integrity", "V3_brain"]

matches = []
for root, dirs, files in os.walk(search_dir):
    if any(p in root for p in [".git", "cache", "openclaw-worker", "Legacy", "test_scaffold", "npm_tools"]):
        continue
    for file in files:
        if file.endswith((".py", ".go", ".json", ".js", ".mjs")):
            file_path = os.path.join(root, file)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    found = [kw for kw in keywords if kw in content]
                    if found:
                        matches.append((file_path, found))
            except Exception as e:
                pass

print(f"Found {len(matches)} files:")
for m in matches:
    print(f"File: {m[0]} -> Keywords: {m[1]}")
