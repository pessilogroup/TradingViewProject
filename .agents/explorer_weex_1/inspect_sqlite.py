import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

db_path = r"C:\Users\pesil\EAIS\Legacy\vps1_small\root\.openclaw\agents\main\qmd\xdg-cache\qmd\index.sqlite"

if not os.path.exists(db_path):
    print("Database does not exist.")
    exit()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables in db:", tables)

for table in tables:
    table_name = table[0]
    cursor.execute(f"PRAGMA table_info({table_name});")
    info = cursor.fetchall()
    print(f"Table {table_name} schema: {info}")
    
    # Try searching for "weex" in columns
    cursor.execute(f"SELECT * FROM {table_name} LIMIT 1;")
    sample = cursor.fetchone()
    if sample:
        # Avoid printing huge text
        sample_str = str(sample)[:300]
        print(f"Sample row from {table_name}: {sample_str}")

    # Find rows with weex (case-insensitive)
    text_cols = [col[1] for col in info]
    
    for col in text_cols:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {col} LIKE '%weex%';")
            count = cursor.fetchone()[0]
            if count > 0:
                print(f"  Column {col} has {count} rows containing 'weex'")
                cursor.execute(f"SELECT {col} FROM {table_name} WHERE {col} LIKE '%weex%' LIMIT 5;")
                rows = cursor.fetchall()
                for r in rows:
                    content_str = str(r[0])
                    print(f"    Match (len={len(content_str)}): {content_str[:200]}...")
        except Exception as e:
            # print(f"Error checking {col}: {e}")
            pass

conn.close()
