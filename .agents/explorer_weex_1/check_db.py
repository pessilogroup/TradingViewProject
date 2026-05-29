import sqlite3
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

memory_dir = r"C:\Users\pesil\EAIS\.agents\memory"
out_path = "db_inspect_output.txt"

with open(out_path, "w", encoding="utf-8") as out:
    def write_log(msg):
        print(msg)
        out.write(msg + "\n")
        
    db_files = [f for f in os.listdir(memory_dir) if f.endswith(".db")]
    write_log(f"Found databases in {memory_dir}: {db_files}")
    
    for db_file in db_files:
        db_path = os.path.join(memory_dir, db_file)
        write_log(f"\n=========================================\nInspecting database: {db_file}\n=========================================")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [t[0] for t in cursor.fetchall()]
            write_log(f"Tables in {db_file}: {tables}")
            
            for table in tables:
                cursor.execute(f"PRAGMA table_info({table});")
                schema = cursor.fetchall()
                write_log(f"  Table: {table}")
                
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                write_log(f"  Row count: {count}")
                
                # Check column schema
                cols = [col[1] for col in schema]
                found_match = False
                for col in cols:
                    try:
                        # Safe query to avoid SQL injection on table/column names (they are from pragma/sqlite_master)
                        # We use LIKE '%weex%'
                        cursor.execute(f"SELECT * FROM [{table}] WHERE CAST([{col}] AS TEXT) LIKE '%weex%'")
                        matches = cursor.fetchall()
                        if matches:
                            found_match = True
                            write_log(f"    Found {len(matches)} matches in column [{col}]:")
                            for m in matches[:5]: # limit to 5
                                write_log(f"      {m}")
                            if len(matches) > 5:
                                write_log(f"      ... and {len(matches) - 5} more matches")
                    except Exception as ex:
                        # Some tables might have virtual/FTS columns that don't like CAST or similar
                        pass
                if not found_match:
                    write_log("    No 'weex' matches.")
        except Exception as e:
            write_log(f"  Error reading {db_file}: {e}")
            
    # Also check if there are other files in the memory dir that contain the word "weex"
    write_log("\n=========================================\nChecking other files in memory folder for 'weex'\n=========================================")
    for f in os.listdir(memory_dir):
        if not f.endswith(".db") and os.path.isfile(os.path.join(memory_dir, f)):
            try:
                with open(os.path.join(memory_dir, f), "r", encoding="utf-8", errors="ignore") as file_obj:
                    content = file_obj.read()
                    if "weex" in content.lower():
                        write_log(f"Found 'weex' in text file: {f}")
            except Exception as e:
                pass
