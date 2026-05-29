import os
import sqlite3
import uuid
import datetime
import json
import urllib.request
import struct
import hashlib
import hmac
import socket
import getpass

db_paths = [
    r"C:\Users\pesil\EAIS\memory\V3_brain.db",
    r"c:\Users\pesil\working\mj_trading\TradingViewProject\memory\V3_brain.db"
]
ki_dir = r"c:\Users\pesil\working\mj_trading\TradingViewProject\lobes\knowledge\weex"
log_path = r"c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\worker_weex_3\ingestion_log.txt"

def get_embedding(text):
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:4747/api/embed",
            data=json.dumps({"text": text}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            if isinstance(res_data, list):
                vector = res_data
            elif isinstance(res_data, dict) and "embedding" in res_data:
                vector = res_data["embedding"]
            elif isinstance(res_data, dict) and "data" in res_data and isinstance(res_data["data"], list):
                vector = res_data["data"]
            else:
                vector = [0.0] * 384
            
            if len(vector) != 384:
                vector = (vector + [0.0]*384)[:384]
            return struct.pack('<384f', *vector)
    except Exception as e:
        return struct.pack('<384f', *[0.0]*384)

def compute_integrity(summary, content, metadata_str):
    angati_secret = os.environ.get("ANGATI_SECRET")
    if angati_secret:
        key = hashlib.sha256(angati_secret.encode('utf-8')).digest()
    else:
        hostname = socket.gethostname()
        username = getpass.getuser()
        seed = f"angati:{hostname}:{username}:v3"
        key = hashlib.sha256(seed.encode('utf-8')).digest()
    
    msg = summary.encode('utf-8') + b'\x00' + content.encode('utf-8') + b'\x00' + metadata_str.encode('utf-8')
    sig = hmac.new(key, msg, hashlib.sha256).hexdigest()
    return sig

def main():
    log_lines = ["--- Ingestion Log ---"]
    try:
        ki_files = [
            ("weex_spot_api.md", "Weex Spot API reference including base URL, headers, order operations, and request/response examples."),
            ("weex_contract_v2_api.md", "Weex Contract V2 API reference covering base URL, _UMCBL suffix, order operations, positions, and V2 migration changelog."),
            ("weex_websocket.md", "Weex WebSocket API specification outlining public tickers subscriptions, tickers payloads, and login authentication."),
            ("weex_signatures.md", "Weex signature calculation mechanism details and executable Python hmac/hashlib/base64 code example."),
            ("weex_quickstart_sandbox.md", "Weex Sandbox (Demo Mode) reference including sandbox URLs, demo keys rules, and mock assets matrix.")
        ]
        
        kis_data = []
        for file_name, summary in ki_files:
            file_path = os.path.join(ki_dir, file_name)
            if not os.path.exists(file_path):
                file_path = os.path.join(r"C:\Users\pesil\EAIS\.agents\lobes\knowledge\weex", file_name)
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    kis_data.append((file_name, summary, content))
            else:
                log_lines.append(f"Error: KI file {file_name} not found!")
                
        for db_path in db_paths:
            log_lines.append(f"Processing database: {db_path}")
            if not os.path.exists(db_path):
                log_lines.append(f"Database not found at {db_path}!")
                continue
                
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Clear old Weex memories if table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memories';")
            if not cursor.fetchone():
                log_lines.append("Table 'memories' not found in database!")
                conn.close()
                continue
                
            cursor.execute("DELETE FROM memories WHERE content LIKE '%Weex%' OR summary LIKE '%Weex%'")
            log_lines.append(f"Cleared old Weex memories. Rows deleted: {cursor.rowcount}")
            
            for file_name, summary, content in kis_data:
                mem_id = str(uuid.uuid4())
                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                metadata_str = json.dumps({"category": "knowledge", "file_name": file_name})
                
                v_blob = get_embedding(content)
                integrity_sig = compute_integrity(summary, content, metadata_str)
                
                cursor.execute(
                    "INSERT INTO memories (id, summary, content, vector_blob, metadata, ts, integrity) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (mem_id, summary, content, v_blob, metadata_str, ts, integrity_sig)
                )
                log_lines.append(f"Inserted L1 Memory for {file_name} (ID: {mem_id})")
                
            conn.commit()
            log_lines.append("L1 Ingestion committed successfully.")
            
            cursor.execute("SELECT id, summary, ts FROM memories WHERE content LIKE '%Weex%'")
            rows = cursor.fetchall()
            log_lines.append(f"Verified L1 Memories: retrieved {len(rows)} entries:")
            for r in rows:
                log_lines.append(f"  ID: {r[0]} | Summary: {r[1]} | TS: {r[2]}")
                
            conn.close()
    except Exception as e:
        log_lines.append(f"Exception: {e}")
        
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

if __name__ == "__main__":
    main()
