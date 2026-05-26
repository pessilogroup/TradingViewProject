import sqlite3
import os

db_path = r"C:\Users\pesil\EAIS\memory\V3_brain.db"
print("DB Exists:", os.path.exists(db_path))

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # List tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables:", tables)
    
    for table_name_tup in tables:
        table_name = table_name_tup[0]
        cursor.execute(f"PRAGMA table_info({table_name});")
        info = cursor.fetchall()
        print(f"Table info for {table_name}:", info)
    
    conn.close()
