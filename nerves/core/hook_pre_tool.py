#!/usr/bin/env python3
import sys
import json
import subprocess
from pathlib import Path

# Add parent directories to path to ensure core imports work
AGENTS_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(AGENTS_ROOT))
sys.path.insert(0, str(AGENTS_ROOT / "nerves" / "core"))

try:
    import core_scar_memory as scar_memory
    import core_reflex as reflex
except ImportError as e:
    print(f"Failed to import core modules: {e}", file=sys.stderr)
    scar_memory = None
    reflex = None

def main():
    # 1. Read stdin
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception as e:
        # Fallback to allow if JSON parsing fails to avoid blocking the agent
        print(f"Error parsing stdin: {e}", file=sys.stderr)
        print(json.dumps({"decision": "allow"}))
        return

    # Extract tool information
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    
    print(f"[PreToolUse] Intercepting tool: {tool_name}", file=sys.stderr)

    # 2. Check if modifying files
    file_writing_tools = {"write_to_file", "replace_file_content", "multi_replace_file_content"}
    if tool_name in file_writing_tools and tool_input:
        target_file = tool_input.get("TargetFile")
        if target_file:
            # Run KG Guard physical check
            angati_exe = AGENTS_ROOT / "tools" / "angati" / "angati.exe"
            if angati_exe.exists():
                print(f"[PreToolUse] Running KG Guard on {target_file}", file=sys.stderr)
                try:
                    res = subprocess.run(
                        [str(angati_exe), "kg", "guard", "--file", str(target_file), "--action", "edit"],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="ignore",
                        timeout=15,
                        check=False
                    )
                    
                    # Log stderr output from kg guard
                    if res.stderr:
                        print(f"[KG Guard Stderr] {res.stderr.strip()}", file=sys.stderr)
                    
                    if res.returncode == 2:
                        print(f"[BLOCKED] [PreToolUse] Blocked by KG Guard for file {target_file}", file=sys.stderr)
                        # Return deny
                        print(json.dumps({
                            "decision": "deny",
                            "message": "Blocked by KG Guard (Exit Code 2). Write sandbox patch to C:\\Users\\pesil\\EAIS\\_sandbox_patches\\ instead."
                        }))
                        return
                    elif res.returncode == 1:
                        print(f"[WARN] [PreToolUse] Caution by KG Guard for file {target_file} (High impact / Protected Core)", file=sys.stderr)
                    else:
                        print(f"[OK] [PreToolUse] KG Guard passed for file {target_file}", file=sys.stderr)
                except Exception as e:
                    print(f"Failed to run KG Guard: {e}", file=sys.stderr)
            else:
                print(f"angati.exe not found at {angati_exe}", file=sys.stderr)

    # 3. Scar Consult & Circuit Breaker Check
    if reflex and tool_input:
        # Create an instruction representation of the tool call
        instruction = f"Executing tool {tool_name} with arguments: {json.dumps(tool_input)}"
        print("[PreToolUse] Running Cognitive Firewall reflex check...", file=sys.stderr)
        
        # Check Circuit Breaker
        if scar_memory:
            try:
                if scar_memory.circuit_breaker_check(instruction):
                    print("[BLOCKED] [PreToolUse] Circuit breaker tripped for this instruction!", file=sys.stderr)
                    print(json.dumps({
                        "decision": "deny",
                        "message": "Circuit breaker broken: This exact failure pattern has occurred >= 3 times in 1 hour."
                    }))
                    return
            except Exception as exc:
                print(f"Error checking circuit breaker: {exc}", file=sys.stderr)

        # Run general reflex rules and output them to stderr so the AI can see
        try:
            reflex_output = reflex.run_reflex(instruction)
            if reflex_output:
                print(reflex_output, file=sys.stderr)
        except Exception as exc:
            print(f"Error running reflex firewall: {exc}", file=sys.stderr)

    # Allow by default if no checks blocked it
    print(json.dumps({"decision": "allow"}))

if __name__ == "__main__":
    main()
