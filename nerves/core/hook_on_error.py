#!/usr/bin/env python3
import sys
import json
import subprocess
from pathlib import Path

AGENTS_ROOT = Path(__file__).resolve().parent.parent.parent

def main():
    # 1. Read stdin
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception as e:
        print(f"Error parsing stdin: {e}", file=sys.stderr)
        print(json.dumps({}))
        return

    # Extract error details
    tool_name = input_data.get("tool_name", "")
    error_message = input_data.get("error_message", "")
    # tool_input is not used by this handler but preserved for forward-compatibility
    # tool_input = input_data.get("tool_input", {})
    
    print(f"[ERROR] [OnError] Detected failure in tool '{tool_name}'!", file=sys.stderr)
    if error_message:
        print(f"[ERROR] [OnError] Error message: {error_message}", file=sys.stderr)

    # 2. Trigger incident triage via nerves/workers/incident_responder.py
    incident_responder = AGENTS_ROOT / "nerves" / "workers" / "incident_responder.py"
    if incident_responder.exists():
        print("[OnError] Running automatic incident triage: incident_responder.py check", file=sys.stderr)
        try:
            res = subprocess.run(
                ["python", str(incident_responder), "check"],
                cwd=str(AGENTS_ROOT),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=30,
                check=False
            )
            
            # Print triage results to stderr so they show up in the console
            if res.stdout:
                print(f"[Incident Responder Output]\n{res.stdout.strip()}", file=sys.stderr)
            if res.stderr:
                print(f"[Incident Responder Stderr]\n{res.stderr.strip()}", file=sys.stderr)

            if res.returncode == 0:
                print("[OK] [OnError] Incident triage completed successfully.", file=sys.stderr)
            else:
                print(f"[WARN] [OnError] Incident triage exited with code {res.returncode}", file=sys.stderr)
        except subprocess.TimeoutExpired:
            print("[WARN] [OnError] Incident responder timed out after 30s", file=sys.stderr)
        except Exception as exc:
            print(f"Failed to execute incident responder: {exc}", file=sys.stderr)
    else:
        print(f"incident_responder.py not found at {incident_responder}", file=sys.stderr)

    # Output empty JSON to let the agent continue
    print(json.dumps({}))

if __name__ == "__main__":
    main()
