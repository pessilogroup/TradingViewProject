import os
import sqlite3

def find_dbs(search_dir):
    dbs = []
    for root, dirs, files in os.walk(search_dir):
        if any(p in root for p in [".git", "cache", "openclaw-worker", "Legacy", "test_scaffold", "npm_tools"]):
            continue
        for file in files:
            if file.endswith((".db", ".sqlite", ".sqlite3")):
                dbs.append(os.path.join(root, file))
    return dbs

search_dir = r"C:\Users\pesil\EAIS"
dbs = find_dbs(search_dir)
print(f"Found {len(dbs)} databases:")
for db in dbs:
    print(f"\nDB: {db}")
    try:
        conn = sqlite3.connect(db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]
        print(f"Tables: {tables}")
        for table in tables:
            cursor.execute(f"PRAGMA table_info([{table}]);")
            cols = [c[1] for c in cursor.fetchall()]
            print(f"  Table {table} columns: {cols}")
        conn.close()
    except Exception as e:
        print(f"  Error: {e}")
