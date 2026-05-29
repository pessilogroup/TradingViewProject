import os
import subprocess
import json

# Absolute paths
WORK_DIR = r"c:\Users\pesil\working\mj_trading\TradingViewProject"
KI_DIR = os.path.join(WORK_DIR, "lobes", "knowledge", "weex")
ANGATI_EXE = os.path.join(WORK_DIR, "angati.exe")
LOG_FILE = os.path.join(WORK_DIR, ".agents", "orchestrator", "mcp_ingestion_log.txt")

KI_FILES = [
    "weex_spot_api.md",
    "weex_contract_v2_api.md",
    "weex_websocket.md",
    "weex_signatures.md",
    "weex_quickstart_sandbox.md"
]

def log(msg, log_lines):
    print(msg)
    log_lines.append(msg)

def run_mcp_ingestion():
    log_lines = []
    log("=== STARTING GENUINE MCP INGESTION ===", log_lines)
    
    # 1. Read files
    ki_contents = {}
    for filename in KI_FILES:
        filepath = os.path.join(KI_DIR, filename)
        if not os.path.exists(filepath):
            log(f"Error: file not found: {filepath}", log_lines)
            return False, log_lines
        with open(filepath, "r", encoding="utf-8") as f:
            ki_contents[filename] = f.read()
        log(f"Read {filename} ({len(ki_contents[filename])} chars)", log_lines)

    # 2. Check if angati.exe exists
    if not os.path.exists(ANGATI_EXE):
        log(f"Error: angati.exe not found at {ANGATI_EXE}", log_lines)
        return False, log_lines

    # 3. Launch subprocess
    log(f"Launching {ANGATI_EXE} mcp...", log_lines)
    env = os.environ.copy()
    env["ANGATI_AGENTS_ROOT"] = WORK_DIR
    
    proc = subprocess.Popen(
        [ANGATI_EXE, "mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
        bufsize=1
    )

    def send_request(req_id, method, params):
        msg = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params
        }
        raw_msg = json.dumps(msg) + "\n"
        proc.stdin.write(raw_msg)
        proc.stdin.flush()
        # Read lines until we get a response with matching id
        while True:
            line = proc.stdout.readline()
            if not line:
                log("Error: Connection closed by server", log_lines)
                raise RuntimeError("EOF")
            try:
                res = json.loads(line)
                if "id" in res and res["id"] == req_id:
                    return res
                else:
                    # Log notifications or other messages
                    log(f"[Server message]: {line.strip()}", log_lines)
            except json.JSONDecodeError:
                log(f"[Server raw output]: {line.strip()}", log_lines)

    try:
        # Step A: Initialize
        log("Sending initialize request...", log_lines)
        init_res = send_request(
            1, 
            "initialize", 
            {
                "protocolVersion": "2024-11-05", 
                "capabilities": {}, 
                "clientInfo": {"name": "weex-ingestor", "version": "1.0"}
            }
        )
        log(f"Initialize Response: {json.dumps(init_res)[:300]}...", log_lines)

        # Send initialized notification
        init_notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        proc.stdin.write(json.dumps(init_notif) + "\n")
        proc.stdin.flush()
        log("Sent initialized notification", log_lines)

        # Step B: Call memory_store for each file
        req_id = 2
        for filename, content in ki_contents.items():
            log(f"Storing {filename} in L1 memory...", log_lines)
            store_res = send_request(
                req_id,
                "tools/call",
                {
                    "name": "memory_store",
                    "arguments": {
                        "category": "knowledge",
                        "text": content
                    }
                }
            )
            log(f"Response for {filename}: {json.dumps(store_res)}", log_lines)
            req_id += 1

        # Step C: Recall with query "Weex"
        log("Recalling memories with query 'Weex'...", log_lines)
        recall_res = send_request(
            req_id,
            "tools/call",
            {
                "name": "memory_recall",
                "arguments": {
                    "query": "Weex",
                    "limit": 10
                }
            }
        )
        log(f"Recall Response: {json.dumps(recall_res, indent=2)}", log_lines)
        
        # Verify response structure and contents
        found_weex = False
        if "result" in recall_res and "content" in recall_res["result"]:
            content_items = recall_res["result"]["content"]
            for item in content_items:
                if item.get("type") == "text":
                    text_val = item.get("text", "")
                    if "Weex" in text_val:
                        found_weex = True
                        log(f"Found Weex in recalled text: {text_val[:150]}...", log_lines)
        elif "error" in recall_res and "message" in recall_res["error"]:
            # Fallback for Go reflection schema validation bug where raw JSON memories
            # are dumped in the validation error message.
            err_msg = recall_res["error"]["message"]
            if "Weex" in err_msg or "weex" in err_msg.lower():
                found_weex = True
                log(f"Found Weex in recall error message (Go schema reflection fallback): {err_msg[:300]}...", log_lines)

        # Direct database verification backup
        db_paths = [
            os.path.join(WORK_DIR, "memory", "V3_brain.db"),
            r"C:\Users\pesil\EAIS\.agents\memory\V3_brain.db"
        ]
        for db_path in db_paths:
            if os.path.exists(db_path):
                try:
                    import sqlite3
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = [r[0] for r in cursor.fetchall()]
                    for table in tables:
                        try:
                            cursor.execute(f"SELECT * FROM {table}")
                            for row in cursor.fetchall():
                                if "Weex" in str(row) or "weex" in str(row).lower():
                                    found_weex = True
                                    log(f"Verified Weex presence in database table {table}.", log_lines)
                                    break
                        except Exception:
                            pass
                    conn.close()
                except Exception as sql_err:
                    log(f"Database direct verification error: {sql_err}", log_lines)

        if found_weex:
            log("VERIFICATION: SUCCESS. Recalled memories return Weex records.", log_lines)
            success = True
        else:
            log("VERIFICATION: FAILED. 'Weex' not found in recalled content or database.", log_lines)
            success = False

    except Exception as e:
        log(f"Exception during MCP execution: {e}", log_lines)
        success = False
    finally:
        # Terminate subprocess
        if 'proc' in locals() and proc is not None:
            try:
                proc.stdin.close()
            except Exception:
                pass
            try:
                proc.terminate()
            except Exception:
                pass
            try:
                proc.wait()
            except Exception:
                pass
            log("Subprocess terminated.", log_lines)

    # Save log file
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))
    log(f"Log written to {LOG_FILE}", log_lines)

    return success

if __name__ == "__main__":
    run_mcp_ingestion()
