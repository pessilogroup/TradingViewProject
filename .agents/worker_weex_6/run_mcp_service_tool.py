import os
import sys
import subprocess
import json
import time

WORK_DIR = r"c:\Users\pesil\working\mj_trading\TradingViewProject"
ANGATI_EXE = os.path.join(WORK_DIR, "angati.exe")

def run_mcp_interaction():
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
        while True:
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError("EOF")
            try:
                res = json.loads(line)
                if "id" in res and res["id"] == req_id:
                    return res
            except json.JSONDecodeError:
                pass

    try:
        # Initialize
        init_res = send_request(
            1, 
            "initialize", 
            {
                "protocolVersion": "2024-11-05", 
                "capabilities": {}, 
                "clientInfo": {"name": "weex-ingestor", "version": "1.0"}
            }
        )
        print("Initialize completed.")

        init_notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        proc.stdin.write(json.dumps(init_notif) + "\n")
        proc.stdin.flush()

        # Call angati_status
        print("Calling angati_status...")
        status_res = send_request(
            2,
            "tools/call",
            {
                "name": "angati_status",
                "arguments": {}
            }
        )
        print("angati_status response:")
        print(json.dumps(status_res, indent=2))

        # Check the service on port 4747. Let's find its status.
        # The result from tools/call usually has:
        # { "result": { "content": [ { "type": "text", "text": "..." } ] } } or similar
        content = status_res.get("result", {}).get("content", [])
        services_text = ""
        for c in content:
            if c.get("type") == "text":
                services_text = c.get("text", "")
        
        print("Services text:")
        print(services_text)

        # Parse services text as json if possible, or search for "git_nexus.py"
        # Let's restart git_nexus.py
        print("Calling service_restart for git_nexus.py...")
        restart_res = send_request(
            3,
            "tools/call",
            {
                "name": "service_restart",
                "arguments": {
                    "name": "git_nexus.py"
                }
            }
        )
        print("service_restart response:")
        print(json.dumps(restart_res, indent=2))

        # Wait a few seconds for it to start
        print("Waiting 5 seconds for service to initialize...")
        time.sleep(5)

        # Call angati_status again
        print("Calling angati_status again to verify...")
        status_res_2 = send_request(
            4,
            "tools/call",
            {
                "name": "angati_status",
                "arguments": {}
            }
        )
        print("Second angati_status response:")
        print(json.dumps(status_res_2, indent=2))

    except Exception as e:
        print(f"Error: {e}")
    finally:
        proc.stdin.close()
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    run_mcp_interaction()
