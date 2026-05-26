import sqlite3
import os

db_path = r"C:\Users\pesil\EAIS\memory\V3_brain.db"
if not os.path.exists(db_path):
    db_path = r"c:\Users\pesil\working\mj_trading\TradingViewProject\memory\V3_brain.db"

print(f"Checking database at: {db_path}")
if not os.path.exists(db_path):
    print("Database not found!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Print tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [t[0] for t in cursor.fetchall()]
print(f"Tables: {tables}")

# 2. Get table info for memories
if "memories" in tables:
    cursor.execute("PRAGMA table_info(memories);")
    columns = cursor.fetchall()
    print("Columns of 'memories' table:")
    for col in columns:
        print(f"  {col}")
        
    # 3. Print first 5 rows to see how integrity and other fields are populated
    cursor.execute("SELECT * FROM memories LIMIT 5;")
    rows = cursor.fetchall()
    print("First 5 rows in 'memories':")
    for r in rows:
        # truncate large content for readability
        r_list = list(r)
        # assuming schema: id, summary, content, vector_blob, metadata, ts, integrity
        # content is at index 2, let's truncate it
        if len(r_list) > 2 and isinstance(r_list[2], str):
            r_list[2] = r_list[2][:100] + "..."
        print(r_list)
else:
    print("No 'memories' table found.")

conn.close()
