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

db_path = r"C:\Users\pesil\EAIS\memory\V3_brain.db"
ki_dir = r"c:\Users\pesil\working\mj_trading\TradingViewProject\lobes\knowledge\weex"
graph_path = r"C:\Users\pesil\EAIS\.agents\cortex\config\mcp_memory_graph.json"
log_path = r"c:\Users\pesil\working\mj_trading\TradingViewProject\.agents\worker_weex_4\execution_log.txt"

log_lines = []

def log(msg):
    print(msg)
    log_lines.append(msg)

def get_embedding(text):
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:4747/api/embed",
            data=json.dumps({"text": text}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=3) as response:
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
        # Fallback to zero vector
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
    log("=== WEEX MEMORY VERIFICATION & INGESTION START ===")
    log(f"Timestamp: {datetime.datetime.now().isoformat()}")
    
    # 1. Read the 5 local KI files
    ki_files = [
        ("weex_spot_api.md", "Weex Spot API reference including base URL, headers, order operations, and request/response examples."),
        ("weex_contract_v2_api.md", "Weex Contract V2 API reference covering base URL, _UMCBL suffix, order operations, positions, and V2 migration changelog."),
        ("weex_websocket.md", "Weex WebSocket API specification outlining public tickers subscriptions, tickers payloads, and login authentication."),
        ("weex_signatures.md", "Weex signature calculation mechanism details and executable Python hmac/hashlib/base64 code example."),
        ("weex_quickstart_sandbox.md", "Weex Sandbox (Demo Mode) reference including sandbox URLs, demo keys rules, and mock assets matrix.")
    ]
    
    kis_data = {}
    for file_name, summary in ki_files:
        file_path = os.path.join(ki_dir, file_name)
        if not os.path.exists(file_path):
            file_path = os.path.join(r"C:\Users\pesil\EAIS\.agents\lobes\knowledge\weex", file_name)
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                kis_data[file_name] = {"summary": summary, "content": content}
                log(f"Loaded KI file: {file_name} ({len(content)} bytes)")
        else:
            log(f"Error: KI file {file_name} not found in local or EAIS paths!")
            
    # 2. Check Database presence and contents
    if not os.path.exists(db_path):
        log(f"Error: Database V3_brain.db not found at {db_path}!")
        write_logs()
        return
        
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verify table structure
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memories';")
        if not cursor.fetchone():
            log("Error: memories table not found in V3_brain.db!")
            conn.close()
            write_logs()
            return
            
        log("Table 'memories' exists. Checking existing Weex records...")
        
        # Retrieve all Weex memories
        cursor.execute("SELECT id, summary, content, metadata, ts, integrity FROM memories WHERE content LIKE '%Weex%' OR summary LIKE '%Weex%'")
        existing_rows = cursor.fetchall()
        log(f"Found {len(existing_rows)} existing Weex memories in database:")
        
        existing_by_file = {}
        for row in existing_rows:
            rid, rsummary, rcontent, rmetadata_str, rts, rintegrity = row
            try:
                rmetadata = json.loads(rmetadata_str) if rmetadata_str else {}
            except Exception:
                rmetadata = {}
            
            file_name = rmetadata.get("file_name")
            category = rmetadata.get("category")
            log(f"  Row ID: {rid} | File: {file_name} | Category: {category} | Integrity: {rintegrity} | TS: {rts}")
            
            if file_name:
                existing_by_file[file_name] = {
                    "id": rid,
                    "summary": rsummary,
                    "content": rcontent,
                    "metadata_str": rmetadata_str,
                    "metadata": rmetadata,
                    "ts": rts,
                    "integrity": rintegrity
                }
                
        # 3. Verify each file's integrity signature and ingest if missing/mismatched
        db_changed = False
        for file_name, file_info in kis_data.items():
            summary = file_info["summary"]
            content = file_info["content"]
            metadata_str = json.dumps({"category": "knowledge", "file_name": file_name})
            
            expected_sig = compute_integrity(summary, content, metadata_str)
            
            if file_name in existing_by_file:
                db_record = existing_by_file[file_name]
                db_sig = db_record["integrity"]
                db_content = db_record["content"]
                db_summary = db_record["summary"]
                db_category = db_record["metadata"].get("category")
                
                # Check if content, summary, category, or integrity differs
                if db_sig != expected_sig or db_content != content or db_summary != summary or db_category != "knowledge":
                    log(f"Signature or content mismatch for {file_name}!")
                    log(f"  DB Sig: {db_sig} | Expected Sig: {expected_sig}")
                    log(f"  DB Category: {db_category} | Expected: knowledge")
                    log(f"Updating memory record for {file_name}...")
                    
                    v_blob = get_embedding(content)
                    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    cursor.execute(
                        "UPDATE memories SET summary = ?, content = ?, vector_blob = ?, metadata = ?, ts = ?, integrity = ? WHERE id = ?",
                        (summary, content, v_blob, metadata_str, ts, expected_sig, db_record["id"])
                    )
                    db_changed = True
                    log(f"  Updated ID: {db_record['id']}")
                else:
                    log(f"Integrity check PASSED for {file_name}. Signature matches: {db_sig}")
            else:
                log(f"Memory record for {file_name} is missing. Ingesting...")
                mem_id = str(uuid.uuid4())
                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                v_blob = get_embedding(content)
                
                cursor.execute(
                    "INSERT INTO memories (id, summary, content, vector_blob, metadata, ts, integrity) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (mem_id, summary, content, v_blob, metadata_str, ts, expected_sig)
                )
                db_changed = True
                log(f"  Inserted new ID: {mem_id} with integrity {expected_sig}")
                
        if db_changed:
            conn.commit()
            log("Changes committed to database successfully.")
        else:
            log("No database changes required. All integrity signatures are valid and match.")
            
        # 4. Perform verification queries
        log("\n=== RUNNING VERIFICATION QUERIES ===")
        cursor.execute("SELECT id, summary, ts, integrity FROM memories WHERE content LIKE '%Weex%' OR summary LIKE '%Weex%'")
        verified_rows = cursor.fetchall()
        log(f"Verification Retrieval: Found {len(verified_rows)} Weex records in database:")
        for r in verified_rows:
            log(f"  ID: {r[0]} | Summary: {r[1]} | TS: {r[2]} | Integrity: {r[3]}")
            
        conn.close()
    except Exception as e:
        log(f"Error during SQLite verification/ingestion: {e}")
        
    # 5. Verify Graph config
    log("\n=== VERIFYING GRAPH MEMORY CONFIG ===")
    if os.path.exists(graph_path):
        try:
            with open(graph_path, "r", encoding="utf-8") as f:
                graph_data = json.load(f)
            log("Loaded graph memory JSON successfully.")
            
            entities = graph_data.get("entities", [])
            relations = graph_data.get("relations", [])
            
            target_entity_names = [
                "Weex Exchange",
                "Weex Spot API",
                "Weex Contract V2 API",
                "Weex WebSocket API",
                "Weex Signatures",
                "Weex Sandbox"
            ]
            
            found_entities = [e for e in entities if e["name"] in target_entity_names]
            log(f"Found {len(found_entities)} Weex entities out of {len(target_entity_names)} required:")
            for fe in found_entities:
                log(f"  Entity: {fe['name']} (Type: {fe['entityType']})")
                
            found_rels = [r for r in relations if r["from"] in target_entity_names or r["to"] in target_entity_names]
            log(f"Found {len(found_rels)} Weex relations in graph config:")
            for fr in found_rels:
                log(f"  Relation: {fr['from']} -[{fr['relationType']}]-> {fr['to']}")
                
            if len(found_entities) == len(target_entity_names):
                log("GRAPH VERIFICATION: SUCCESS (All 6 Weex entities and their relations are verified in config)")
            else:
                log("GRAPH VERIFICATION: INCOMPLETE (Some entities are missing!)")
        except Exception as e:
            log(f"Error reading/parsing graph memory JSON: {e}")
    else:
        log(f"Error: Graph config file not found at {graph_path}!")
        
    log("=== WEEX MEMORY VERIFICATION & INGESTION END ===")
    write_logs()

def write_logs():
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

if __name__ == "__main__":
    main()
